# azure_llm_client.py

import os
from openai import AzureOpenAI
from typing import List, Dict, Optional # Para type hinting
import traceback # Para logging de erros mais detalhado
import re 

class AzureLLMClient:
    """
    Uma classe para interagir com um modelo LLM implementado no Azure OpenAI.
    """
    def __init__(self, azure_endpoint: str, api_key: str, deployment_name: str, api_version: str = "2024-05-01-preview"): # API version atualizada para uma mais recente
        """
        Inicializa o cliente Azure OpenAI.

        Args:
            azure_endpoint: O endpoint URL para o recurso Azure OpenAI.
            api_key: A chave API para autenticação.
            deployment_name: O nome do modelo implementado (deployment).
            api_version: A versão da API a ser usada.
        """
        self.azure_endpoint = azure_endpoint
        self.api_key = api_key
        self.deployment_name = deployment_name
        self.api_version = api_version
        self.client = None

        try:
            print(f"Inicializando cliente com API version: {self.api_version}")
            self.client = AzureOpenAI(
                api_version=self.api_version,
                azure_endpoint=self.azure_endpoint,
                api_key=self.api_key,
            )
            print("Cliente Azure OpenAI inicializado com sucesso.")
        except Exception as e:
            print(f"Erro Crítico: Falha ao inicializar o cliente AzureOpenAI: {e}")
            print(traceback.format_exc())

    def get_completion(self, messages: List[Dict[str, str]], max_tokens: Optional[int] = None) -> Optional[str]:
        """
        Envia uma lista de mensagens para o modelo LLM e retorna a resposta.
        """
        if not self.client:
            print("Erro: O cliente AzureOpenAI não foi inicializado corretamente.")
            return None

        try:
            params = {
                "model": self.deployment_name,
                "messages": messages
            }
            
            if max_tokens is not None:
                params["max_completion_tokens"] = max_tokens

            print(f"DEBUG: Enviando requisição para o deployment '{self.deployment_name}'")
            # Para evitar logs muito grandes, não vamos imprimir os 'messages' completos aqui se forem extensos.
            # print(f"DEBUG: Parâmetros da requisição: {params}") 

            response = self.client.chat.completions.create(**params)

            if response.choices:
                choice = response.choices[0]
                raw_content = choice.message.content
                finish_reason = choice.finish_reason
                
                print(f"DEBUG: Tokens de prompt: {response.usage.prompt_tokens}")
                print(f"DEBUG: Tokens de completion gerados: {response.usage.completion_tokens}")
                print(f"DEBUG: Custo total em tokens: {response.usage.total_tokens}")
                print(f"DEBUG: Finish reason: {finish_reason}")
                print(f"DEBUG: Conteúdo bruto da resposta ANTES DO STRIP: '{raw_content}'")

                if raw_content is None:
                    print("AVISO: Conteúdo da mensagem da API é None.")
                    return None 
                
                if finish_reason == "length":
                    print("AVISO: A resposta do modelo foi truncada porque o limite de 'max_completion_tokens' foi atingido.")
                
                return raw_content.strip()
            else:
                print("AVISO: A resposta da API não continha 'choices'.")
                return None

        except Exception as e:
            print(f"Ocorreu um erro ao chamar a API do Azure OpenAI: {e}")
            print(traceback.format_exc())
            return None

    def filter_candidates_by_description(self, candidates_data: List[Dict[str, str]], 
                                        role_description: str, 
                                        max_tokens: int = 1500,
                                        chunk_size: int = 10) -> Dict:  # Novo parâmetro chunk_size
        """
        Filtra candidatos em chunks menores, pedindo à IA para retornar apenas Nome e Perfil dos matches.
        
        Args:
            candidates_data: Lista de dicionários com 'name' e 'profile' dos candidatos.
            role_description: Descrição do role ou keywords para filtrar.
            max_tokens: Limite de tokens para a resposta da API por chunk.
            chunk_size: Número de candidatos por chunk/requisição.
                
        Returns:
            dict: Contendo 'matched_profiles' (lista de dicts com nome e perfil) ou 'error'.
        """
        try:
            if not self.client:
                return {"error": "Cliente Azure OpenAI não inicializado."}
            if not candidates_data:
                return {"error": "Nenhum candidato fornecido para análise."}
            
            system_message = """Você é um assistente de recrutamento altamente eficiente. 
            Sua tarefa é analisar perfis de candidatos e identificar aqueles com PROBABILIDADE de corresponder 
            a uma descrição de vaga ou keywords. Seja conciso e preciso."""
            
            # Dividir candidatos em chunks
            all_matched_profiles = []
            total_chunks = (len(candidates_data) + chunk_size - 1) // chunk_size
            
            print(f"\n=== Iniciando Análise em Chunks ===")
            print(f"Total de candidatos: {len(candidates_data)}")
            print(f"Tamanho do chunk: {chunk_size}")
            print(f"Total de chunks: {total_chunks}\n")
            
            for chunk_index in range(0, len(candidates_data), chunk_size):
                chunk = candidates_data[chunk_index:chunk_index + chunk_size]
                current_chunk_number = (chunk_index // chunk_size) + 1
                
                print(f"\n--- Processando Chunk {current_chunk_number}/{total_chunks} ---")
                print(f"Candidatos neste chunk: {len(chunk)}")
                
                candidates_text_parts = []
                for i, c in enumerate(chunk):
                    name = c.get('name', 'N/A').strip()
                    profile = c.get('profile', 'N/A').strip()
                    if not name and not profile:
                        continue
                    candidates_text_parts.append(f"Candidato {i+1}:\nNome: {name}\nPerfil: {profile}")
                
                if not candidates_text_parts:
                    print(f"Chunk {current_chunk_number}: Todos os candidatos vazios, pulando.")
                    continue
                
                candidates_text = "\n\n".join(candidates_text_parts)
                
                user_message = f"""Analise os seguintes {len(candidates_text_parts)} candidatos e identifique aqueles que têm PROBABILIDADE de corresponder à seguinte descrição: {role_description}

    {candidates_text}

    Para CADA candidato que corresponder com PROBABILIDADE, responda APENAS no seguinte formato, um candidato por bloco:
    Nome: [Nome do Candidato]
    Perfil: [Perfil do Candidato]

    Se NENHUM candidato corresponder com probabilidade, responda apenas com "Não foram encontrados candidatos correspondentes."
    NÃO inclua explicações, níveis de correspondência ou qualquer outro texto além do solicitado."""
                
                messages = [
                    {"role": "system", "content": system_message},
                    {"role": "user", "content": user_message}
                ]
                
                print(f"\nChunk {current_chunk_number}: Enviando requisição para API OpenAI")
                print(f"Total de candidatos no chunk: {len(candidates_text_parts)}")
                
                response_text = self.get_completion(messages, max_tokens=max_tokens)
                
                print(f"\n=== Resposta da API para Chunk {current_chunk_number} ===")
                print(f"Resposta recebida: '{response_text}'\n")
                
                if response_text is None:
                    print(f"ERRO: Chunk {current_chunk_number} - Resposta None da API")
                    continue
                if not response_text.strip():
                    print(f"ERRO: Chunk {current_chunk_number} - Resposta vazia após strip")
                    continue

                # Processar resposta do chunk atual
                if response_text.strip().lower() == "não foram encontrados candidatos correspondentes.":
                    print(f"Chunk {current_chunk_number}: Nenhum candidato correspondente")
                    continue

                # Extrair candidatos da resposta do chunk
                pattern = re.compile(r"Nome:\s*(.*?)\nPerfil:\s*(.*?)(?=\nNome:|\Z)", re.DOTALL | re.IGNORECASE)
                chunk_matches = []
                
                for match in pattern.finditer(response_text):
                    name = match.group(1).strip()
                    profile_text = match.group(2).strip()
                    profile_text = re.sub(r"^Candidato\s*\d+:\s*", "", profile_text, flags=re.IGNORECASE).strip()
                    
                    if name:
                        chunk_matches.append({"name": name, "profile": profile_text})
                
                if chunk_matches:
                    print(f"Chunk {current_chunk_number}: {len(chunk_matches)} candidatos correspondentes encontrados")
                    all_matched_profiles.extend(chunk_matches)
                else:
                    print(f"Chunk {current_chunk_number}: Nenhum candidato extraído da resposta")

            # Resultados finais
            print(f"\n=== Resultados Finais ===")
            print(f"Total de candidatos correspondentes encontrados: {len(all_matched_profiles)}")
            
            if not all_matched_profiles:
                return {
                    "matched_profiles": [],
                    "raw_response": "Não foram encontrados candidatos correspondentes."
                }

            return {
                "matched_profiles": all_matched_profiles,
                "raw_response": f"Total de {len(all_matched_profiles)} candidatos correspondentes encontrados em {total_chunks} chunks."
            }
                    
        except Exception as e:
            print(f"Erro inesperado ao filtrar candidatos: {e}")
            print(traceback.format_exc())
            return {"error": f"Erro ao filtrar candidatos: {str(e)}"}


# Exemplo de uso (opcional, para teste direto do ficheiro)
if __name__ == '__main__':
    # Carregar de variáveis de ambiente para segurança
    AZURE_ENDPOINT = os.getenv("AZURE_OPENAI_ENDPOINT")
    AZURE_API_KEY = os.getenv("AZURE_OPENAI_API_KEY")
    AZURE_DEPLOYMENT_NAME = os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME") 
    AZURE_API_VERSION = os.getenv("AZURE_OPENAI_API_VERSION", "2024-05-01-preview")

    if not all([AZURE_ENDPOINT, AZURE_API_KEY, AZURE_DEPLOYMENT_NAME]):
        print("Por favor, defina as variáveis de ambiente: AZURE_OPENAI_ENDPOINT, AZURE_OPENAI_API_KEY, AZURE_OPENAI_DEPLOYMENT_NAME")
    else:
        client = AzureLLMClient(
            azure_endpoint=AZURE_ENDPOINT,
            api_key=AZURE_API_KEY,
            deployment_name=AZURE_DEPLOYMENT_NAME,
            api_version=AZURE_API_VERSION
        )

        sample_candidates = [
            {"name": "João Silva", "profile": "Engenheiro de Software com experiência em Python e AWS."},
            {"name": "Maria Oliveira", "profile": "Analista de Dados júnior, conhecimento em SQL e PowerBI."},
            {"name": "Carlos Pereira", "profile": "Gestor de Projetos com foco em metodologias ágeis e Python."},
            {"name": "Ana Costa", "profile": "Desenvolvedora Fullstack, proficiente em JavaScript, React, Node.js e Python."},
            {"name": "Pedro Alves", "profile": "Especialista em Segurança da Informação, CISSP, Python para automação de segurança."},
            {"name": "Sofia Santos", "profile": "Cientista de Dados Sénior, Machine Learning, Python, R, TensorFlow."}
        ]
        role_desc_python = "Engenheiro de Software Python"
        role_desc_security = "Especialista em Segurança com Python"

        print("\n--- Teste com Prompt Otimizado (Python Developer) ---")
        result_python = client.filter_candidates_by_description(sample_candidates, role_desc_python, max_tokens=800)
        
        if "error" in result_python:
            print(f"Erro: {result_python['error']}")
            if "raw_response" in result_python:
                 print(f"Resposta Bruta: {result_python['raw_response']}")
        elif result_python.get("matched_profiles"):
            print("Candidatos Correspondentes (Nome e Perfil):")
            for candidate in result_python["matched_profiles"]:
                print(f"  Nome: {candidate['name']}\n  Perfil: {candidate['profile']}\n")
        else:
            print("Nenhum candidato correspondente encontrado para Desenvolvedor Python.")
            if "raw_response" in result_python:
                 print(f"Resposta Bruta: {result_python['raw_response']}")


        print("\n--- Teste com Prompt Otimizado (Security Specialist) ---")
        result_security = client.filter_candidates_by_description(sample_candidates, role_desc_security, max_tokens=800)
        
        if "error" in result_security:
            print(f"Erro: {result_security['error']}")
            if "raw_response" in result_security:
                 print(f"Resposta Bruta: {result_security['raw_response']}")
        elif result_security.get("matched_profiles"):
            print("Candidatos Correspondentes (Nome e Perfil):")
            for candidate in result_security["matched_profiles"]:
                print(f"  Nome: {candidate['name']}\n  Perfil: {candidate['profile']}\n")
        else:
            print("Nenhum candidato correspondente encontrado para Especialista em Segurança.")
            if "raw_response" in result_security:
                 print(f"Resposta Bruta: {result_security['raw_response']}")

        print("\n--- Teste com Nenhum Candidato Correspondente (Prompt Otimizado) ---")
        no_match_role_desc = "Engenheiro Aeroespacial com experiência em foguetes interplanetários"
        no_match_result = client.filter_candidates_by_description(sample_candidates, no_match_role_desc, max_tokens=500)
        if "error" in no_match_result:
            print(f"Erro: {no_match_result['error']}")
            if "raw_response" in no_match_result:
                 print(f"Resposta Bruta: {no_match_result['raw_response']}")
        elif not no_match_result.get("matched_profiles"):
            print("Resultado esperado: Nenhum candidato correspondente.")
            if "raw_response" in no_match_result:
                 print(f"Resposta Bruta: {no_match_result['raw_response']}") # Deve ser "Não foram encontrados..."
        else:
            print("ERRO NO TESTE: Foram encontrados candidatos quando não deveriam.")
            for candidate in no_match_result["matched_profiles"]:
                print(f"  Nome: {candidate['name']}\n  Perfil: {candidate['profile']}\n")

