import requests
import json
import traceback

class OllamaClient:
    def __init__(self, model_name="gemma2:2b", host="http://localhost:11434"):
        """
        Inicializa o cliente base para comunicar com o Ollama local.
        """
        self.model_name = model_name
        self.host = host
        self.api_url = f"{self.host}/api/generate"

    def _clean_json_response(self, response_text):
        """Limpa a resposta do LLM removendo blocos markdown."""
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        elif cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        return cleaned.strip()

    def _call_llm(self, system_prompt, user_prompt, temperature=0.0):
        """Método base para fazer a chamada HTTP ao Ollama."""
        payload = {
            "model": self.model_name,
            "system": system_prompt,
            "prompt": user_prompt,
            "stream": False,
            "options": {
                "temperature": temperature, # 0.0 forçar respostas determinísticas
                "num_predict": 50 # Precisamos de pouquíssimos tokens para um JSON pequeno
            }
        }
        
        try:
            response = requests.post(self.api_url, json=payload, timeout=30)
            if response.status_code == 200:
                result_json = response.json()
                raw_text = result_json.get("response", "")
                cleaned_text = self._clean_json_response(raw_text)
                
                try:
                    return {"success": True, "data": json.loads(cleaned_text)}
                except json.JSONDecodeError:
                    return {"success": False, "error": "LLM não retornou JSON válido.", "raw": cleaned_text}
            else:
                return {"success": False, "error": f"Erro HTTP {response.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # =========================================================================
    # MÉTODOS DE DECISÃO (Adiciona novos métodos aqui no futuro)
    # =========================================================================

    def evaluate_portuguese_name(self, candidate_name):
        """
        Avalia a probabilidade (0-100) de um nome ser português.
        """
        if not candidate_name or not candidate_name.strip():
            return 0
            
        system_prompt = """
        You are an expert linguistic analyzer. Your ONLY task is to evaluate if a given name is Portuguese or commonly used by Portuguese people.
        Return ONLY a valid JSON object with a single key "probability" containing an integer from 0 to 100.
        Do not include ANY other text, explanations, or markdown formatting.
        Example output: {"probability": 85}
        """
        
        user_prompt = f"Name to evaluate: {candidate_name}"
        
        result = self._call_llm(system_prompt, user_prompt)
        
        if result.get("success"):
            # Extrai o valor com segurança, assumindo 0 se algo falhar
            prob = result["data"].get("probability", 0)
            # Garante que é um inteiro entre 0 e 100
            return max(0, min(100, int(prob)))
        else:
            print(f"Erro ao avaliar nome '{candidate_name}': {result.get('error')} | Raw: {result.get('raw')}")
            return 0 # Em caso de dúvida/erro, devolve 0 ou podes mudar para devolver None se quiseres tratar o erro na interface

# Teste direto no terminal
if __name__ == "__main__":
    client = OllamaClient()
    
    nomes_teste = [
        "João Silva", 
        "Maria Leonor Correia", 
        "John Smith", 
        "Vladimir Putin", 
        "Ana dos Santos",
        "Wei Chen"
    ]
    
    print("A testar deteção de nomes portugueses...\n")
    for nome in nomes_teste:
        probabilidade = client.evaluate_portuguese_name(nome)
        print(f"Nome: {nome:<25} | Probabilidade PT: {probabilidade}%")