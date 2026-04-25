# config_manager.py
import json
import os

class ConfigManager:
    def __init__(self, config_file="calibration.json"):
        self.config_file = config_file
        # self.config é agora atualizado por load_config()
        self.config = self._load_config_data() # Carregar na inicialização

    def _load_config_data(self): # Renomeado para uso interno
        """Carrega dados de configuração do ficheiro e retorna-os."""
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, 'r') as f:
                    loaded_data = json.load(f)
                    return loaded_data
            except Exception as e:
                print(f"Erro ao carregar configuração de '{self.config_file}': {e}")
                return {"regions": {}, "anchors": {}, "tesseract_path": "", "templates_path": ""} # Estrutura padrão
        else:
            print(f"Ficheiro de configuração '{self.config_file}' não encontrado. Usando configuração padrão.")
            return {"regions": {}, "anchors": {}, "tesseract_path": "", "templates_path": ""}

    def save_config(self): 
        """Salva o estado atual no ficheiro, preservando o que foi salvo pelo calibrador."""
        try:
            # 1. Carrega os dados mais frescos do disco
            current_file_data = {"regions": {}, "anchors": {}}
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    current_file_data = json.load(f)
            
            # 2. Mescla a memória atual sobre os dados frescos
            current_file_data.update(self.config)
            
            # 3. Salva a fusão de volta no disco
            with open(self.config_file, 'w') as f:
                json.dump(current_file_data, f, indent=4)
                
            # 4. Atualiza a memória
            self.config = current_file_data
            print(f"Configuração salva em '{self.config_file}'.")
        except Exception as e:
            print(f"Erro ao salvar configuração em '{self.config_file}': {e}")

    def get_regions(self):
        """Retorna as regiões configuradas, recarregando do ficheiro."""
        # Sempre recarrega para garantir dados frescos
        current_data = self._load_config_data()
        self.config["regions"] = current_data.get("regions", {}) # Atualiza a instância se necessário
        return self.config["regions"]
    
    def get_anchors(self):
        """Retorna os pontos âncora configurados, recarregando do ficheiro."""
        current_data = self._load_config_data()
        self.config["anchors"] = current_data.get("anchors", {})
        return self.config["anchors"]

    def set_regions(self, regions):
        """Define as regiões e salva a configuração."""
        self.config["regions"] = regions
        self.save_config()
    
    def set_anchors(self, anchors):
        """Define os pontos âncora e salva a configuração."""
        self.config["anchors"] = anchors
        self.save_config()
    
    def get_setting(self, key, default=None):
        """Obtém uma configuração específica, recarregando do ficheiro."""
        current_data = self._load_config_data()
        # Atualizar a configuração da instância com todos os settings carregados
        # para que set_setting funcione corretamente sobre a base mais recente.
        if key not in ["regions", "anchors"]: # Evitar sobrescrever o que get_regions/get_anchors já fizeram
            self.config[key] = current_data.get(key, default)
        return self.config.get(key, default) # Retorna da instância (agora atualizada)
    
    def set_setting(self, key, value):
        """Define uma configuração específica e salva a configuração."""
        # Carregar primeiro para não perder outros settings se self.config estiver desatualizado
        _ = self.get_setting(key) # Isso força o carregamento de current_data para self.config
        self.config[key] = value
        self.save_config()

    def reset_calibrations(self):
        """Reset regions, anchors, and profile circle to empty/None."""
        self.config["regions"] = {}
        self.config["anchors"] = {}
        self.config["reference_profile_circle_center"] = None  # <--- ADICIONA ESTA LINHA!
        self.save_config()
        print("Calibrações foram redefinidas para o estado inicial.")
