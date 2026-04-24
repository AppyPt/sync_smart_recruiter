# image_processor.py
import cv2
import numpy as np
import pytesseract
from PIL import Image
import os
import traceback
import pandas as pd # Adicionado para processar o output de image_to_data, se necessário

DEBUG_OUTPUT_DIR = "debug_files"

class ImageProcessor:
    def __init__(self, tesseract_path=None):
        self.debug = False
        
        # Configurações padrão (mais conservadoras)
        self.clahe_enabled = True
        self.clahe_clip_limit = 2.0
        
        self.adaptive_block_size = 11
        self.adaptive_c = 2
        
        self.blur_enabled = False
        self.blur_kernel_size = 3
        
        self.morph_open_enabled = False
        self.morph_close_enabled = False
        self.morph_kernel_size = 3
        
        self.zoom_factor = 1.5
        
        # Configuração do Tesseract
        if tesseract_path:
            tesseract_path_fmt = r"{}".format(tesseract_path)
            pytesseract.pytesseract.tesseract_cmd = tesseract_path_fmt
            
            # Verificar e configurar TESSDATA_PREFIX
            tessdata_dir = os.path.join(os.path.dirname(tesseract_path_fmt), "tessdata")
            if os.path.exists(tessdata_dir):
                os.environ["TESSDATA_PREFIX"] = tessdata_dir
                print(f"IP: TESSDATA_PREFIX configurado para: {tessdata_dir}")
            else:
                print(f"AVISO IP: Diretório tessdata não encontrado em: {tessdata_dir}")
            
            # Verificar arquivos de idioma
            required_files = ["por.traineddata", "por_best.traineddata", "eng.traineddata"]
            missing_files = []
            for file in required_files:
                file_path = os.path.join(tessdata_dir, file)
                if not os.path.exists(file_path):
                    missing_files.append(file)
            
            if missing_files:
                print(f"AVISO IP: Arquivos de idioma faltando: {', '.join(missing_files)}")
                print("Por favor, baixe os arquivos de https://github.com/tesseract-ocr/tessdata")
        else:
            try:
                pass  # Add your code here
            except Exception as e:
                print(f"An error occurred: {e}")
                pass  # Add your code here
            except Exception as e:
                print(f"An error occurred: {e}")
                pytesseract.get_tesseract_version()
            except pytesseract.TesseractNotFoundError:
                print("AVISO IP: Caminho do Tesseract não fornecido e Tesseract não encontrado no PATH.")

    def _preprocess_for_ocr(self, image_input_cv_bgr):
        """
        Preprocesses an image for OCR using a configurable set of techniques, including optional zoom.
        
        Args:
            image_input_cv_bgr: OpenCV BGR image
            
        Returns:
            Preprocessed binary image optimized for OCR
        """
        gray = cv2.cvtColor(image_input_cv_bgr, cv2.COLOR_BGR2GRAY)
        
        # 0. Zoom (opcional)
        if self.zoom_factor > 1.0:
            width = int(gray.shape[1] * self.zoom_factor)
            height = int(gray.shape[0] * self.zoom_factor)
            dim = (width, height)
            gray = cv2.resize(gray, dim, interpolation=cv2.INTER_CUBIC)
        
        # 1. Contraste adaptativo (CLAHE)
        if self.clahe_enabled:
            clahe = cv2.createCLAHE(clipLimit=self.clahe_clip_limit, tileGridSize=(8,8))
            gray = clahe.apply(gray)
        
        # 2. Thresholding adaptativo
        binary = cv2.adaptiveThreshold(
            gray, 
            255, 
            cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY, 
            self.adaptive_block_size,
            self.adaptive_c
        )
        
        # 2.5. Thresholding de Otsu (adicionado)
        _, binary_otsu = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        # Compare com o adaptativo e escolha o melhor (por média de branco/preto ou visualmente em debug)
        
        # 3. Remoção de ruído (blur)
        if self.blur_enabled:
            binary = cv2.medianBlur(binary, self.blur_kernel_size)
        
        # 4. Dilatação/Erosão
        kernel = np.ones((self.morph_kernel_size, self.morph_kernel_size), np.uint8)
        if self.morph_open_enabled:
            binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
        if self.morph_close_enabled:
            binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, kernel)
        
        # Debug
        if self.debug:
            try:
                os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, "debug_ocr_preprocess_1_gray.png"), gray)
                cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, "debug_ocr_preprocess_2_binary.png"), binary)
                print("IP: Saved debug images for OCR preprocessing steps")
            except Exception as e:
                pass
                print(f"ERRO IP na identificação de células por círculos: {e}")
                traceback.print_exc()
                return []
                print(f"ERRO IP ao salvar imagens de debug do pré-processamento: {e}")
        
        return binary

    def _preprocess_for_line_detection(self, image_pil):
        """Prepara a imagem PIL para deteção de linhas, retornando a imagem de bordas."""
        open_cv_image_bgr = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(open_cv_image_bgr, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        sobel_horizontal = cv2.Sobel(blurred, cv2.CV_64F, 0, 1, ksize=3)
        sobel_horizontal = cv2.convertScaleAbs(sobel_horizontal)
        _, binary = cv2.threshold(sobel_horizontal, 50, 255, cv2.THRESH_BINARY)
        
        if self.debug:
            os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
            cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, "debug_line_detection_01_edges.png"), binary)
            print("IP: Imagem de bordas (Sobel + Threshold) para deteção de linhas salva.")
        return binary

    def identify_candidate_cells_by_lines(self, image_pil,
                                          hough_threshold=50,
                                          hough_min_line_length_ratio=0.6,
                                          hough_max_line_gap=25,
                                          angle_tolerance_degrees=3,
                                          line_grouping_y_threshold=10,
                                          min_cell_height_px=40):
        # (Código deste método permanece como no ficheiro [16] fornecido)
        # ... (Implementação completa como no ficheiro original) ...
        try:
            print("\n--- IP: INÍCIO DA IDENTIFICAÇÃO DE CÉLULAS POR LINHAS HORIZONTAIS ---")
            if not isinstance(image_pil, Image.Image):
                print("ERRO IP: identify_candidate_cells_by_lines espera uma imagem PIL.")
                return []

            img_width, img_height = image_pil.size
            print(f"IP: Dimensões da imagem da lista (PIL): {img_width}x{img_height}")

            edges_for_hough = self._preprocess_for_line_detection(image_pil)

            actual_min_line_length = int(img_width * hough_min_line_length_ratio)
            print(f"IP: HoughLinesP params: threshold={hough_threshold}, minLineLength={actual_min_line_length}, maxLineGap={hough_max_line_gap}")

            lines = cv2.HoughLinesP(
                edges_for_hough, rho=1, theta=np.pi / 180, threshold=30,
                minLineLength=int(img_width * 0.5), maxLineGap=20
            )

            detected_horizontal_lines_y = []
            debug_lines_img = None
            if self.debug:
                os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                debug_lines_img = cv2.cvtColor(np.array(image_pil.copy()), cv2.COLOR_RGB2BGR)

            if lines is not None:
                print(f"IP: {len(lines)} linhas detetadas inicialmente por HoughLinesP.")
                for line_segment in lines:
                    x1, y1, x2, y2 = line_segment[0]
                    angle_rad = np.arctan2(y2 - y1, x2 - x1)
                    angle_deg = np.degrees(angle_rad)
                    
                    if abs(angle_deg) <= angle_tolerance_degrees:
                        avg_y = (y1 + y2) // 2
                        detected_horizontal_lines_y.append(avg_y)
                        if self.debug and debug_lines_img is not None:
                            cv2.line(debug_lines_img, (x1, y1), (x2, y2), (0, 0, 255), 1)
                if self.debug and debug_lines_img is not None:
                    cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, "debug_line_detection_02_hough_lines.png"), debug_lines_img)
                    print("IP: Imagem com linhas candidatas de Hough salva.")
            else:
                print("IP: Nenhuma linha detetada por HoughLinesP.")

            if not detected_horizontal_lines_y:
                print("IP: Nenhuma linha horizontal significativa filtrada.")
                return []

            detected_horizontal_lines_y.sort()
            unique_y_separators = []
            if detected_horizontal_lines_y:
                current_group = [detected_horizontal_lines_y[0]]
                for y_coord in detected_horizontal_lines_y[1:]:
                    if y_coord - current_group[-1] <= line_grouping_y_threshold:
                        current_group.append(y_coord)
                    else:
                        unique_y_separators.append(int(np.mean(current_group)))
                        current_group = [y_coord]
                unique_y_separators.append(int(np.mean(current_group)))

            print(f"IP: Coordenadas Y únicas dos separadores horizontais: {unique_y_separators}")

            if not unique_y_separators:
                print("IP: Nenhuma linha separadora única encontrada após agrupamento.")
                return []

            cell_boundaries_y = sorted(list(set([0] + unique_y_separators + [img_height])))
            
            final_boundaries_y = []
            if cell_boundaries_y:
                final_boundaries_y.append(cell_boundaries_y[0])
                for y_b in cell_boundaries_y[1:]:
                    if (y_b - final_boundaries_y[-1] > line_grouping_y_threshold / 2) and \
                       not (final_boundaries_y[-1] == img_height and y_b == img_height):
                        final_boundaries_y.append(y_b)
            if final_boundaries_y and final_boundaries_y[-1] < img_height and \
               (img_height - final_boundaries_y[-1] > line_grouping_y_threshold / 2):
                final_boundaries_y.append(img_height)
            elif final_boundaries_y and final_boundaries_y[-1] > img_height :
                 final_boundaries_y[-1] = img_height

            print(f"IP: Delimitadores Y finais para células (incluindo topo/fundo): {final_boundaries_y}")

            regions = []
            for i in range(len(final_boundaries_y) - 1):
                y_start = final_boundaries_y[i]
                y_end = final_boundaries_y[i+1]
                cell_h = y_end - y_start
                
                if cell_h >= min_cell_height_px:
                    region = (0, y_start, img_width, cell_h)
                    regions.append(region)
                    print(f"IP: Célula por Linhas #{i+1} identificada: x={region[0]}, y={region[1]}, w={region[2]}, h={region[3]}")
                else:
                    print(f"IP: Célula potencial entre y={y_start} e y={y_end} ignorada (altura {cell_h}px < {min_cell_height_px}px).")

            if self.debug:
                os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                debug_final_cells_img = cv2.cvtColor(np.array(image_pil.copy()), cv2.COLOR_RGB2BGR)
                for i, (x_r, y_r, w_r, h_r) in enumerate(regions):
                    cv2.rectangle(debug_final_cells_img, (x_r, y_r), (x_r + w_r, y_r + h_r), (0, 255, 0), 2) 
                    cv2.putText(debug_final_cells_img, f"LC{i+1}", (x_r + 5, y_r + 20), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                if final_boundaries_y: # Adicionado para evitar erro se final_boundaries_y estiver vazio
                    for y_b_line in final_boundaries_y:
                        cv2.line(debug_final_cells_img, (0, y_b_line), (img_width, y_b_line), (255, 0, 0), 1) 
                cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, "debug_line_detection_03_final_cells.png"), debug_final_cells_img)
                print("IP: Imagem 'debug_line_detection_03_final_cells.png' salva.")

            print(f"IP: Total: {len(regions)} células de candidatos identificadas por linhas.")
            print("--- IP: FIM DA IDENTIFICAÇÃO DE CÉLULAS POR LINHAS HORIZONTAIS ---\n")
            return regions

        except Exception as e:
            print(f"ERRO IP na identificação de células por linhas: {e}")
            traceback.print_exc()
            return []
        pass

    def extract_text(self, image_to_ocr_pil, region_in_image_to_ocr=None):
        try:
            if not isinstance(image_to_ocr_pil, Image.Image):
                print("ERRO IP: extract_text espera uma imagem PIL.")
                return ""

            target_pil_image = image_to_ocr_pil
            if region_in_image_to_ocr:
                x, y, w, h = region_in_image_to_ocr
                img_w, img_h = target_pil_image.size
                crop_x1 = max(0, x)
                crop_y1 = max(0, y)
                crop_x2 = min(img_w, x + w)
                crop_y2 = min(img_h, y + h)
                if crop_x2 <= crop_x1 or crop_y2 <= crop_y1:
                    print(f"  AVISO IP: Sub-região inválida ou fora dos limites da célula: ({x},{y},{w},{h}) na célula de {img_w}x{img_h}. OCR da célula inteira será tentado.")
                else:
                    target_pil_image = target_pil_image.crop((crop_x1, crop_y1, crop_x2, crop_y2))

            cv_bgr_for_preprocess = cv2.cvtColor(np.array(target_pil_image), cv2.COLOR_RGB2BGR)
            preprocessed_cv_img = self._preprocess_for_ocr(cv_bgr_for_preprocess)
            
            # Converter imagem preprocessada de CV2 para PIL
            preprocessed_pil = Image.fromarray(preprocessed_cv_img)
            
            debug_filename_base = "debug_ocr_input_full_cell.png"
            if self.debug:
                try:
                    os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                    if region_in_image_to_ocr:
                        debug_filename_base = f"debug_ocr_input_sub_region_x{region_in_image_to_ocr[0]}_y{region_in_image_to_ocr[1]}_w{region_in_image_to_ocr[2]}_h{region_in_image_to_ocr[3]}.png"
                    
                    debug_file_path = os.path.join(DEBUG_OUTPUT_DIR, debug_filename_base)
                    cv2.imwrite(debug_file_path, preprocessed_cv_img)
                    print(f"IP: Imagem de input do OCR salva: {debug_file_path}")
                except Exception as e_save:
                    print(f"ERRO IP ao salvar imagem de debug do OCR: {e_save}")

            # Configuração do OCR
            custom_config = (
                '--oem 3 '
                '--psm 7 '
                '-l por+por_best+eng '  # Changed to include Portuguese
                '-c preserve_interword_spaces=1 '
                '-c language_model_penalty_non_dict_word=0.8 '
                '-c language_model_penalty_non_freq_dict_word=0.8'
            )

            text = pytesseract.image_to_string(
                preprocessed_pil,
                config=custom_config
            )

            # Se não encontrou nada com inglês, tenta com português
            if not text.strip():
                if os.path.exists(os.path.join(os.getenv("TESSDATA_PREFIX", ""), "por.traineddata")):
                    custom_config = custom_config.replace("-l eng", "-l por+por_best+eng")
                    text = pytesseract.image_to_string(
                        preprocessed_pil,
                        config=custom_config
                    )

            clean_text = text.strip().replace('\n', ' | ')
            preview = clean_text[:100] + ('...' if len(clean_text) > 100 else '')
            log_prefix = "  IP: OCR da célula inteira:"
            if region_in_image_to_ocr:
                log_prefix = f"  IP: OCR da sub-região ({region_in_image_to_ocr[0]},{region_in_image_to_ocr[1]}):"
            print(f"{log_prefix} [{preview}]")

            return clean_text

        except Exception as e:
            print(f"ERRO IP durante OCR: {e}")
            traceback.print_exc()
            return ""
        pass

    def get_text_bounding_box(self, image_pil_region, target_text_sequence, lang='por+eng'):
        """
        Finds the bounding box for a target text sequence within an image.
        """
        if not image_pil_region or not target_text_sequence:
            print(f"IP (get_text_bounding_box): Entrada inválida. Imagem: {image_pil_region is not None}, Texto Alvo: '{target_text_sequence}'")
            return None

        try:
            # Salvar imagem original para debug
            debug_prefix = "debug_latest_resume" if "Latest Resume" in target_text_sequence else "debug_text_search"
            if self.debug:
                try:
                    os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                    original_image_path = os.path.join(DEBUG_OUTPUT_DIR, f"{debug_prefix}_original.png")
                    image_pil_region.save(original_image_path)
                    print(f"IP (get_text_bounding_box): Imagem original salva em: {original_image_path}")
                except Exception as e_save:
                    print(f"ERRO IP ao salvar imagem original: {e_save}")

            # Pré-processamento
            cv_bgr_for_preprocess = cv2.cvtColor(np.array(image_pil_region), cv2.COLOR_RGB2BGR)
            preprocessed_cv_img = self._preprocess_for_ocr(cv_bgr_for_preprocess)

            # Salvar imagem pré-processada para debug
            if self.debug:
                try:
                    preprocessed_image_path = os.path.join(DEBUG_OUTPUT_DIR, f"{debug_prefix}_preprocessed.png")
                    cv2.imwrite(preprocessed_image_path, preprocessed_cv_img)
                    print(f"IP (get_text_bounding_box): Imagem pré-processada salva em: {preprocessed_image_path}")
                except Exception as e_save:
                    print(f"ERRO IP ao salvar imagem pré-processada: {e_save}")

            # Lista de configurações PSM para tentar
            psm_configs = [
                ('--psm 6', 'Bloco uniforme de texto'),
                ('--psm 7', 'Linha única de texto'),
                ('--psm 3', 'Auto-paginação'),
                ('--psm 11', 'Texto esparso'),
            ]

            best_result = None
            best_confidence = 0

            print(f"\nIP (get_text_bounding_box): Iniciando busca por '{target_text_sequence}' com múltiplas configurações PSM")
            
            for psm_config, psm_desc in psm_configs:
                print(f"\n--- Tentando com {psm_config} ({psm_desc}) ---")
                
                custom_config = f'--oem 3 {psm_config}'
                ocr_data = pytesseract.image_to_data(
                    preprocessed_cv_img, 
                    lang=lang,
                    config=custom_config,
                    output_type=pytesseract.Output.DICT
                )

                # Debug: Mostrar todas as palavras detectadas com este PSM
                print(f"Palavras detectadas com {psm_config}:")
                detected_words = []
                for i in range(len(ocr_data['text'])):
                    if int(ocr_data['level'][i]) == 5:  # Nível de palavra
                        word = ocr_data['text'][i].strip()
                        conf = int(ocr_data['conf'][i])
                        if word and conf > 0:
                            detected_words.append(word)
                            print(f"  Palavra: '{word}' | Confiança: {conf}% | Pos: ({ocr_data['left'][i]}, {ocr_data['top'][i]}) | Tam: {ocr_data['width'][i]}x{ocr_data['height'][i]}")

                # Juntar palavras detectadas e comparar com o alvo
                detected_text = ' '.join(detected_words)
                target_text = target_text_sequence.lower()
                
                # Encontrar todas as palavras que são parte da sequência alvo
                found_words = []
                total_conf = 0
                
                for i in range(len(ocr_data['text'])):
                    if int(ocr_data['level'][i]) == 5:  # Nível de palavra
                        ocr_word = ocr_data['text'][i].strip()
                        if not ocr_word:
                            continue
                            
                        conf = int(ocr_data['conf'][i])
                        
                        # Verificar se esta palavra é parte da sequência alvo
                        if (ocr_word.lower() in target_text or 
                            any(w.lower() in target_text for w in ocr_word.split()) or
                            any(ocr_word.lower() in t.lower() for t in target_text_sequence.split())):
                        
                            found_words.append({
                                'text': ocr_word,
                                'left': int(ocr_data['left'][i]),
                                'top': int(ocr_data['top'][i]),
                                'width': int(ocr_data['width'][i]),
                                'height': int(ocr_data['height'][i]),
                                'conf': conf
                            })
                            total_conf += conf

                if found_words:
                    avg_conf = total_conf / len(found_words)
                    print(f"Palavras encontradas com {psm_config}: {[w['text'] for w in found_words]} (Confiança média: {avg_conf:.1f}%)")
                    
                    if avg_conf > best_confidence:
                        best_confidence = avg_conf
                        
                        # Calcular bounding box combinado
                        min_x = min(word['left'] for word in found_words)
                        min_y = min(word['top'] for word in found_words)
                        max_x = max(word['left'] + word['width'] for word in found_words)
                        max_y = max(word['top'] + word['height'] for word in found_words)
                        
                        best_result = {
                            'left': min_x,
                            'top': min_y,
                            'width': max_x - min_x,
                            'height': max_y - min_y,
                            'conf': avg_conf,
                            'psm_used': psm_config
                        }

            if best_result:
                print(f"\nIP (get_text_bounding_box): Melhor resultado encontrado usando {best_result['psm_used']}")
                print(f"Bounding box: {best_result}")
                print(f"Confiança: {best_result['conf']:.1f}%")

                # Desenhar bounding box na imagem original para debug
                if self.debug:
                    try:
                        debug_img_with_box = cv2.cvtColor(np.array(image_pil_region.copy()), cv2.COLOR_RGB2BGR)
                        cv2.rectangle(
                            debug_img_with_box,
                            (best_result['left'], best_result['top']),
                            (best_result['left'] + best_result['width'], best_result['top'] + best_result['height']),
                            (0, 255, 0),
                            2
                        )
                        box_image_path = os.path.join(DEBUG_OUTPUT_DIR, f"{debug_prefix}_with_box.png")
                        cv2.imwrite(box_image_path, debug_img_with_box)
                        print(f"IP (get_text_bounding_box): Imagem com bounding box salva em: {box_image_path}")
                    except Exception as e_box:
                        print(f"ERRO IP ao salvar imagem com bounding box: {e_box}")

                return best_result
            else:
                print("\nIP (get_text_bounding_box): Nenhum resultado satisfatório encontrado com nenhuma configuração PSM")
                
                # Tentar OCR simples para debug
                print("\nTentando OCR simples na região completa:")
                try:
                    simple_text = pytesseract.image_to_string(preprocessed_cv_img, lang=lang)
                    print(f"Texto completo encontrado:\n{simple_text}")
                except Exception as e_simple:
                    print(f"ERRO IP ao tentar OCR simples: {e_simple}")
                return None

        except Exception as e:
            print(f"ERRO IP (get_text_bounding_box) para '{target_text_sequence}': {e}")
            traceback.print_exc()
            return None

        
    def compare_images(self, img1_pil, img2_pil, threshold=1000):
        """
        Compares two PIL images and returns True if they are different enough.
        """
        if not isinstance(img1_pil, Image.Image) or not isinstance(img2_pil, Image.Image):
            print("ERRO IP: compare_images espera duas imagens PIL.")
            return True 

        img1_np = np.array(img1_pil.convert('L')) 
        img2_np = np.array(img2_pil.convert('L'))
        
        if img1_np.shape != img2_np.shape:
            h1, w1 = img1_np.shape
            h2, w2 = img2_np.shape
            if h1*w1 < h2*w2:
                img1_np = cv2.resize(img1_np, (w2, h2), interpolation=cv2.INTER_AREA)
            elif h2*w2 < h1*w1:
                img2_np = cv2.resize(img2_np, (w1, h1), interpolation=cv2.INTER_AREA)
            print(f"AVISO IP: Imagens para comparação com tamanhos diferentes. Tentativa de redimensionamento. Original1: {h1}x{w1}, Original2: {h2}x{w2}")

        diff = cv2.absdiff(img1_np, img2_np)
        diff_score = np.sum(diff)
        
        print(f"IP: Comparação de imagens: Pontuação de diferença = {diff_score} (Limiar = {threshold})")
        return diff_score > threshold

    def set_tesseract_path(self, tesseract_path):
        # (Código deste método permanece como no ficheiro [16] fornecido)
        # ... (Implementação completa como no ficheiro original) ...
        if tesseract_path:
            tesseract_path_fmt = r"{}".format(tesseract_path)
            pytesseract.pytesseract.tesseract_cmd = tesseract_path_fmt
            print(f"IP: Caminho do Tesseract atualizado para: {tesseract_path_fmt}")
            
            if not os.path.exists(tesseract_path_fmt):
                print(f"AVISO IP: Arquivo Tesseract não encontrado em: {tesseract_path_fmt}")
                return False
            try:
                pytesseract.get_tesseract_version()
                print("IP: Tesseract OCR funcional com o novo caminho.")
                return True
            except pytesseract.TesseractNotFoundError:
                print(f"ERRO IP: Tesseract não encontrado ou não funcional com o caminho: {tesseract_path_fmt}")
                return False
        return False


    def identify_candidate_cells_by_profile_circles(self, image_pil,
                                                min_circle_radius=20,
                                                max_circle_radius=40,
                                                hough_dp=1.2,
                                                hough_min_dist_ratio=0.2,
                                                hough_param1=30,  # <-- BAIXAMOS de 60 para 30 (Vê melhor cores claras/pastel)
                                                hough_param2=18,  # <-- BAIXAMOS de 35 para 18 (Aceita círculos imperfeitos/com fotos)
                                                circle_filter_max_x_ratio=0.25,
                                                cell_y_offset_from_circle_center=-45,
                                                min_cell_height=50):
        """Identifies candidate cells in an image based on profile circles."""
        try:
            print("\n--- IP: INÍCIO DA IDENTIFICAÇÃO DE CÉLULAS POR CÍRCULOS DE PERFIL ---")

            if not isinstance(image_pil, Image.Image):
                print("ERRO IP: identify_candidate_cells_by_profile_circles espera uma imagem PIL.")
                return []

            open_cv_image = cv2.cvtColor(np.array(image_pil), cv2.COLOR_RGB2BGR)
            img_height, img_width = open_cv_image.shape[:2]
            
            gray = cv2.cvtColor(open_cv_image, cv2.COLOR_BGR2GRAY)
            blurred = cv2.medianBlur(gray, 5) 
            
            actual_min_dist = int(img_height * hough_min_dist_ratio)
            actual_min_dist = max(actual_min_dist, 30) 

            print(f"IP: HoughCircles params: dp={hough_dp}, minDist={actual_min_dist}, param1={hough_param1}, param2={hough_param2}, minR={min_circle_radius}, maxR={max_circle_radius}")

            circles = cv2.HoughCircles(
                blurred, cv2.HOUGH_GRADIENT,
                dp=hough_dp, minDist=actual_min_dist, 
                param1=hough_param1, param2=hough_param2,   
                minRadius=min_circle_radius, maxRadius=max_circle_radius
            )
            
            debug_img_circles = None
            if self.debug:
                debug_img_circles = open_cv_image.copy() 
            
            detected_circles_info = [] 
            if circles is not None:
                circles_int = np.round(circles).astype(int)
                print(f"IP: Detetados {len(circles_int[0])} círculos potenciais por Hough.")
                
                for c_data in circles_int[0, :]:
                    center_x = int(c_data[0]) 
                    center_y = int(c_data[1])
                    radius = int(c_data[2])
                    
                    if center_x > img_width * circle_filter_max_x_ratio: 
                        continue
                    
                    detected_circles_info.append({
                        'center_x_abs': center_x, 
                        'center_y_abs': center_y, 
                        'radius': radius
                    })

            # Add border circle filtering
            border_margin = max(min_circle_radius * 1.5, 30)  # Safety margin
            filtered_circles = []
            
            print(f"\nIP: Filtrando círculos próximos às bordas (margem: {border_margin}px)...")
            
            for circle_info in detected_circles_info:
                cx = circle_info['center_x_abs']
                cy = circle_info['center_y_abs']
                radius = circle_info['radius']
                
                # Check if circle is fully inside image with margin
                if (cx - radius > border_margin and 
                    cy - radius > border_margin and
                    cx + radius < img_width - border_margin and
                    cy + radius < img_height - border_margin):
                    filtered_circles.append(circle_info)
                else:
                    print(f"IP: Círculo em ({cx},{cy}) ignorado por estar muito próximo à borda.")
            
            print(f"IP: {len(detected_circles_info) - len(filtered_circles)} círculos removidos por proximidade às bordas.")
            detected_circles_info = filtered_circles
            
            # Ordenar os círculos de cima para baixo (pelo eixo Y)
            detected_circles_info.sort(key=lambda c: c['center_y_abs'])
            
            # ---> NOVA TÉCNICA: Filtro de Eixo Vertical (Rejeitar Alucinações) <---
            if detected_circles_info:
                import statistics
                # Extrair todos os eixos X
                x_coords = [c['center_x_abs'] for c in detected_circles_info]
                # A mediana ignora os outliers (círculos falsos) e encontra a coluna real
                median_x = statistics.median(x_coords)
                
                aligned_circles = []
                for c in detected_circles_info:
                    # Só aceita círculos que estejam a +/- 15 pixeis da coluna central
                    if abs(c['center_x_abs'] - median_x) <= 15:
                        aligned_circles.append(c)
                    else:
                        print(f"IP: Círculo FALSO rejeitado em ({c['center_x_abs']}, {c['center_y_abs']}) - Fora do eixo X.")
                
                detected_circles_info = aligned_circles
                
            if self.debug and debug_img_circles is not None:
                try:
                    # Draw border margins for visualization
                    cv2.rectangle(
                        debug_img_circles,
                        (int(border_margin), int(border_margin)),
                        (int(img_width - border_margin), int(img_height - border_margin)),
                        (0, 255, 255),  # Yellow color for margin visualization
                        2
                    )
                except Exception as e:
                    print(f"ERRO IP na identificação de células por círculos de perfil: {e}")
                    traceback.print_exc()
                    return []

            # Calculate cell regions based on circle positions
            candidate_cells = []
            for circle_info in detected_circles_info:
                center_x = circle_info['center_x_abs']
                center_y = circle_info['center_y_abs']
                radius = circle_info['radius']

                # Calculate cell boundaries
                cell_x = 0
                cell_y = center_y + cell_y_offset_from_circle_center
                cell_width = img_width
                
                # Aumentamos a altura da célula para não cortar a Data (que está mais abaixo)
                cell_height = max(160, int(radius * 6.0))

                # Create cell region tuple
                cell_region = (cell_x, cell_y, cell_width, cell_height)
                candidate_cells.append((cell_region, circle_info))

                if self.debug and debug_img_circles is not None:
                    cv2.rectangle(
                        debug_img_circles,
                        (cell_x, cell_y),
                        (cell_x + cell_width, cell_y + cell_height),
                        (0, 255, 0),
                        2
                    )
                    cv2.circle(
                        debug_img_circles,
                        (center_x, center_y),
                        radius,
                        (255, 0, 0),
                        2
                    )

            if self.debug and debug_img_circles is not None:
                os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
                cv2.imwrite(os.path.join(DEBUG_OUTPUT_DIR, "debug_circles_03_candidate_cells.png"), debug_img_circles)
                print("IP: Imagem com círculos e células candidatas salva.")

            print(f"IP: Total: {len(candidate_cells)} células de candidatos identificadas por círculos.")
            print("--- IP: FIM DA IDENTIFICAÇÃO DE CÉLULAS POR CÍRCULOS DE PERFIL ---\n")
            return candidate_cells

        except Exception as e:
            print(f"ERRO IP na identificação de células por círculos de perfil: {e}")
            traceback.print_exc()
            return []


