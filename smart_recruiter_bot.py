# smart_recruiter_bot.py
import pyautogui
import time
import os
import sys
from PIL import Image 
import traceback
import json
import uuid
from etl_pipeline import ETLPipeline

import subprocess

class LinuxWindow:
    """Classe que imita o comportamento do objeto Window do PyGetWindow"""
    def __init__(self, win_id, title):
        self.win_id = win_id
        self.title = title

    def activate(self):
        try:
            # Usa o xdotool para forçar a janela a vir para a frente
            subprocess.run(['xdotool', 'windowactivate', self.win_id], check=True, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"Erro ao ativar janela no Linux: {e}")

class LinuxWindowHelper:
    """Classe que imita o módulo PyGetWindow"""
    @staticmethod
    def getActiveWindow():
        try:
            # Pega o ID da janela ativa
            win_id = subprocess.check_output(['xdotool', 'getactivewindow']).decode('utf-8').strip()
            # Pega o título da janela usando o ID
            title = subprocess.check_output(['xdotool', 'getwindowname', win_id]).decode('utf-8').strip()
            return LinuxWindow(win_id, title)
        except Exception:
            return None

# Testa se o xdotool está instalado no sistema
try:
    subprocess.run(['xdotool', '--version'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    gw = LinuxWindowHelper() # Substitui o PyGetWindow pela nossa versão Linux
    print("Sucesso: xdotool detetado. Gestão de janelas ativa para Linux.")
except FileNotFoundError:
    print("AVISO BOT: xdotool não instalado no Ubuntu. Executa: sudo apt-get install xdotool")
    gw = None

try:
    import pyperclip
except ImportError:
    print("AVISO BOT: pyperclip não instalado. A escrita direta do caminho do ficheiro será tentada.")
    pyperclip = None

DEBUG_OUTPUT_DIR = "debug_files"

class SmartRecruiterBot:
    def __init__(self, config_manager, image_processor, candidate_extractor):
        self.config = config_manager 
        self.image_processor = image_processor
        self.candidate_extractor = candidate_extractor
        self.scroll_interval = 2.0 
        self.log_gui_callback = None
        self.gui_log_callback_capture = None
        self.stop_requested = False  # <--- NOVA LINHA: O interruptor de paragem

    def _log_to_gui(self, message):
        if self.log_gui_callback: 
            self.log_gui_callback(f"BOT_INTERACT: {message}")
        elif self.gui_log_callback_capture: 
            self.gui_log_callback_capture(f"BOT_CAPTURE: {message}")
        else:
            print(f"BOT (no_gui_log): {message}")

    def _get_calibrated_region_coords(self, region_name):
        current_regions_from_config_file = self.config.get_regions()
        if region_name in current_regions_from_config_file:
            return current_regions_from_config_file[region_name]
        
        if region_name == "Nome (Dentro da Célula)_rel_to_cell":
            alt_keys = ["Nome (Relativo ao Círculo)_offset_from_circle", "Nome (Relativo ao Círculo)"]
            for key in alt_keys:
                if key in current_regions_from_config_file:
                    data = current_regions_from_config_file[key]
                    if "offset_x" in data: 
                        return {"left": data["offset_x"], "top": data["offset_y"], "width": data["width"], "height": data["height"]}
                    elif "left" in data: 
                        return data 
        elif region_name == "Perfil (Dentro da Célula)_rel_to_cell":
            alt_keys = ["Perfil (Relativo ao Círculo)_offset_from_circle", "Perfil (Relativo ao Círculo)"]
            for key in alt_keys:
                if key in current_regions_from_config_file:
                    data = current_regions_from_config_file[key]
                    if "offset_x" in data: 
                        return {"left": data["offset_x"], "top": data["offset_y"], "width": data["width"], "height": data["height"]}
                    elif "left" in data: 
                        return data
        elif region_name == "Data (Dentro da Célula)_rel_to_cell":
            alt_keys = ["Data (Relativo ao Círculo)_offset_from_circle", "Data (Relativo ao Círculo)"]
            for key in alt_keys:
                if key in current_regions_from_config_file:
                    data = current_regions_from_config_file[key]
                    if "offset_x" in data: 
                        return {"left": data["offset_x"], "top": data["offset_y"], "width": data["width"], "height": data["height"]}
                    elif "left" in data: 
                        return data
        elif region_name == "Localização (Dentro da Célula)_rel_to_cell":
            alt_keys = ["Localização (Relativo ao Círculo)_offset_from_circle", "Localização (Relativo ao Círculo)"]
            for key in alt_keys:
                if key in current_regions_from_config_file:
                    data = current_regions_from_config_file[key]
                    if "offset_x" in data: 
                        return {"left": data["offset_x"], "top": data["offset_y"], "width": data["width"], "height": data["height"]}
                    elif "left" in data: 
                        return data
        
        self._log_to_gui(f"ERRO BOT: Região '{region_name}' não encontrada na calibração.")
        raise ValueError(f"Região '{region_name}' não encontrada na calibração.")

    def capture_region_pil(self, region_name_for_capture):
        try:
            region_coords = self._get_calibrated_region_coords(region_name_for_capture)
            return pyautogui.screenshot(region=(region_coords["left"], region_coords["top"], region_coords["width"], region_coords["height"]))
        except Exception as e:
            self._log_to_gui(f"ERRO BOT ao capturar região '{region_name_for_capture}': {e}")
            return Image.new('RGB', (100, 100), color='red')

    def _process_individual_cell(self, individual_cell_image_pil, circle_info_in_list_image, cell_start_x_in_list, cell_start_y_in_list, name_sub_region_calib, profile_sub_region_calib, date_sub_region_calib=None, location_sub_region_calib=None): # <--- NOVO ARGUMENTO
        if not individual_cell_image_pil: 
            return None
        
        initial_name_ocr_region_rel_to_cell = None
        if name_sub_region_calib and circle_info_in_list_image:
            circle_center_x_rel_to_cell = circle_info_in_list_image['center_x_abs'] - cell_start_x_in_list
            circle_center_y_rel_to_cell = circle_info_in_list_image['center_y_abs'] - cell_start_y_in_list
            initial_name_ocr_region_rel_to_cell = {
                "left": int(circle_center_x_rel_to_cell + name_sub_region_calib["left"]), 
                "top": int(circle_center_y_rel_to_cell + name_sub_region_calib["top"]), 
                "width": int(name_sub_region_calib["width"]), 
                "height": int(name_sub_region_calib["height"])
            }
        
        adjusted_profile_coords_for_ocr = None
        if profile_sub_region_calib and circle_info_in_list_image:
            circle_center_x_rel_to_cell = circle_info_in_list_image['center_x_abs'] - cell_start_x_in_list
            circle_center_y_rel_to_cell = circle_info_in_list_image['center_y_abs'] - cell_start_y_in_list
            adjusted_profile_coords_for_ocr = {
                "left": int(circle_center_x_rel_to_cell + profile_sub_region_calib["left"]), 
                "top": int(circle_center_y_rel_to_cell + profile_sub_region_calib["top"]), 
                "width": int(profile_sub_region_calib["width"]), 
                "height": int(profile_sub_region_calib["height"])
            }

        adjusted_date_coords_for_ocr = None
        if date_sub_region_calib and circle_info_in_list_image:
            circle_center_x_rel_to_cell = circle_info_in_list_image['center_x_abs'] - cell_start_x_in_list
            circle_center_y_rel_to_cell = circle_info_in_list_image['center_y_abs'] - cell_start_y_in_list
            adjusted_date_coords_for_ocr = {
                "left": int(circle_center_x_rel_to_cell + date_sub_region_calib["left"]), 
                "top": int(circle_center_y_rel_to_cell + date_sub_region_calib["top"]), 
                "width": int(date_sub_region_calib["width"]), 
                "height": int(date_sub_region_calib["height"])
            }

        adjusted_location_coords_for_ocr = None
        if location_sub_region_calib and circle_info_in_list_image:
            circle_center_x_rel_to_cell = circle_info_in_list_image['center_x_abs'] - cell_start_x_in_list
            circle_center_y_rel_to_cell = circle_info_in_list_image['center_y_abs'] - cell_start_y_in_list
            adjusted_location_coords_for_ocr = {
                "left": int(circle_center_x_rel_to_cell + location_sub_region_calib["left"]), 
                "top": int(circle_center_y_rel_to_cell + location_sub_region_calib["top"]), 
                "width": int(location_sub_region_calib["width"]), 
                "height": int(location_sub_region_calib["height"])
            }

        extracted_data = self.candidate_extractor.extract_name_and_profile_from_cell_image(
            individual_cell_image_pil, 
            initial_name_ocr_region_rel_to_cell, 
            adjusted_profile_coords_for_ocr,
            adjusted_date_coords_for_ocr,
            adjusted_location_coords_for_ocr # <--- ADICIONADO AQUI
        )
        
        if not extracted_data or not extracted_data.get("name"): 
            return {
                'extracted_data': None, 
                'name_precise_click_center_rel_to_cell': None, 
                'name_ocr_region_rel_to_cell': initial_name_ocr_region_rel_to_cell
            }

        extracted_name_str = extracted_data["name"]
        name_precise_click_center_rel_to_cell = None
        
        if initial_name_ocr_region_rel_to_cell and extracted_name_str:
            try:
                clipped_name_ocr_region = self.candidate_extractor._clip_region_to_cell(
                    initial_name_ocr_region_rel_to_cell, 
                    individual_cell_image_pil.width, 
                    individual_cell_image_pil.height
                )
                name_ocr_region_image_pil = individual_cell_image_pil.crop((
                    clipped_name_ocr_region[0], 
                    clipped_name_ocr_region[1], 
                    clipped_name_ocr_region[0] + clipped_name_ocr_region[2], 
                    clipped_name_ocr_region[1] + clipped_name_ocr_region[3]
                ))
                precise_name_box_in_sub_image = self.image_processor.get_text_bounding_box(
                    name_ocr_region_image_pil, 
                    extracted_name_str
                )
                
                if precise_name_box_in_sub_image:
                    precise_name_box_rel_to_cell = {
                        'left': clipped_name_ocr_region[0] + precise_name_box_in_sub_image['left'], 
                        'top': clipped_name_ocr_region[1] + precise_name_box_in_sub_image['top'], 
                        'width': precise_name_box_in_sub_image['width'], 
                        'height': precise_name_box_in_sub_image['height']
                    }
                    name_precise_click_center_rel_to_cell = (
                        int(precise_name_box_rel_to_cell['left'] + precise_name_box_rel_to_cell['width'] // 2), 
                        int(precise_name_box_rel_to_cell['top'] + precise_name_box_rel_to_cell['height'] // 2)
                    )
            except Exception: 
                pass
        
        if not name_precise_click_center_rel_to_cell and initial_name_ocr_region_rel_to_cell:
            name_precise_click_center_rel_to_cell = (
                int(initial_name_ocr_region_rel_to_cell['left'] + initial_name_ocr_region_rel_to_cell['width'] // 2), 
                int(initial_name_ocr_region_rel_to_cell['top'] + initial_name_ocr_region_rel_to_cell['height'] // 2)
            )
        
        return {
            'extracted_data': extracted_data, 
            'name_precise_click_center_rel_to_cell': name_precise_click_center_rel_to_cell, 
            'name_ocr_region_rel_to_cell': initial_name_ocr_region_rel_to_cell
        }

    def capture_candidates_with_cell_strategy(self, gui_log_callback_capture=None):
        """Captures candidates from the list using cell detection strategy with improved scrolling."""
        self.gui_log_callback_capture = gui_log_callback_capture 
        all_unique_candidates_data = [] 
        processed_candidate_names = set() 
        
        # ✅ ALTERAÇÃO 1: Configuração de scroll mais conservadora
        INITIAL_SCROLL_ADJUSTMENT = 3
        SCROLL_PERCENTAGE = 0.60  # REDUZIDO de 0.80 para 0.60
        MIN_SCROLL_PIXELS = 100
        SCROLL_STABILIZATION_DELAY = 0.5
        
        # ✅ ALTERAÇÃO 4: Tracking de posições Y para evitar duplicados
        
        try:
            # Get list area coordinates
            try:
                list_area_coords = self._get_calibrated_region_coords("Lista de Candidatos")
                if list_area_coords["height"] < 300:
                    self._log_to_gui("AVISO: Altura da região 'Lista de Candidatos' pode ser muito pequena!")
            except ValueError as e:
                self._log_to_gui(f"ERRO CRÍTICO BOT: {e}")
                return []

            # Initialize calibration regions
            name_sub_region_calib = None
            profile_sub_region_calib = None
            date_sub_region_calib = None
            try:
                name_sub_region_calib = self._get_calibrated_region_coords("Nome (Dentro da Célula)_rel_to_cell")
            except ValueError:
                self._log_to_gui("AVISO BOT: Sub-região 'Nome' não calibrada.")
            try:
                profile_sub_region_calib = self._get_calibrated_region_coords("Perfil (Dentro da Célula)_rel_to_cell")
            except ValueError:
                self._log_to_gui("AVISO BOT: Sub-região 'Perfil' não calibrada.")
            try:
                date_sub_region_calib = self._get_calibrated_region_coords("Data (Dentro da Célula)_rel_to_cell")
            except ValueError:
                self._log_to_gui("AVISO BOT: Sub-região 'Data' não calibrada.")
            location_sub_region_calib = None
            try:
                location_sub_region_calib = self._get_calibrated_region_coords("Localização (Dentro da Célula)_rel_to_cell")
            except ValueError:
                self._log_to_gui("AVISO BOT: Sub-região 'Localização' não calibrada.")

            # Calculate scroll points
            scroll_point_x = list_area_coords["left"] + list_area_coords["width"] // 2
            scroll_point_y = list_area_coords["top"] + list_area_coords["height"] // 2

            # Initial scroll to top
            self._log_to_gui("\n=== Ajustando posição inicial da lista ===")
            pyautogui.moveTo(scroll_point_x, scroll_point_y, duration=0.1)
            time.sleep(0.2)
            
            for i in range(INITIAL_SCROLL_ADJUSTMENT):
                pyautogui.press('home')
                time.sleep(0.3)
            
            self._log_to_gui("Lista posicionada no topo")
            time.sleep(SCROLL_STABILIZATION_DELAY)

            # Inicializar a conduta de gravação na BD
            self.etl_pipeline = ETLPipeline(self.config, log_callback=self._log_to_gui)

            # Main capture loop
            iteration = 0
            consecutive_iterations_without_new_candidates = 0
            cumulative_scroll_pixels = 0  # Para calcular posição Y absoluta

            while True:
                # ---> NOVO TRAVÃO 1
                if self.stop_requested:
                    self._log_to_gui("🛑 Captura interrompida pelo utilizador.")
                    break
                iteration += 1
                
                # ✅ ALTERAÇÃO 5: Logging melhorado
                self._log_to_gui(f"\n📊 Iteração de Captura #{iteration}")
                self._log_to_gui(f"   Candidatos únicos até agora: {len(processed_candidate_names)}")

                # Capture current view
                current_list_image_pil = self.capture_region_pil("Lista de Candidatos")
                
                # Debug save
                if hasattr(self.image_processor, 'debug') and self.image_processor.debug:
                    try:
                        os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                        current_list_image_pil.save(os.path.join(DEBUG_OUTPUT_DIR, f"debug_capture_iter_{iteration}.png"))
                    except Exception as e_save:
                        self._log_to_gui(f"ERRO BOT ao salvar imagem de debug: {e_save}")

                # Process cells in current view
                cells_with_circles = self.image_processor.identify_candidate_cells_by_profile_circles(current_list_image_pil)
                cells_count = len(cells_with_circles)
                self._log_to_gui(f"   Células detectadas: {cells_count}")

                # ✅ ALTERAÇÃO 2: Melhor detecção de células cortadas
                if cells_with_circles:
                    img_width, img_height = current_list_image_pil.size
                    last_cell = cells_with_circles[-1]
                    last_cell_region, last_circle_info = last_cell
                    last_cell_y_bottom = last_cell_region[1] + last_cell_region[3]
                    
                    BOTTOM_SAFETY_MARGIN = 40  # AUMENTADO de 20 para 40
                    
                    if img_height - last_cell_y_bottom < BOTTOM_SAFETY_MARGIN:
                        self._log_to_gui(f"⚠️ AVISO: Última célula pode estar cortada!")
                        self._log_to_gui(f"   Distância da borda: {img_height - last_cell_y_bottom}px < {BOTTOM_SAFETY_MARGIN}px")
                        
                        # Verificar altura suspeita
                        if last_cell_region[3] < 80:
                            self._log_to_gui(f"   Altura da célula suspeita: {last_cell_region[3]}px")
                            self._log_to_gui("   >> Célula será ignorada e processada na próxima iteração")
                            cells_with_circles = cells_with_circles[:-1]

                # Process each cell
                new_candidates_found_this_iteration = 0

                for i, (cell_region_in_list_image, circle_info_in_list_image) in enumerate(cells_with_circles):
                    # ---> NOVO TRAVÃO 2
                    if self.stop_requested:
                        break
                    x_cell, y_cell, w_cell, h_cell = cell_region_in_list_image

                    try:
                        individual_cell_image_pil = current_list_image_pil.crop((
                            x_cell, y_cell, x_cell + w_cell, y_cell + h_cell
                        ))
                        
                        if hasattr(self.image_processor, 'debug') and self.image_processor.debug:
                            individual_cell_image_pil.save(os.path.join(DEBUG_OUTPUT_DIR, f"debug_cell_iter{iteration}_idx{i}.png"))
                        
                        cell_processing_result = self._process_individual_cell(
                            individual_cell_image_pil,
                            circle_info_in_list_image,
                            x_cell, y_cell,
                            name_sub_region_calib,
                            profile_sub_region_calib,
                            date_sub_region_calib,
                            location_sub_region_calib # <--- ADICIONADO AQUI
                        )

                        if cell_processing_result and cell_processing_result['extracted_data']:
                            candidate_data = cell_processing_result['extracted_data']
                            if candidate_data.get("name") and candidate_data["name"].strip():
                                candidate_name = candidate_data["name"].strip()
                                if candidate_name not in processed_candidate_names:
                                    final_candidate_entry = {
                                        "name": candidate_name,
                                        "profile": candidate_data.get("profile", "").strip(),
                                        "date": candidate_data.get("date", "").strip(),
                                        "location": candidate_data.get("location", "").strip() # <--- ADICIONADO AQUI
                                    }
                                    all_unique_candidates_data.append(final_candidate_entry)
                                    processed_candidate_names.add(candidate_name)
                                    new_candidates_found_this_iteration += 1
                                    
                                    self._log_to_gui(f"   ✓ Célula #{i+1}: {candidate_name}")

                                    # =================================================================
                                    # INÍCIO DA LÓGICA DE DOWNLOAD INLINE DO CV
                                    # =================================================================
                                    name_click_center = cell_processing_result.get('name_precise_click_center_rel_to_cell')
                                    if name_click_center:
                                        # Calcula a coordenada X e Y absoluta no ecrã para o clique
                                        name_link_x_on_screen = list_area_coords["left"] + x_cell + name_click_center[0]
                                        name_link_y_on_screen = list_area_coords["top"] + y_cell + name_click_center[1]

                                        self._log_to_gui(f"   📥 Iniciando extração do CV para: {candidate_name}")
                                        try:
                                            # Shift+Click abre o link numa NOVA JANELA no Chrome
                                            pyautogui.keyDown('shift')
                                            pyautogui.click(name_link_x_on_screen, name_link_y_on_screen)
                                            pyautogui.keyUp('shift')

                                            # Aguarda a página do perfil carregar (sleep seguro/interrompível)
                                            delay_segundos = self.config.get_setting("page_load_delay_sec", 7)
                                            self._log_to_gui(f"   Aguardando {delay_segundos}s pelo carregamento do perfil...")
                                            
                                            for _ in range(int(delay_segundos * 10)):
                                                if self.stop_requested:
                                                    self._log_to_gui("   🛑 Cancelado enquanto aguardava a página abrir!")
                                                    break
                                                time.sleep(0.1)
                                                
                                            if self.stop_requested:
                                                continue # Salta este candidato e sai do ciclo
                                            
                                            # Chama a função que já tens pronta para baixar o CV e fechar a janela
                                            # Chama a função que já tens pronta para baixar o CV e fechar a janela
                                            # Agora devolve o PATH em vez de um booleano
                                            local_cv_path = self.process_candidate_profile_page(
                                                candidate_name, 
                                                final_candidate_entry["profile"]
                                            )
                                            
                                            if local_cv_path: # Se não for falso
                                                self._log_to_gui(f"   ✅ CV de {candidate_name} guardado localmente com sucesso!")
                                                final_candidate_entry["cv_downloaded"] = True
                                                
                                                # ==========================================
                                                # O MAGNÍFICO PIPELINE DE INJEÇÃO (ETL)
                                                # ==========================================
                                                
                                                # --- NOVO: ESPERAR PELO FICHEIRO NO DISCO (COM LOGS DE DEBUG) ---
                                                if local_cv_path:
                                                    # Extrair apenas o nome base (ex: Prince_Godspower_resume_05f9c10b)
                                                    base_name = os.path.basename(local_cv_path).replace('.pdf', '')
                                                    target_dir = os.path.dirname(local_cv_path)
                                                    self._log_to_gui(f"   Aguardando que o ficheiro que começa por '{base_name}' apareça...")
                                                    
                                                    timeout_contador = 0
                                                    file_found = False
                                                    actual_file_path = None

                                                    while timeout_contador < 10:
                                                        if os.path.exists(target_dir):
                                                            # LER E MOSTRAR TUDO O QUE ESTÁ NA PASTA
                                                            files_in_dir = os.listdir(target_dir)
                                                            self._log_to_gui(f"   [DEBUG DIR] Ficheiros na pasta: {files_in_dir}")
                                                            
                                                            for f in files_in_dir:
                                                                if f.startswith(base_name):
                                                                    # Ignorar ficheiros temporários de download do Chrome
                                                                    if f.endswith(".crdownload"):
                                                                        self._log_to_gui(f"   [DEBUG DIR] Download ainda em curso: {f}")
                                                                    else:
                                                                        actual_file_path = os.path.join(target_dir, f)
                                                                        file_found = True
                                                                        break
                                                        
                                                        if file_found:
                                                            break
                                                            
                                                        time.sleep(1) 
                                                        timeout_contador += 1
                                                        
                                                    if file_found and actual_file_path:
                                                        self._log_to_gui(f"   ✅ Ficheiro detetado e validado no disco: {actual_file_path}")
                                                        local_cv_path = actual_file_path # Atualiza para o caminho real encontrado (ex: .pdf.pdf)
                                                    else:
                                                        self._log_to_gui("   ⚠️ ERRO: O Chrome não gravou o ficheiro a tempo ou falhou a gravação!")
                                                        local_cv_path = None 
                                                # --------------------------------------------
                                                # --------------------------------------------

                                                sucesso_etl, msg_etl = self.etl_pipeline.process_candidate(
                                                    candidate_info=final_candidate_entry, 
                                                    local_cv_path=local_cv_path
                                                )
                                                self._log_to_gui(f"   ☁️ ETL: {msg_etl}")
                                                
                                                # --- APAGAR FICHEIRO LOCAL ---
                                                if local_cv_path and os.path.exists(local_cv_path):
                                                    try:
                                                        os.remove(local_cv_path)
                                                        self._log_to_gui("   🗑️ CV apagado do disco (guardado apenas no Azure).")
                                                    except Exception as e:
                                                        self._log_to_gui(f"   ⚠️ Erro ao apagar CV local: {e}")
                                                # -----------------------------------
                                                # ==========================================
                                            else:
                                                self._log_to_gui(f"   ⚠️ Não foi possível baixar o CV de {candidate_name}.")
                                                final_candidate_entry["cv_downloaded"] = False
                                                
                                        except Exception as e_click:
                                            self._log_to_gui(f"   ❌ ERRO ao tentar abrir o perfil de {candidate_name}: {e_click}")
                                            pyautogui.keyUp('shift') # Garantir que o shift não fica preso
                                            final_candidate_entry["cv_downloaded"] = False
                                    else:
                                        self._log_to_gui(f"   ⚠️ Sem coordenadas precisas para clicar em {candidate_name}. CV ignorado.")
                                        final_candidate_entry["cv_downloaded"] = False
                                    # =================================================================
                                    # FIM DA LÓGICA DE DOWNLOAD INLINE DO CV
                                    # =================================================================

                    except Exception as e_cell:
                        self._log_to_gui(f"ERRO BOT ao processar célula #{i+1}: {e_cell}")

                # Update iteration status
                if new_candidates_found_this_iteration == 0:
                    if iteration > 1 or (iteration == 1 and cells_count == 0):
                        consecutive_iterations_without_new_candidates += 1
                else:
                    consecutive_iterations_without_new_candidates = 0

                # Check termination conditions
                if consecutive_iterations_without_new_candidates >= 3:
                    self._log_to_gui("Nenhum novo candidato encontrado em 3 iterações consecutivas. Finalizando captura.")
                    break


                # ✅ ALTERAÇÃO 3: Cálculo dinâmico do scroll
                base_scroll_pixels = int(list_area_coords["height"] * SCROLL_PERCENTAGE)
                scroll_pixels = base_scroll_pixels
                
                # Ajuste dinâmico se última célula estava muito próxima da borda
                if cells_with_circles:
                    last_cell_region = cells_with_circles[-1][0]
                    last_cell_bottom = last_cell_region[1] + last_cell_region[3]
                    distance_from_bottom = current_list_image_pil.height - last_cell_bottom
                    
                    if distance_from_bottom < 40:
                        scroll_pixels = int(list_area_coords["height"] * 0.40)
                        self._log_to_gui(f"🔧 Ajuste: Última célula próxima da borda. Scroll reduzido para {scroll_pixels}px")
                
                scroll_pixels = max(MIN_SCROLL_PIXELS, scroll_pixels)
                
                # Execute scroll
                # Execute scroll
                # No Linux/Chrome, a aceleração do scroll é muito agressiva.
                # Cada "tick" roda cerca de 130 pixeis.
                PIXELS_POR_TICK = 130
                ticks_de_scroll = int(scroll_pixels / PIXELS_POR_TICK)
                scroll_amount = -max(1, ticks_de_scroll) # Garante que faz pelo menos 1 click para baixo
                
                self._log_to_gui(f"📜 Scroll: Calculado {scroll_pixels}px -> Executando {scroll_amount} ticks do rato")
                
                pyautogui.moveTo(scroll_point_x, scroll_point_y, duration=0.1)
                time.sleep(0.2)
                
                try:
                    pyautogui.scroll(scroll_amount)
                    cumulative_scroll_pixels += (abs(scroll_amount) * PIXELS_POR_TICK)
                except Exception as e_scroll:
                    self._log_to_gui(f"ERRO BOT ao executar scroll: {e_scroll}")
                
                time.sleep(self.scroll_interval)

            # Finalize capture
            self.candidate_extractor.candidates = all_unique_candidates_data
            self._log_to_gui(f"\n✅ Captura finalizada. Total de candidatos únicos: {len(all_unique_candidates_data)}")
            return all_unique_candidates_data

        except Exception as e:
            self._log_to_gui(f"ERRO CRÍTICO durante captura: {e}")
            traceback.print_exc()
            return []

    def _find_text_coords_in_region(self, calibrated_region_name, text_to_find):
        """Procura por um texto específico dentro de uma região calibrada."""
        self._log_to_gui(f"Procurando por texto '{text_to_find}' na região '{calibrated_region_name}'.")
        
        try:
            search_area_coords_on_screen = self._get_calibrated_region_coords(calibrated_region_name)
        except ValueError:
            self._log_to_gui(f"ERRO: Região '{calibrated_region_name}' não calibrada.")
            return None

        try:
            region_image_pil = pyautogui.screenshot(region=(
                search_area_coords_on_screen["left"],
                search_area_coords_on_screen["top"],
                search_area_coords_on_screen["width"],
                search_area_coords_on_screen["height"]
            ))

            if hasattr(self.image_processor, 'debug') and self.image_processor.debug:
                os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                if "Latest Resume" in text_to_find:
                    debug_filename = f"debug_latest_resume_region_{time.strftime('%H%M%S')}.png"
                    region_image_pil.save(os.path.join(DEBUG_OUTPUT_DIR, debug_filename))
                    self._log_to_gui(f"Imagem da região de busca do 'Latest Resume' salva: {debug_filename}")

            text_box_in_region_image = self.image_processor.get_text_bounding_box(region_image_pil, text_to_find)
            
            if text_box_in_region_image:
                click_x_rel_region = text_box_in_region_image['left'] + int(text_box_in_region_image['width'] * 0.20)
                click_y_rel_region = text_box_in_region_image['top'] + (text_box_in_region_image['height'] // 2)

                coords_on_screen = (
                    search_area_coords_on_screen['left'] + click_x_rel_region,
                    search_area_coords_on_screen['top'] + click_y_rel_region
                )
                
                # --- SUPER DEBUGGING ---
                self._log_to_gui("--- DEBUG MATEMÁTICA DO CLIQUE ---")
                self._log_to_gui(f" 1. Ponto Inicial da Região Ecrã : X={search_area_coords_on_screen['left']}, Y={search_area_coords_on_screen['top']}")
                self._log_to_gui(f" 2. Caixa do OCR (Na Região)    : left={text_box_in_region_image['left']}, top={text_box_in_region_image['top']}, w={text_box_in_region_image['width']}, h={text_box_in_region_image['height']}")
                self._log_to_gui(f" 3. Ponto de Clique (Na Região) : x={click_x_rel_region}, y={click_y_rel_region}")
                self._log_to_gui(f" 4. Ponto Final Absoluto no Ecrã: X={coords_on_screen[0]}, Y={coords_on_screen[1]}")
                
                # Desenhar uma mira na imagem para vermos onde o bot ACHA que vai clicar
                if hasattr(self.image_processor, 'debug') and self.image_processor.debug:
                    import cv2
                    import numpy as np
                    try:
                        debug_img_cv = cv2.cvtColor(np.array(region_image_pil), cv2.COLOR_RGB2BGR)
                        cv2.rectangle(debug_img_cv, 
                                     (text_box_in_region_image['left'], text_box_in_region_image['top']), 
                                     (text_box_in_region_image['left'] + text_box_in_region_image['width'], 
                                      text_box_in_region_image['top'] + text_box_in_region_image['height']), 
                                     (0, 255, 0), 2)
                        # Desenha uma MIRA VERMELHA no local exato do clique
                        cv2.drawMarker(debug_img_cv, (click_x_rel_region, click_y_rel_region), (0, 0, 255), markerType=cv2.MARKER_CROSS, markerSize=20, thickness=2)
                        
                        crosshair_path = os.path.join(DEBUG_OUTPUT_DIR, f"debug_crosshair_{time.strftime('%H%M%S')}.png")
                        cv2.imwrite(crosshair_path, debug_img_cv)
                        self._log_to_gui(f" MIRA VISUAL: A imagem com o alvo vermelho foi gravada em: {crosshair_path}")
                    except Exception as e_cross:
                        self._log_to_gui(f" Erro ao desenhar a mira de debug: {e_cross}")
                self._log_to_gui("----------------------------------")
                
                return coords_on_screen
            else:
                self._log_to_gui(f"Texto '{text_to_find}' NÃO encontrado na região '{calibrated_region_name}'.")
                
                if "Latest Resume" in text_to_find:
                    try:
                        all_text = self.image_processor.extract_text(region_image_pil)
                        self._log_to_gui(f"DEBUG - Todo texto encontrado na região:\n{all_text}")
                    except Exception as e_ocr:
                        self._log_to_gui(f"Erro ao tentar OCR completo da região: {e_ocr}")
                return None

        except Exception as e:
            self._log_to_gui(f"Erro ao capturar/processar região '{calibrated_region_name}': {e}")
            traceback.print_exc()
            return None

    def _generate_unique_resume_filename(self, candidate_name):
        safe_name = "".join(c if c.isalnum() else "_" for c in candidate_name[:50])
        unique_id = str(uuid.uuid4().hex)[:8]
        return f"{safe_name}_resume_{unique_id}.pdf"

    def _save_resume_mapping(self, candidate_name, candidate_profile, final_saved_filename, download_directory):
        map_file_path = os.path.join(download_directory, "resume_map.json")
        mapping_data = {}
        if os.path.exists(map_file_path):
            try:
                with open(map_file_path, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
            except Exception:
                mapping_data = {} 
        
        file_key = os.path.basename(final_saved_filename)
        mapping_data[file_key] = {
            "candidate_name": candidate_name,
            "candidate_profile": candidate_profile,
            "saved_on": time.strftime("%Y-%m-%d %H:%M:%S")
        }
        try:
            with open(map_file_path, 'w', encoding='utf-8') as f:
                json.dump(mapping_data, f, indent=4, ensure_ascii=False)
            self._log_to_gui(f"Mapeamento do resumo salvo para '{file_key}' em '{map_file_path}'.")
        except Exception as e:
            self._log_to_gui(f"Erro ao salvar mapeamento do resumo: {e}")

    def _handle_save_as_dialog(self, candidate_name, candidate_profile):
        """
        Lida com a janela de diálogo 'Guardar Como...' do sistema operacional.
        """
        self._log_to_gui("Janela 'Guardar Como...' deve estar aberta. Tentando interagir...")
        time.sleep(1.5)

        # Determinar caminho de salvamento temporário
        download_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "downloaded_resumes")
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        # Gerar um nome de ficheiro seguro e único
        safe_name = "".join([c for c in candidate_name if c.isalpha() or c.isdigit() or c==' ']).rstrip()
        safe_name = safe_name.replace(' ', '_')
        unique_id = uuid.uuid4().hex[:8]
        
        # O Chrome/Linux vai adicionar o .pdf automaticamente no final
        filename_with_ext = f"{safe_name}_resume_{unique_id}"
        
        # O Chrome/Linux vai guardar nesta pasta
        full_path_to_save = os.path.join(download_dir, filename_with_ext)
        
        self._log_to_gui(f"Tentando definir o nome do ficheiro para: '{full_path_to_save}'")

        # Usar pyperclip para copiar o caminho para a área de transferência
        import pyperclip
        pyperclip.copy(full_path_to_save)
        time.sleep(0.5)

        # Colar o caminho na janela de gravação
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.8)
        self._log_to_gui(f"Caminho '{full_path_to_save}' colado.")

        # Guardar - Apenas 1 Enter (Isto grava e seleciona o ficheiro no Linux)
        self._log_to_gui("Pressionando Enter (Gravação)...")
        pyautogui.press('enter')

        # Esperar um pouco mais para garantir que o download termina fisicamente
        self._log_to_gui("Aguardando 3s para o ficheiro ser salvo no disco...")
        time.sleep(3)
        
        return full_path_to_save # Devolve a string do caminho original

    def process_candidate_profile_page(self, candidate_name, candidate_profile, original_window_title=None):
        """Processa a página de perfil do candidato."""
        self._log_to_gui(f"\n=== Processando página de perfil para: {candidate_name} ===")
        time.sleep(2)

        # ======================================================
        # INÍCIO DA VALIDAÇÃO DO INDICATIVO TELEFÓNICO (+351)
        # ======================================================
        self._log_to_gui("A validar indicativo de telefone (+351)...")
        try:
            search_area_coords = self._get_calibrated_region_coords("Área de Busca do 'Latest Resume' (Página do Perfil)")
            region_image_pil = pyautogui.screenshot(region=(
                search_area_coords["left"],
                search_area_coords["top"],
                search_area_coords["width"],
                search_area_coords["height"]
            ))
            
            # Extrair todo o texto da região de cabeçalho
            header_text = self.image_processor.extract_text(region_image_pil)
            
            # Remover espaços e traços para evitar falhas do OCR (ex: "+ 351" ou "+351-")
            clean_header = header_text.replace(" ", "").replace("-", "")
            
            # Se não encontrar "+351" nem "00351", rejeita automaticamente
            if "+351" not in clean_header and "00351" not in clean_header:
                self._log_to_gui("❌ CANDIDATO REJEITADO: Sem indicativo PT (+351) no perfil.")
                self._log_to_gui("Fechando janela do perfil com Alt+F4...")
                pyautogui.hotkey('alt', 'f4')
                time.sleep(1.0)
                return False  # Aborta imediatamente e diz à rotina principal que falhou/rejeitou
            else:
                self._log_to_gui("✅ Indicativo de Portugal detetado. Prosseguindo para o CV...")
        except Exception as e:
            self._log_to_gui(f"⚠️ Erro ao tentar validar telefone: {e}. A prosseguir por segurança...")
        # ======================================================
        # FIM DA VALIDAÇÃO DO INDICATIVO TELEFÓNICO
        # ======================================================

        resume_link_variations = [
            "Latest Resume",
            "LatestResume",
            "Latest_Resume",
            "Latest",
            "Resume",
            "CV",
            "Download"
        ]

        configured_text = self.config.get_setting("resume_link_text", "Latest Resume")
        if configured_text and configured_text not in resume_link_variations:
            resume_link_variations.insert(0, configured_text)

        link_coords = None
        text_found = None

        for attempt, text_variation in enumerate(resume_link_variations, 1):
            self._log_to_gui(f"\nTentativa {attempt}: Procurando por '{text_variation}'")
            
            coords = self._find_text_coords_in_region(
                "Área de Busca do 'Latest Resume' (Página do Perfil)", 
                text_variation
            )
            
            if coords:
                link_coords = coords
                text_found = text_variation
                self._log_to_gui(f"Texto '{text_variation}' encontrado nas coordenadas: {coords}")
                break
            else:
                self._log_to_gui(f"Texto '{text_variation}' não encontrado, tentando próxima variação...")
                time.sleep(0.5)

        if link_coords:
            self._log_to_gui(f"Mapeando o rato lentamente para o alvo {link_coords} para confirmação visual...")
            # Move o rato durante 1.5 segundos para a posição para que os teus olhos possam acompanhar
            pyautogui.moveTo(link_coords[0], link_coords[1], duration=1.5)
            time.sleep(0.5) # Dá meio segundo para veres bem onde o rato parou
            
            self._log_to_gui(f"Clicando com botão direito em '{text_found}'...")
            pyautogui.rightClick(link_coords[0], link_coords[1])
            time.sleep(0.8)

            # Abordagem blindada: Pressionar a letra de atalho do menu "Save link as" ('k')
            self._log_to_gui("Enviando comando para Guardar Link (tecla 'k').")
            pyautogui.press('k')  
            time.sleep(2.0) # Dá tempo extra para a janela de Guardar aparecer e estabilizar

            success = self._handle_save_as_dialog(candidate_name, candidate_profile)
            
            # --- NOVO: Lidar com o caminho devolvido ---
            if isinstance(success, str): # Se for uma string (o caminho), o download funcionou
                self._log_to_gui("Download concluído. Fechando janela do perfil com Alt+F4...")
                pyautogui.hotkey('alt', 'f4')
                time.sleep(1.0)
                self._log_to_gui("=== Processamento do perfil concluído com sucesso ===")
                return success # Devolver o caminho até cá acima
            else:
                self._log_to_gui("Download falhou na etapa final.")
                pyautogui.hotkey('alt', 'f4')
                return False
            # ---------------------------------------------
        else:
            self._log_to_gui("AVISO: Não foi possível encontrar o link do currículo após tentar todas as variações.")

        self._log_to_gui("Tentando fechar a janela do perfil...")
        pyautogui.hotkey('alt', 'f4')
        time.sleep(2)

        self._log_to_gui("=== Processamento do perfil concluído com falhas ===\n")
        return False

    def interact_with_ai_filtered_candidates(self, ai_candidates_to_process, gui_log_callback):
        self.log_gui_callback = gui_log_callback 
        self._log_to_gui(f"Iniciando interação para {len(ai_candidates_to_process)} candidatos da IA.")
        
        if not ai_candidates_to_process: 
            self._log_to_gui("Nenhum candidato da IA para processar.")
            return

        processed_ai_candidate_names = set()
        MAX_SCROLL_ITERATIONS_PER_TARGET = 100 # Limite de segurança interno
        
        try: 
            list_area_coords_on_screen = self._get_calibrated_region_coords("Lista de Candidatos")
        except ValueError as e: 
            self._log_to_gui(f"ERRO CRÍTICO (Interação): {e}")
            return
        
        name_sub_region_calib, profile_sub_region_calib = None, None
        try: 
            name_sub_region_calib = self._get_calibrated_region_coords("Nome (Dentro da Célula)_rel_to_cell")
        except ValueError: 
            self._log_to_gui("ERRO CRÍTICO (Interação): Calibração do Nome ausente.")
            return
        try: 
            profile_sub_region_calib = self._get_calibrated_region_coords("Perfil (Dentro da Célula)_rel_to_cell")
        except ValueError: 
            self._log_to_gui("AVISO BOT (Interação): Calibração do Perfil ausente.")

        original_active_window = None
        if gw:
            try: 
                original_active_window = gw.getActiveWindow()
            except Exception: 
                pass

        for target_candidate_info in ai_candidates_to_process:
            target_name = target_candidate_info.get("name", "").strip()
            target_profile = target_candidate_info.get("profile", "").strip()
            
            if not target_name or target_name in processed_ai_candidate_names: 
                continue

            self._log_to_gui(f"--- Procurando por: {target_name} ---")
            found_and_opened_current_target = False
            current_scroll_iteration = 0
            consecutive_iterations_without_finding_target_hint = 0
            MAX_CONSECUTIVE_NO_HINT = 3

            while current_scroll_iteration < MAX_SCROLL_ITERATIONS_PER_TARGET:
                current_scroll_iteration += 1
                
                current_list_image_pil = self.capture_region_pil("Lista de Candidatos")
                if hasattr(self.image_processor, 'debug') and self.image_processor.debug:
                    try: 
                        os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                        current_list_image_pil.save(os.path.join(DEBUG_OUTPUT_DIR, f"debug_interact_target_{''.join(c if c.isalnum() else '_' for c in target_name[:15])}_scroll_iter_{current_scroll_iteration}.png"))
                    except Exception: 
                        pass
                
                cells_with_circles = self.image_processor.identify_candidate_cells_by_profile_circles(current_list_image_pil)

                if not cells_with_circles and current_scroll_iteration > 1: 
                    consecutive_iterations_without_finding_target_hint += 1
                elif cells_with_circles: 
                    consecutive_iterations_without_finding_target_hint = 0
                
                candidate_found_in_this_view = False
                for i, (cell_region_in_list_image, circle_info_in_list_image) in enumerate(cells_with_circles):
                    x_cell, y_cell, w_cell, h_cell = cell_region_in_list_image
                    try:
                        individual_cell_image_pil = current_list_image_pil.crop((x_cell, y_cell, x_cell + w_cell, y_cell + h_cell))
                        cell_processing_result = self._process_individual_cell(
                            individual_cell_image_pil, 
                            circle_info_in_list_image, 
                            x_cell, y_cell, 
                            name_sub_region_calib, 
                            profile_sub_region_calib
                        )

                        if cell_processing_result and cell_processing_result['extracted_data']:
                            page_candidate_data = cell_processing_result['extracted_data']
                            name_click_center_rel_to_cell = cell_processing_result['name_precise_click_center_rel_to_cell'] 

                            if page_candidate_data.get("name"):
                                page_candidate_name = page_candidate_data["name"].strip()
                                if name_click_center_rel_to_cell: 
                                    self._log_to_gui(f"Célula {i+1}: Nome='{page_candidate_name}', CliqueRel='{name_click_center_rel_to_cell}'")

                                if page_candidate_name.lower() == target_name.lower():
                                    self._log_to_gui(f"ALVO ENCONTRADO: {target_name}!")
                                    candidate_found_in_this_view = True
                                    if name_click_center_rel_to_cell:
                                        name_link_x_on_screen = list_area_coords_on_screen["left"] + x_cell + name_click_center_rel_to_cell[0]
                                        name_link_y_on_screen = list_area_coords_on_screen["top"] + y_cell + name_click_center_rel_to_cell[1]
                                        
                                        active_window_before_click = None
                                        if gw:
                                            try: 
                                                active_window_before_click = gw.getActiveWindow()
                                            except Exception: 
                                                pass
                                        try:
                                            pyautogui.keyDown('shift')
                                            time.sleep(0.1)
                                            pyautogui.click(name_link_x_on_screen, name_link_y_on_screen)
                                            time.sleep(0.1)
                                            pyautogui.keyUp('shift')
                                            self._log_to_gui(f"Shift+Click executado em {target_name}.")
                                            time.sleep(self.config.get_setting("page_load_delay_sec", 7))
                                            self._log_to_gui(f"Nova janela para {target_name} presumivelmente aberta.")
                                            
                                            original_title_for_profile = active_window_before_click.title if active_window_before_click else None
                                            self.process_candidate_profile_page(target_name, target_profile, original_title_for_profile) 
                                            
                                            if original_active_window:
                                                try: 
                                                    original_active_window.activate()
                                                    time.sleep(0.5)
                                                except Exception: 
                                                    pass
                                            elif active_window_before_click:
                                                try: 
                                                    active_window_before_click.activate()
                                                    time.sleep(0.5)
                                                except Exception: 
                                                    pass
                                        except Exception as e_shift_click: 
                                            self._log_to_gui(f"ERRO durante Shift+Click: {e_shift_click}")
                                        
                                        processed_ai_candidate_names.add(target_name)
                                        found_and_opened_current_target = True
                                        break 
                                    else: 
                                        self._log_to_gui(f"AVISO: Alvo {target_name} encontrado, mas sem coordenadas de clique PRECISAS.")
                    except Exception as e_cell_proc: 
                        self._log_to_gui(f"Erro ao processar célula {i+1}: {e_cell_proc}")
                
                if found_and_opened_current_target: 
                    break 
                if consecutive_iterations_without_finding_target_hint >= MAX_CONSECUTIVE_NO_HINT: 
                    break 
                if current_scroll_iteration >= MAX_SCROLL_ITERATIONS_PER_TARGET: 
                    break 
                
                scroll_point_x_abs = list_area_coords_on_screen["left"] + list_area_coords_on_screen["width"] // 2
                scroll_point_y_abs = list_area_coords_on_screen["top"] + list_area_coords_on_screen["height"] // 2
                scroll_amount_pixels = int(list_area_coords_on_screen["height"] * 0.8)
                # No Linux, converte pixeis para ticks da roda do rato (assumindo ~50px por tick)
                ticks_de_scroll = int(scroll_amount_pixels / 50)
                scroll_pyautogui_val = -max(1, ticks_de_scroll)  # Garante pelo menos 1 tick para baixo
                
                pyautogui.moveTo(scroll_point_x_abs, scroll_point_y_abs, duration=0.1)
                time.sleep(0.2)
                pyautogui.scroll(scroll_pyautogui_val)
                time.sleep(self.scroll_interval) 
            
            if not found_and_opened_current_target: 
                self._log_to_gui(f"AVISO: {target_name} não foi encontrado após todos os scrolls.")
        
        self._log_to_gui("Processo de interação com perfis da IA finalizado.")
        self.log_gui_callback = None
