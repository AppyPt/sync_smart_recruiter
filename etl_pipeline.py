# etl_pipeline.py
import os
import hashlib
from datetime import datetime
from pymongo import MongoClient
from azure.storage.blob import BlobServiceClient, ContentSettings

class ETLPipeline:
    def __init__(self, config_manager, log_callback=None):
        """
        Inicializa o Pipeline de ETL ligando as configurações às credenciais do Azure.
        """
        self.config = config_manager
        self.log = log_callback if log_callback else print
        self.mongo_client = None
        self.db = None
        self.candidates_collection = None
        self.blob_service_client = None
        self.container_name = None

    def _connect_mongo(self):
        """Estabelece ligação ao MongoDB/Cosmos DB."""
        if self.mongo_client:
            return True
            
        conn_str = self.config.get_setting("mongo_connection_string")
        db_name = self.config.get_setting("mongo_db_name", "deliveryai_etl")
        
        if not conn_str:
            self.log("ETL: Connection String do MongoDB não configurada.")
            return False
            
        try:
            self.mongo_client = MongoClient(conn_str, tlsDisableOCSPEndpointCheck=True)
            self.db = self.mongo_client[db_name]
            self.candidates_collection = self.db['candidates']
            
            # Criar índice único no hash para evitar duplicados a nível de BD (se não existir)
            self.candidates_collection.create_index("candidate_hash", unique=True)
            return True
        except Exception as e:
            self.log(f"ETL: Erro ao ligar ao MongoDB: {e}")
            return False

    def _connect_blob(self):
        """Estabelece ligação ao Azure Blob Storage."""
        if self.blob_service_client:
            return True
            
        conn_str = self.config.get_setting("azure_blob_connection_string")
        self.container_name = self.config.get_setting("azure_blob_container_name", "cv-uploads")
        
        if not conn_str:
            self.log("ETL: Connection String do Azure Blob não configurada.")
            return False
            
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(conn_str)
            # Tentar obter ou criar o container
            container_client = self.blob_service_client.get_container_client(self.container_name)
            if not container_client.exists():
                container_client.create_container()
            return True
        except Exception as e:
            self.log(f"ETL: Erro ao ligar ao Azure Blob: {e}")
            return False

    def generate_candidate_hash(self, name, profile):
        """Gera um hash único baseado no nome e perfil para evitar duplicados."""
        raw_string = f"{str(name).lower().strip()}{str(profile).lower().strip()}"
        return hashlib.md5(raw_string.encode('utf-8')).hexdigest()

    def candidato_existe(self, candidate_hash):
        """Verifica se um candidato já existe na base de dados pelo seu hash."""
        if not self._connect_mongo():
            return False  # Se falhar a ligação, assume que não existe para processar

        try:
            # Procura se existe pelo menos um documento com este hash
            count = self.candidates_collection.count_documents({"candidate_hash": candidate_hash}, limit=1)
            return count > 0
        except Exception as e:
            self.log(f"ETL: Erro ao verificar existência do candidato: {e}")
            return False

    def upload_cv_to_blob(self, local_file_path):
        """Faz o upload do ficheiro PDF para o Azure Blob e retorna o URL público."""
        if not self._connect_blob() or not local_file_path or not os.path.exists(local_file_path):
            self.log(f"ETL: Falha na validação do ficheiro local ou credenciais do Blob: {local_file_path}")
            return None
            
        try:
            file_name = os.path.basename(local_file_path)
            blob_client = self.blob_service_client.get_blob_client(container=self.container_name, blob=file_name)
            
            with open(local_file_path, "rb") as data:
                blob_client.upload_blob(
                    data, 
                    overwrite=True, 
                    content_settings=ContentSettings(content_type='application/pdf')
                )
            
            # O blob_client.url devolve o link direto (podes precisar de SAS tokens futuramente se o container for privado)
            return blob_client.url
        except Exception as e:
            self.log(f"ETL: Erro no upload para Blob: {e}")
            return None

    def process_candidate(self, candidate_info, local_cv_path=None):
        """
        Orquestra a persistência de um candidato:
        1. Verifica duplicados via Hash.
        2. Faz upload do CV se existir.
        3. Grava/Atualiza metadados no Mongo com histórico.
        """
        if not self._connect_mongo():
            return False, "Erro de ligação à Base de Dados."

        name = candidate_info.get("name")
        profile = candidate_info.get("profile")
        
        if not name:
            return False, "Nome do candidato ausente, a ignorar."

        candidate_hash = self.generate_candidate_hash(name, profile)
        now = datetime.utcnow()
        
        # 1. Tratar o ficheiro CV
        blob_url = None
        if local_cv_path:
            self.log(f"ETL: A iniciar upload do CV para {name}...")
            blob_url = self.upload_cv_to_blob(local_cv_path)
            if blob_url:
                self.log(f"ETL: Upload concluído: {blob_url}")

        # 2. Preparar a estrutura do documento
        # Usamos $setOnInsert para dados que só gravamos na primeira vez
        # Usamos $push para o histórico
        # Usamos $set para o estado atual
        
        history_entry = {
            "stage": "CAPTURE_AND_LOAD",
            "timestamp": now,
            "details": f"Capturado via Bot. CV Uploaded: {'Sim' if blob_url else 'Não'}"
        }

        update_data = {
            "$setOnInsert": {
                "candidate_hash": candidate_hash,
                "name": name,
                "system_added_date_str": candidate_info.get("date"),
                "created_at": now
            },
             "$set": {
                 "profile": profile, # Movemos o profile para $set caso a pessoa mude de cargo
                 "location": candidate_info.get("location", ""), # <--- NOVO CAMPO INJETADO
                 "last_capture_at": now,
                 "etl_status": "PROCESSED",
                 "cv_metadata": {
                     "blob_url": blob_url,
                     "updated_at": now
                 }
             },
            "$push": {
                "processing_history": history_entry
            }
        }

        try:
            # Upsert: Insere se não existir, atualiza se existir (baseado no hash)
            result = self.candidates_collection.update_one(
                {"candidate_hash": candidate_hash},
                update_data,
                upsert=True
            )
            
            if result.upserted_id:
                return True, "Novo candidato inserido com sucesso na BD."
            else:
                return True, "Candidato já existia na BD, metadados e histórico atualizados."
                
        except Exception as e:
            return False, f"Erro ao gravar no Mongo: {e}"

    def close(self):
        """Fecha as ligações ativas."""
        if self.mongo_client:
            self.mongo_client.close()