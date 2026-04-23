# candidate_extractor.py
import re 
import pandas as pd
from tkinter import messagebox
import os

class CandidateExtractor:
    def __init__(self, image_processor):
        self.image_processor = image_processor
        self.candidates = [] 

    def _clean_text(self, text):
         if not text:
             return ""
         cleaned = re.sub(r'\s+', ' ', text).strip()
         # remove underscores, travessões ou outros símbolos apenas se
         # aparecerem colados ao início/fim do token OCR
         cleaned = re.sub(r'^[\W_]+|[\W_]+$', '', cleaned)
         return cleaned

    def _clip_region_to_cell(self, region, cell_width, cell_height):
        x = max(0, region["left"])
        y = max(0, region["top"])
        w = min(region["width"], cell_width - x)
        h = min(region["height"], cell_height - y)
        return (x, y, w, h)

    def extract_name_and_profile_from_cell_image(self, 
                                            cell_image, 
                                            name_sub_region_coords_relative_to_cell, 
                                            profile_sub_region_coords_relative_to_cell):
        """
        Extrai nome e perfil de uma célula de candidato usando sub-regiões calibradas.
        
        Args:
            cell_image: Imagem PIL da célula completa do candidato
            name_sub_region_coords_relative_to_cell: Coordenadas da sub-região do nome
            profile_sub_region_coords_relative_to_cell: Coordenadas da sub-região do perfil
        
        Returns:
            dict: Dicionário com 'name' e 'profile' ou None se não for possível extrair
        """
        candidate_data = {"name": "", "profile": ""}
        extracted_something = False
        
        # Obter dimensões da célula para validação
        cell_w, cell_h = cell_image.size
        print(f"\nDEBUG EXTRACT: Dimensões da célula: {cell_w}x{cell_h}")

        # Salvar imagem da célula completa para debug
        if hasattr(self.image_processor, 'debug') and self.image_processor.debug:
            try:
                os.makedirs("debug_files", exist_ok=True)
                debug_cell_path = os.path.join("debug_files", "debug_full_cell.png")
                cell_image.save(debug_cell_path)
                print(f"DEBUG EXTRACT: Imagem da célula completa salva em {debug_cell_path}")
            except Exception as e:
                print(f"DEBUG EXTRACT: Erro ao salvar imagem de debug da célula: {e}")

        # --- Extração do Nome ---
        if name_sub_region_coords_relative_to_cell:
            try:
                print(f"DEBUG EXTRACT: Tentando extrair nome com coords originais: {name_sub_region_coords_relative_to_cell}")
                
                # Garantir que as coordenadas estão dentro dos limites da célula
                region = self._clip_region_to_cell(name_sub_region_coords_relative_to_cell, cell_w, cell_h)
                print(f"DEBUG EXTRACT: Região ajustada para nome após clipping: {region}")
                
                # Salvar sub-região do nome para debug
                if hasattr(self.image_processor, 'debug') and self.image_processor.debug:
                    try:
                        name_region_img = cell_image.crop((
                            region[0], region[1],
                            region[0] + region[2],
                            region[1] + region[3]
                        ))
                        debug_name_path = os.path.join("debug_files", "debug_name_region.png")
                        name_region_img.save(debug_name_path)
                        print(f"DEBUG EXTRACT: Sub-região do nome salva em {debug_name_path}")
                    except Exception as e:
                        print(f"DEBUG EXTRACT: Erro ao salvar imagem de debug do nome: {e}")
                
                # Extrair texto da sub-região do nome
                name_text_raw = self.image_processor.extract_text(
                    cell_image, 
                    region_in_image_to_ocr=region
                )
                
                candidate_data["name"] = self._clean_text(name_text_raw)
                if candidate_data["name"]:
                    extracted_something = True
                    print(f"DEBUG EXTRACT: Nome extraído da sub-região: '{candidate_data['name']}'")
                else:
                    print("DEBUG EXTRACT: Nome extraído está vazio após limpeza")
                    
            except Exception as e:
                print(f"ERRO ao extrair nome da sub-região: {e}")
                traceback.print_exc()
        else:
            print("DEBUG EXTRACT: Sub-região do Nome não calibrada, usando fallback da célula inteira")
            try:
                full_cell_text_raw = self.image_processor.extract_text(cell_image)
                lines = [line.strip() for line in full_cell_text_raw.strip().split('\n') if line.strip()]
                if lines:
                    candidate_data["name"] = self._clean_text(lines[0])
                    if candidate_data["name"]:
                        extracted_something = True
                    print(f"DEBUG EXTRACT: Nome (fallback da célula inteira): '{candidate_data['name']}'")
            except Exception as e:
                print(f"ERRO no fallback do nome: {e}")

        # --- Extração do Perfil ---
        if profile_sub_region_coords_relative_to_cell:
            try:
                print(f"DEBUG EXTRACT: Tentando extrair perfil com coords originais: {profile_sub_region_coords_relative_to_cell}")
                
                # Garantir que as coordenadas estão dentro dos limites da célula
                region = self._clip_region_to_cell(profile_sub_region_coords_relative_to_cell, cell_w, cell_h)
                print(f"DEBUG EXTRACT: Região ajustada para perfil após clipping: {region}")
                
                # Salvar sub-região do perfil para debug
                if hasattr(self.image_processor, 'debug') and self.image_processor.debug:
                    try:
                        profile_region_img = cell_image.crop((
                            region[0], region[1],
                            region[0] + region[2],
                            region[1] + region[3]
                        ))
                        debug_profile_path = os.path.join("debug_files", "debug_profile_region.png")
                        profile_region_img.save(debug_profile_path)
                        print(f"DEBUG EXTRACT: Sub-região do perfil salva em {debug_profile_path}")
                    except Exception as e:
                        print(f"DEBUG EXTRACT: Erro ao salvar imagem de debug do perfil: {e}")
                
                # Extrair texto da sub-região do perfil
                profile_text_raw = self.image_processor.extract_text(
                    cell_image, 
                    region_in_image_to_ocr=region
                )
                
                candidate_data["profile"] = self._clean_text(profile_text_raw)
                if candidate_data["profile"]:
                    extracted_something = True
                    print(f"DEBUG EXTRACT: Perfil extraído da sub-região: '{candidate_data['profile']}'")
                else:
                    print("DEBUG EXTRACT: Perfil extraído está vazio após limpeza")
                    
            except Exception as e:
                print(f"ERRO ao extrair perfil da sub-região: {e}")
                traceback.print_exc()
        else:
            print("DEBUG EXTRACT: Sub-região do Perfil não calibrada, usando fallback da célula inteira")
            try:
                if 'lines' not in locals(): 
                    full_cell_text_raw = self.image_processor.extract_text(cell_image)
                    lines = [line.strip() for line in full_cell_text_raw.strip().split('\n') if line.strip()]
                if len(lines) > 1:
                    candidate_data["profile"] = self._clean_text(lines[1])
                    if candidate_data["profile"]:
                        extracted_something = True
                    print(f"DEBUG EXTRACT: Perfil (fallback da célula inteira): '{candidate_data['profile']}'")
            except Exception as e:
                print(f"ERRO no fallback do perfil: {e}")

        # Resultado final
        if extracted_something and candidate_data.get("name", "").strip():
            print(f"DEBUG EXTRACT: Extração bem-sucedida: {candidate_data}")
            return candidate_data
        else:
            print("DEBUG EXTRACT: Nenhum dado válido extraído")
            return None

    def save_to_xlsx(self, filename="candidates.xlsx"):
        if not self.candidates:
            print("Nenhum candidato para salvar em XLSX.")
            return None
        try:
            df = pd.DataFrame(self.candidates)
            if 'name' not in df.columns:
                df['name'] = ""
            if 'profile' not in df.columns:
                df['profile'] = ""
            
            df_to_save = df[['name', 'profile']]
            df_to_save.to_excel(filename, index=False, engine='openpyxl')
            print(f"Dados salvos com sucesso em {filename}")
            return filename
        except ImportError:
            print("ERRO: A biblioteca 'openpyxl' é necessária para salvar em XLSX. Instale com 'pip install openpyxl'")
            # Poderia levantar um erro aqui ou retornar None para a GUI tratar
            messagebox.showerror("Dependência em Falta", "A biblioteca 'openpyxl' é necessária para salvar em XLSX.\nPor favor, instale-a com: pip install openpyxl")
            return None
        except Exception as e:
            print(f"Erro ao salvar arquivo XLSX: {e}")
            messagebox.showerror("Erro ao Salvar XLSX", f"Ocorreu um erro ao salvar o arquivo XLSX:\n{e}")
            return None

