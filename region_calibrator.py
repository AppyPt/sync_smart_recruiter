# region_calibrator.py
import cv2
import numpy as np
import pyautogui
import tkinter as tk
from tkinter import ttk, messagebox # Adicionado messagebox
from PIL import Image, ImageTk
import time
import json 
import os

DEBUG_OUTPUT_DIR = "debug_files" # Consistência

class RegionCalibrator:
    def __init__(self, root=None):
        self.root = root or tk.Tk()
        self.root.title("SmartRecruiters Region Calibrator")
        
        # Increase dimensions by 20%
        base_width = 1400
        base_height = 850
        increased_width = int(base_width * 1.2)  # 20% larger
        increased_height = int(base_height * 1.2)  # 20% larger
        
        # Set the new window size
        self.root.geometry(f"{increased_width}x{increased_height}")
        
        # Also increase minimum size by 20%
        min_width = int(1200 * 1.2)
        min_height = int(700 * 1.2)
        self.root.minsize(min_width, min_height)
        
        self.regions = {}
        self.current_region_to_calibrate = None 
        self.screenshot = None
        self.scale_factor = 1.0 
        self.display_img_pil = None 
        self.tk_img = None 
        self.anchors = {} 
        
        # Para guardar o centro do círculo de referência da "Célula de Candidato"
        self.reference_profile_circle_center = None # (x_abs, y_abs)

        self.load_calibration_data()
        self.create_widgets()
    
    def load_calibration_data(self):
        try:
            if os.path.exists('calibration.json'):
                with open('calibration.json', 'r') as f:
                    data = json.load(f)
                    self.regions = data.get("regions", {})
                    self.anchors = data.get("anchors", {})
                    # Carregar também o centro do círculo de referência se existir
                    self.reference_profile_circle_center = data.get("reference_profile_circle_center", None)
                    print("Dados de calibração carregados.")
            else:
                print("Ficheiro calibration.json não encontrado. Nenhuma calibração carregada.")
        except Exception as e:
            print(f"Erro ao carregar dados de calibração: {e}")
            self.regions = {}
            self.anchors = {}
            self.reference_profile_circle_center = None

    def create_widgets(self):
        # ... (como antes) ...
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        control_frame = ttk.LabelFrame(main_frame, text="Controles")
        control_frame.pack(side=tk.LEFT, fill=tk.Y, padx=5, pady=5)
        
        ttk.Button(control_frame, text="Capturar Tela", command=self.capture_screen).pack(fill=tk.X, pady=5)
        
        ttk.Label(control_frame, text="Regiões para Calibrar:").pack(anchor=tk.W, pady=(10,0))
        
        self.region_list_values = [
            "Lista de Candidatos",      
            "Célula de Candidato (com círculo de perfil)", # Instrução mais clara
            "Nome (Relativo ao Círculo)",  
            "Perfil (Relativo ao Círculo)",
            "Data (Relativo ao Círculo)",
            "Localização (Relativo ao Círculo)", # <--- NOVA OPÇÃO AQUI
            "Área de Busca do 'Latest Resume' (Página do Perfil)" 
        ]
        self.region_list = ttk.Combobox(control_frame, values=self.region_list_values, state="readonly")
        self.region_list.pack(fill=tk.X, pady=5)
        self.region_list.bind("<<ComboboxSelected>>", self.on_region_selected_for_calibration)
        
        self.instruction_label = ttk.Label(control_frame, text="Selecione uma região para ver as instruções.", wraplength=200)
        self.instruction_label.pack(fill=tk.X, pady=5)

        ttk.Button(control_frame, text="Definir Região Selecionada", command=self.start_region_selection).pack(fill=tk.X, pady=5)
        ttk.Button(control_frame, text="Salvar Calibração", command=self.save_calibration_data).pack(fill=tk.X, pady=5)
        
        self.view_frame = ttk.LabelFrame(main_frame, text="Visualização da Captura")
        self.view_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.canvas = tk.Canvas(self.view_frame, bg="lightgrey")
        # ... (resto do create_widgets como antes) ...
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Button-1>", self.on_canvas_click)
        self.canvas.bind("<B1-Motion>", self.on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_canvas_release)
        
        self.info_label = ttk.Label(self.view_frame, text="Clique em 'Capturar Tela' para começar.")
        self.info_label.pack(anchor=tk.W, side=tk.BOTTOM)
        
        self.start_x = self.start_y = self.end_x = self.end_y = 0
        self.selection_active = False
        self.selection_rect = None

    def on_region_selected_for_calibration(self, event=None):
        selected = self.region_list.get()
        instructions = {
            "Lista de Candidatos": (
                "IMPORTANTE: A região da lista deve ser ALTA o suficiente!\n\n"
                "• Desenhe um retângulo que inclua TODA a área visível da lista\n"
                "• Inclua pelo menos 3-4 células de candidatos completas\n"
                "• Deixe margem inferior para scroll suave\n"
                "• Quanto maior a altura, melhor o resultado\n"
                "• Evite altura muito justa para prevenir cortes"
            ),
            "Célula de Candidato (com círculo de perfil)": "Desenhe um retângulo em volta de UM candidato completo que contenha um círculo de perfil visível. O sistema tentará encontrar este círculo.",
            "Nome (Relativo ao Círculo)": "IMPORTANTE: Primeiro calibre 'Célula de Candidato'. Depois, desenhe um retângulo APENAS na área do NOME. A sua posição será guardada em relação ao círculo de perfil da célula de referência.",
"Perfil (Relativo ao Círculo)": "IMPORTANTE: Primeiro calibre 'Célula de Candidato'. Depois, desenhe um retângulo APENAS na área do PERFIL/CARGO. A sua posição será guardada em relação ao círculo de perfil da célula de referência.",
"Data (Relativo ao Círculo)": "IMPORTANTE: Desenhe um retângulo à volta da data (ex: 'Added to system: Apr 24, 2026'). A sua posição será guardada em relação ao círculo.",
"Localização (Relativo ao Círculo)": "IMPORTANTE: Desenhe um retângulo à volta da localização (ex: 'London, England'). A sua posição será guardada em relação ao círculo.", # <--- NOVA INSTRUÇÃO
"Área de Busca do 'Latest Resume' (Página do Perfil)": "NA PÁGINA DE PERFIL DE UM CANDIDATO, desenhe um retângulo na área onde o link 'Latest Resume' (ou similar) provavelmente aparecerá. O OCR tentará encontrá-lo dentro desta área."
        }
        self.instruction_label.config(
            text=instructions.get(selected, "Selecione uma região para ver as instruções."),
            wraplength=250  # Increased for better readability
        )
        
        # Show immediate warning for Lista de Candidatos
        if selected == "Lista de Candidatos":
            messagebox.showinfo(
                "Dicas para Calibração da Lista",
                "Para melhor resultado na captura:\n\n"
                "1. Maximize a janela do navegador\n"
                "2. Selecione uma área ALTA da lista\n"
                "3. Inclua várias células completas\n"
                "4. Deixe espaço extra para scroll\n\n"
                "Uma boa calibração evita cortes e falhas!"
            )
    
        if self.screenshot: 
            self.show_region(selected)

    def _detect_circle_in_reference_cell(self):
        """Tenta detetar um círculo de perfil dentro da 'Célula de Candidato' calibrada."""
        if "Célula de Candidato (com círculo de perfil)" not in self.regions or not self.screenshot:
            return None

        ref_cell_coords = self.regions["Célula de Candidato (com círculo de perfil)"]
        
        # Cortar a imagem da célula de referência da screenshot original
        ref_cell_img_pil = self.screenshot.crop((
            ref_cell_coords["left"], ref_cell_coords["top"],
            ref_cell_coords["left"] + ref_cell_coords["width"],
            ref_cell_coords["top"] + ref_cell_coords["height"]
        ))

        ref_cell_cv = cv2.cvtColor(np.array(ref_cell_img_pil), cv2.COLOR_RGB2BGR)
        gray = cv2.cvtColor(ref_cell_cv, cv2.COLOR_BGR2GRAY)
        blurred = cv2.medianBlur(gray, 5)

        # Parâmetros de HoughCircles para a célula de referência (podem ser mais restritivos)
        # min_dist_ref = ref_cell_coords["height"] // 2 # Distância mínima entre círculos
        circles = cv2.HoughCircles(
            blurred, cv2.HOUGH_GRADIENT, dp=1.2, minDist=max(30, ref_cell_coords["height"] // 2),
            param1=60, param2=30, minRadius=15, maxRadius=40 # Ajustar raios
        )

        if circles is not None:
            circles = np.uint16(np.around(circles))
            # Assumir o primeiro círculo detetado (ou o mais proeminente/central)
            # Para simplificar, pegamos o primeiro. Uma lógica mais robusta poderia ser adicionada.
            c = circles[0, 0]
            # Coordenadas do centro do círculo relativas à screenshot original
            center_x_abs = ref_cell_coords["left"] + c[0]
            center_y_abs = ref_cell_coords["top"] + c[1]
            print(f"Círculo de referência detetado em ({c[0]},{c[1]}) dentro da célula de ref. Coords abs: ({center_x_abs},{center_y_abs}), Raio: {c[2]}")
            
            # Desenhar no canvas para feedback visual
            if hasattr(self, 'scale_factor') and self.scale_factor > 0:
                 cx_canvas = center_x_abs * self.scale_factor
                 cy_canvas = center_y_abs * self.scale_factor
                 r_canvas = c[2] * self.scale_factor
                 self.canvas.create_oval(cx_canvas-r_canvas, cy_canvas-r_canvas, 
                                         cx_canvas+r_canvas, cy_canvas+r_canvas, 
                                         outline="magenta", width=2, tags="ref_circle")
                 self.canvas.create_oval(cx_canvas-2, cy_canvas-2, cx_canvas+2, cy_canvas+2, fill="magenta", outline="magenta", tags="ref_circle")


            return {"x": center_x_abs, "y": center_y_abs, "radius": c[2]}
        
        print("Nenhum círculo de referência detetado automaticamente na 'Célula de Candidato'. Usando centro geométrico como fallback.")
        # Fallback: usar o centro geométrico da "Célula de Candidato"
        center_x_abs = ref_cell_coords["left"] + ref_cell_coords["width"] // 2
        center_y_abs = ref_cell_coords["top"] + ref_cell_coords["height"] // 2
        return {"x": center_x_abs, "y": center_y_abs, "radius": 0} # Raio 0 indica fallback

    def on_canvas_release(self, event):
        if self.selection_active and self.screenshot and self.scale_factor > 0:
            self.end_x = self.canvas.canvasx(event.x)
            self.end_y = self.canvas.canvasy(event.y)
            
            # Calcular coordenadas absolutas na screenshot original
            abs_x1 = min(self.start_x, self.end_x) / self.scale_factor
            abs_y1 = min(self.start_y, self.end_y) / self.scale_factor
            abs_x2 = max(self.start_x, self.end_x) / self.scale_factor
            abs_y2 = max(self.start_y, self.end_y) / self.scale_factor

            width_abs = abs_x2 - abs_x1
            height_abs = abs_y2 - abs_y1

            # Verificar se a seleção tem tamanho mínimo
            if width_abs < 5 or height_abs < 5:
                self.info_label.config(text="Seleção muito pequena. Tente novamente.")
                if self.selection_rect: self.canvas.delete(self.selection_rect)
                self.selection_active = False
                self.selection_rect = None
                return

            defined_region_name = self.current_region_to_calibrate
            
            # Salvar coordenadas absolutas da seleção
            current_defined_region_abs_coords = {
                "left": int(abs_x1), "top": int(abs_y1),
                "width": int(width_abs), "height": int(height_abs)
            }
            self.regions[defined_region_name] = current_defined_region_abs_coords
            
            self.info_label.config(text=f"Região '{defined_region_name}' definida: {int(width_abs)}x{int(height_abs)} @ ({int(abs_x1)},{int(abs_y1)})")
            
            # Se for "Célula de Candidato", detectar círculo de perfil
            if defined_region_name == "Célula de Candidato (com círculo de perfil)":
                cell_img_pil = self.screenshot.crop((
                    int(abs_x1), int(abs_y1), int(abs_x2), int(abs_y2)
                ))
                
                cell_cv = cv2.cvtColor(np.array(cell_img_pil), cv2.COLOR_RGB2BGR)
                gray = cv2.cvtColor(cell_cv, cv2.COLOR_BGR2GRAY)
                blurred = cv2.medianBlur(gray, 5)
                
                # Detectar círculos de perfil
                circles = cv2.HoughCircles(
                    blurred, cv2.HOUGH_GRADIENT, dp=1.2, 
                    minDist=max(30, int(height_abs) // 2),
                    param1=60, param2=30, 
                    minRadius=15, maxRadius=40
                )
                
                # Se detectamos círculos, usar o primeiro
                if circles is not None:
                    circles = np.uint16(np.around(circles))
                    c = circles[0, 0]  # Pegar primeiro círculo
                    
                    # Coordenadas do círculo em relação à screenshot
                    circle_x = int(abs_x1) + int(c[0])
                    circle_y = int(abs_y1) + int(c[1])
                    circle_r = int(c[2])
                    
                    # Guardar o círculo de referência
                    self.reference_profile_circle_center = {
                        "x": circle_x, 
                        "y": circle_y, 
                        "radius": circle_r
                    }
                    
                    # Feedback visual - desenhar o círculo no canvas
                    cx_canvas = circle_x * self.scale_factor
                    cy_canvas = circle_y * self.scale_factor
                    r_canvas = circle_r * self.scale_factor
                    
                    self.canvas.create_oval(
                        cx_canvas - r_canvas, cy_canvas - r_canvas,
                        cx_canvas + r_canvas, cy_canvas + r_canvas,
                        outline="magenta", width=2, tags="ref_circle"
                    )
                    
                    self.info_label.config(text=f"'Célula de Candidato' definida com círculo em ({circle_x},{circle_y}), raio={circle_r}px")
                    print(f"Círculo de referência definido: {self.reference_profile_circle_center}")
                else:
                    # Estimativa de círculo se não detectamos
                    self.reference_profile_circle_center = {
                        "x": int(abs_x1 + width_abs // 4),
                        "y": int(abs_y1 + height_abs // 2),
                        "radius": min(25, int(min(width_abs, height_abs) // 5))
                    }
                    self.info_label.config(text=f"'Célula de Candidato' definida. Círculo estimado, não detectado automaticamente.")
                    print(f"Círculo estimado: {self.reference_profile_circle_center}")
            
            # Para Nome, Perfil, Data ou Localização, calcular offsets relativos ao círculo
            elif defined_region_name in ["Nome (Relativo ao Círculo)", "Perfil (Relativo ao Círculo)", "Data (Relativo ao Círculo)", "Localização (Relativo ao Círculo)"]:
                if self.reference_profile_circle_center:
                    # Calcular offsets relativos ao centro do círculo
                    offset_x = int(abs_x1) - self.reference_profile_circle_center["x"]
                    offset_y = int(abs_y1) - self.reference_profile_circle_center["y"]
                    
                    # Salvar tanto no formato de offset quanto no formato compatível
                    offset_key = f"{defined_region_name}_offset_from_circle"
                    self.regions[offset_key] = {
                        "offset_x": offset_x,
                        "offset_y": offset_y,
                        "width": int(width_abs),
                        "height": int(height_abs)
                    }
                    
                    # Formato compatível usado pelo bot atual
                    compat_name = defined_region_name.replace("Relativo ao Círculo", "Dentro da Célula")
                    compat_key = f"{compat_name}_rel_to_cell"
                    self.regions[compat_key] = {
                        "left": offset_x,
                        "top": offset_y,
                        "width": int(width_abs),
                        "height": int(height_abs)
                    }
                    
                    # <--- CORREÇÃO AQUI: Apagar a gravação absoluta inútil que causa duplicação
                    if defined_region_name in self.regions:
                        del self.regions[defined_region_name]
                        
                    self.info_label.config(text=f"{defined_region_name} definida. Offset do círculo: ({offset_x},{offset_y})")
                    print(f"Coordenadas relativas salvas para {compat_key}: {self.regions[compat_key]}")
                else:
                    self.info_label.config(text=f"AVISO: {defined_region_name} definida mas sem círculo de referência!")
                    messagebox.showwarning(
                        "Círculo de Referência Ausente", 
                        f"Para calibrar {defined_region_name} corretamente, deve primeiro definir 'Célula de Candidato (com círculo de perfil)'."
                    )
            
            # Finalizar edição
            self.selection_active = False
            if self.selection_rect: self.canvas.delete(self.selection_rect)
            self.selection_rect = None
            
            # Atualizar visualização
            self.display_all_calibrated_regions()


    def _convert_numpy_to_python(self, obj):
        """Converte valores NumPy para tipos Python nativos recursivamente."""
        if obj is None:
            return None
        elif isinstance(obj, dict):
            return {k: self._convert_numpy_to_python(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_to_python(item) for item in obj]
        elif hasattr(obj, "item") and callable(getattr(obj, "item", None)):
            return obj.item()  # Converte de NumPy para Python nativo
        else:
            return obj
    
    def save_calibration_data(self): 
        try:
            # 1. Ler o que já existe no ficheiro para não apagar configurações globais
            existing_data = {}
            if os.path.exists('calibration.json'):
                with open('calibration.json', 'r') as f:
                    existing_data = json.load(f)

            # 2. Atualizar apenas as chaves de calibração
            existing_data["regions"] = self._convert_numpy_to_python(self.regions)
            existing_data["anchors"] = self._convert_numpy_to_python(self.anchors)
            existing_data["reference_profile_circle_center"] = self._convert_numpy_to_python(self.reference_profile_circle_center)
            
            # 3. Salvar o ficheiro completo
            with open('calibration.json', 'w') as f:
                json.dump(existing_data, f, indent=4)
                
            self.info_label.config(text="Calibração salva com sucesso em calibration.json!")
            messagebox.showinfo("Salvo", "Dados de calibração salvos.")
        except Exception as e:
            self.info_label.config(text=f"Erro ao salvar calibração: {e}")
            messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar os dados de calibração:\n{e}")


    def display_all_calibrated_regions(self):
        if not self.tk_img: return
        
        self.canvas.delete("region_rect") 
        self.canvas.delete("region_text") 
        self.canvas.delete("highlight")
        self.canvas.delete("ref_circle") # Limpar círculo de referência anterior

        colors = {
            "Lista de Candidatos": "blue",
            "Célula de Candidato (com círculo de perfil)": "red",
            "Nome (Relativo ao Círculo)": "darkgreen", 
            "Perfil (Relativo ao Círculo)": "purple",
            "Data (Relativo ao Círculo)": "teal",
            "Localização (Relativo ao Círculo)": "brown", # <--- NOVA COR
            "Área de Busca do 'Latest Resume' (Página do Perfil)": "orange"
            # Adicione mais cores se tiver mais tipos de regiões que não são de offset
        }
        for name, region_data in self.regions.items(): # Renomeado para region_data para clareza
            # CORREÇÃO AQUI:
            if name.endswith("_offset_from_circle"): 
                # Esta é uma região de offset puro, não tem 'left'/'top' absolutos para desenhar diretamente.
                # O seu desenho é implícito pela região relativa ao círculo.
                continue 

            # Adicionar uma verificação robusta para garantir que region_data tem o formato esperado
            if not isinstance(region_data, dict) or not all(k in region_data for k in ["left", "top", "width", "height"]):
                print(f"AVISO (display_all_calibrated_regions): Região '{name}' com formato inesperado ou incompleto: {region_data}. Ignorando para desenho.")
                continue
            
            # Se passou pelas verificações, region_data é region_coords_abs
            region_coords_abs = region_data

            x1_c = region_coords_abs["left"] * self.scale_factor
            y1_c = region_coords_abs["top"] * self.scale_factor
            x2_c = (region_coords_abs["left"] + region_coords_abs["width"]) * self.scale_factor
            y2_c = (region_coords_abs["top"] + region_coords_abs["height"]) * self.scale_factor
            
            # Determinar a cor. Se a região for uma _rel_to_cell, usar a cor da sua base "Relativo ao Círculo"
            base_name_for_color = name
            if name.endswith("_rel_to_cell"):
                base_name_for_color = name.replace("_rel_to_cell", "").replace("Dentro da Célula", "Relativo ao Círculo")
            
            color = colors.get(base_name_for_color, "black") # Cor padrão preta se não definida

            # Para regiões _rel_to_cell, as coordenadas 'left' e 'top' são offsets.
            # Precisamos desenhá-las em relação ao reference_profile_circle_center.
            if name.endswith("_rel_to_cell"):
                if self.reference_profile_circle_center:
                    # 'left' e 'top' em region_coords_abs são os offsets x e y
                    offset_x = region_coords_abs["left"]
                    offset_y = region_coords_abs["top"]
                    
                    # Coordenadas absolutas do canto superior esquerdo da região relativa
                    abs_rel_left = self.reference_profile_circle_center["x"] + offset_x
                    abs_rel_top = self.reference_profile_circle_center["y"] + offset_y
                    
                    x1_c = abs_rel_left * self.scale_factor
                    y1_c = abs_rel_top * self.scale_factor
                    x2_c = (abs_rel_left + region_coords_abs["width"]) * self.scale_factor
                    y2_c = (abs_rel_top + region_coords_abs["height"]) * self.scale_factor
                    
                    self.canvas.create_rectangle(x1_c, y1_c, x2_c, y2_c, outline=color, width=2, dash=(3,3), tags=("region_rect", name))
                else:
                    # Se não há círculo de referência, ignoramos o desenho para não atirar caixas para o canto superior!
                    continue
            else: # Para regiões absolutas (ex: Lista de Candidatos)
                self.canvas.create_rectangle(x1_c, y1_c, x2_c, y2_c, outline=color, width=2, tags=("region_rect", name))

            self.canvas.create_text(x1_c + 5, y1_c + 5, text=name, anchor=tk.NW, fill=color, font=("Arial", 8, "bold"), tags=("region_text", name))
        
        # ... (resto do código para desenhar o círculo de referência) ...
        if self.reference_profile_circle_center and self.reference_profile_circle_center.get("radius", 0) > 0 :
            cx_abs = self.reference_profile_circle_center["x"]
            cy_abs = self.reference_profile_circle_center["y"]
            r_abs = self.reference_profile_circle_center["radius"]
            
            cx_canvas = cx_abs * self.scale_factor
            cy_canvas = cy_abs * self.scale_factor
            r_canvas = r_abs * self.scale_factor
            self.canvas.create_oval(cx_canvas-r_canvas, cy_canvas-r_canvas, 
                                     cx_canvas+r_canvas, cy_canvas+r_canvas, 
                                     outline="magenta", width=2, tags="ref_circle")
            self.canvas.create_oval(cx_canvas-2, cy_canvas-2, cx_canvas+2, cy_canvas+2, fill="magenta", outline="magenta", tags="ref_circle")


    def show_region(self, region_name_to_show):
        if not self.tk_img:
            self.info_label.config(text="Capture a tela primeiro para ver as regiões.")
            return

        self.display_all_calibrated_regions() 

        if region_name_to_show in self.regions and not region_name_to_show.endswith("_offset_from_ref_circle"):
            region_coords_abs = self.regions[region_name_to_show]
            x1_c = region_coords_abs["left"] * self.scale_factor
            y1_c = region_coords_abs["top"] * self.scale_factor
            x2_c = (region_coords_abs["left"] + region_coords_abs["width"]) * self.scale_factor
            y2_c = (region_coords_abs["top"] + region_coords_abs["height"]) * self.scale_factor
            
            self.canvas.create_rectangle(x1_c, y1_c, x2_c, y2_c, outline="yellow", width=3, tags="highlight")
            self.info_label.config(text=f"Mostrando região: {region_name_to_show}")
        else:
            self.info_label.config(text=f"Região '{region_name_to_show}' não calibrada ou é uma definição de offset.")
            
    # ... (capture_screen, display_screenshot_on_canvas, detect_browser, start_region_selection, on_canvas_click, on_canvas_drag, run)
    def capture_screen(self): # Manter como estava
        self.info_label.config(text="Preparando para capturar tela em 3 segundos...")
        self.root.update()
        time.sleep(1); self.info_label.config(text="Capturando em 2..."); self.root.update()
        time.sleep(1); self.info_label.config(text="Capturando em 1..."); self.root.update()
        time.sleep(1)
        
        self.root.iconify()
        self.root.update()
        time.sleep(0.5) 
        self.screenshot = pyautogui.screenshot()
        self.root.deiconify()
        
        self.display_screenshot_on_canvas() 
        self.info_label.config(text="Captura de tela concluída! Selecione uma região e clique 'Definir Região'.")
        self.display_all_calibrated_regions() 

    def display_screenshot_on_canvas(self): # Manter como estava
        if self.screenshot:
            self.canvas.update_idletasks() 
            canvas_width = self.canvas.winfo_width()
            canvas_height = self.canvas.winfo_height()
            
            if canvas_width <= 1 or canvas_height <= 1:
                canvas_width, canvas_height = 1000, 700 
            
            img_width, img_height = self.screenshot.size
            self.scale_factor = min(canvas_width / img_width, canvas_height / img_height)
            
            new_width = int(img_width * self.scale_factor)
            new_height = int(img_height * self.scale_factor)
            
            self.display_img_pil = self.screenshot.resize((new_width, new_height), Image.Resampling.LANCZOS)
            self.tk_img = ImageTk.PhotoImage(self.display_img_pil)
            
            self.canvas.delete("all")
            self.canvas.create_image(0, 0, image=self.tk_img, anchor=tk.NW)
            print(f"Imagem redimensionada para {new_width}x{new_height}, fator de escala: {self.scale_factor}")

    def detect_browser(self): # Manter como estava (opcional)
        self.info_label.config(text="Detecção de navegador (Opcional).")
        pass 

    def start_region_selection(self): # Manter como estava
        if not self.screenshot:
            self.info_label.config(text="ERRO: Capture a tela primeiro!")
            messagebox.showerror("Erro", "Você precisa capturar a tela antes de definir uma região.")
            return
        self.current_region_to_calibrate = self.region_list.get()
        if not self.current_region_to_calibrate:
            self.info_label.config(text="ERRO: Selecione um tipo de região da lista!")
            messagebox.showerror("Erro", "Por favor, selecione um tipo de região da lista.")
            return
            
        self.selection_active = True
        self.info_label.config(text=f"Desenhando '{self.current_region_to_calibrate}': Clique e arraste na imagem.")

    def on_canvas_click(self, event): # Manter como estava
        if self.selection_active:
            self.start_x = self.canvas.canvasx(event.x) 
            self.start_y = self.canvas.canvasy(event.y)
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
            self.selection_rect = None 
    
    def on_canvas_drag(self, event): # Manter como estava
        if self.selection_active:
            cur_x = self.canvas.canvasx(event.x)
            cur_y = self.canvas.canvasy(event.y)
            if self.selection_rect:
                self.canvas.delete(self.selection_rect)
            self.selection_rect = self.canvas.create_rectangle(
                self.start_x, self.start_y, cur_x, cur_y,
                outline="green", width=2, dash=(4, 2)
            )
    def run(self): # Manter como estava
        self.root.mainloop()

