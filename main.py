# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
import pandas as pd
import sys
import traceback
import json

from smart_recruiter_bot import SmartRecruiterBot
from region_calibrator import RegionCalibrator
from image_processor import ImageProcessor
from candidate_extractor import CandidateExtractor
from config_manager import ConfigManager

class SmartRecruiterGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("SmartRecruiters Automation Tool")
        
        # Create a style for the reset button
        style = ttk.Style()
        style.configure("Reset.TButton", 
                       foreground="red",
                       padding=5)
        
        # Obter as dimensões do ecrã
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        
        window_width = int(screen_width // 3)  
        window_height = int((screen_height - 120))
        
        # Center the window on screen
        position_x = 0
        position_y = 0
        
        # Ensure window doesn't exceed screen bounds
        window_width = min(window_width, screen_width)
        window_height = min(window_height, screen_height)
        
        self.root.geometry(f"{window_width}x{window_height}+{position_x}+{position_y}")

        # --- INICIALIZAÇÃO DAS VARIÁVEIS TKINTER PARA CONFIGURAÇÕES ---
        self.tesseract_path_var = tk.StringVar()
        
        # Novas variáveis Tkinter para configurações de download de resumos
        self.resume_download_dir_var = tk.StringVar()
        self.resume_link_text_var = tk.StringVar()
        self.save_as_option_index_var = tk.IntVar(value=5)

        # Variáveis para configurações gerais de captura
        self.max_scroll_iter_var = tk.IntVar(value=20)
        self.scroll_interval_var = tk.DoubleVar(value=2.0)

        self.config_manager = ConfigManager()
        self.image_processor = ImageProcessor()
        
        # Verificar se o Tesseract está disponível e configurado
        self.tesseract_available = False
        tesseract_path = self.config_manager.get_setting("tesseract_path")
        if tesseract_path:
            if os.path.exists(tesseract_path):
                self.image_processor.set_tesseract_path(tesseract_path)
                self.tesseract_available = True
        else:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self.tesseract_available = True
            except (ImportError, Exception):
                self.tesseract_available = False

        self.candidate_extractor = CandidateExtractor(self.image_processor)
        
        self.bot = SmartRecruiterBot(
            self.config_manager, 
            self.image_processor,
            self.candidate_extractor
        )

        self.ai_matched_candidate_details = []
        self.original_captured_candidates = []
        self.filtered_candidates = []
        
        self.running = False
        self.interacting_with_profiles = False
        self.debug_var = tk.BooleanVar(value=False)

        self.create_widgets()
        self.load_settings_to_ui()
        self.update_status("Pronto")
    
    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.capture_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.capture_tab, text="Captura")
        
        self.calibration_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.calibration_tab, text="Calibração")
        
        self.results_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.results_tab, text="Resultados")

        
        
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Configurações")
        
        self.setup_capture_tab()
        self.setup_calibration_tab()
        self.setup_results_tab()
        
        self.setup_settings_tab()
        
        self.status_var = tk.StringVar()
        self.status_var.set("Pronto")
        self.status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)
    
    def setup_capture_tab(self):
        capture_frame = self.capture_tab
        
        instruction_label = ttk.Label(
            capture_frame, 
            text="Esta ferramenta automatiza a captura de candidatos do SmartRecruiters.\n"
                "1. Configure o Tesseract e outras opções na aba 'Configurações'.\n"
                "2. Use a aba 'Calibração' para definir as regiões de captura.\n"
                "3. Clique em 'Iniciar Captura' e não mova o mouse.\n",
            justify=tk.LEFT,
            wraplength=600
        )
        instruction_label.pack(anchor='w', padx=10, pady=10)

        main_capture_frame = ttk.Frame(capture_frame)
        main_capture_frame.pack(fill=tk.BOTH, padx=10, pady=10, expand=True)
        
        top_options_frame = ttk.Frame(main_capture_frame)
        top_options_frame.pack(fill=tk.X, pady=(0, 10))
        
        buttons_frame = ttk.Frame(top_options_frame)
        buttons_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        self.capture_button = ttk.Button(buttons_frame, text="Iniciar Captura", command=self.start_capture)
        self.capture_button.pack(side=tk.LEFT, padx=(0, 5))
        
        self.reset_button = ttk.Button(
            buttons_frame, 
            text="Redefinir Calibrações",
            command=self.reset_calibrations,
            style="Reset.TButton"
        )
        self.reset_button.pack(side=tk.LEFT, padx=5)
        
        debug_check = ttk.Checkbutton(top_options_frame, text="Modo Debug", variable=self.debug_var)
        debug_check.pack(side=tk.LEFT)

        status_frame = ttk.Frame(main_capture_frame)
        status_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(status_frame, text="Status:").pack(side=tk.LEFT, padx=(0,5))
        self.status_label = ttk.Label(status_frame, text="Pronto")
        self.status_label.pack(side=tk.LEFT)
        
        self.progress_var = tk.DoubleVar(value=0)
        self.progress_bar = ttk.Progressbar(
            main_capture_frame, 
            orient="horizontal", 
            length=600, 
            mode="determinate", 
            variable=self.progress_var
        )
        self.progress_bar.pack(fill=tk.X, pady=(0, 10))
        
        log_frame = ttk.LabelFrame(main_capture_frame, text="Logs")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=15)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        log_scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)
        
        ttk.Label(
            main_capture_frame, 
            text="Após a captura, vá para a aba 'Resultados' para ver os candidatos extraídos."
        ).pack(anchor='w', pady=(0, 10))

    def setup_calibration_tab(self):
        main_frame = ttk.Frame(self.calibration_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        ttk.Button(main_frame, text="Abrir Calibrador Visual", command=self.open_calibrator).pack(fill=tk.X, pady=10)
        
        calibration_status_frame = ttk.LabelFrame(main_frame, text="Status de Calibração")
        calibration_status_frame.pack(fill=tk.X, pady=10)
        
        ttk.Label(calibration_status_frame, text="Regiões calibradas:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        
        self.calibration_status_text = tk.Text(calibration_status_frame, height=10, width=50, wrap=tk.WORD, state=tk.DISABLED)
        self.calibration_status_text.grid(row=1, column=0, padx=5, pady=5, sticky=tk.EW)
        
        self.update_calibration_status()
    
    def setup_results_tab(self):
        main_frame = ttk.Frame(self.results_tab)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        stats_frame = ttk.LabelFrame(main_frame, text="Estatísticas")
        stats_frame.pack(fill=tk.X, pady=5)
        
        self.stats_var = tk.StringVar()
        self.stats_var.set("Nenhuma captura realizada.")
        ttk.Label(stats_frame, textvariable=self.stats_var, justify=tk.LEFT).pack(padx=5, pady=5, anchor=tk.W)
        
        table_frame = ttk.LabelFrame(main_frame, text="Candidatos Capturados (Nome e Perfil)")
        table_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        columns = ("Nome", "Perfil")
        self.results_tree = ttk.Treeview(table_frame, columns=columns, show="headings", height=12)
        
        style = ttk.Style()
        style.configure("Treeview", rowheight=25)
        
        self.results_tree.heading("Nome", text="Nome do Candidato")
        self.results_tree.column("Nome", width=250, minwidth=150, stretch=tk.YES)
        
        self.results_tree.heading("Perfil", text="Perfil/Cargo")
        self.results_tree.column("Perfil", width=300, minwidth=200, stretch=tk.YES)
        
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar_y = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        scrollbar_y.pack(side=tk.RIGHT, fill=tk.Y)
        self.results_tree.configure(yscrollcommand=scrollbar_y.set)

        scrollbar_x = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.results_tree.xview)
        scrollbar_x.pack(side=tk.BOTTOM, fill=tk.X)
        self.results_tree.configure(xscrollcommand=scrollbar_x.set)

        buttons_frame = ttk.Frame(main_frame)
        buttons_frame.pack(fill=tk.X, pady=5)
        
        ttk.Button(buttons_frame, text="Exportar XLSX", command=self.export_xlsx).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Limpar Resultados", command=self.clear_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Atualizar Tabela", command=self.update_results_display).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Resetar para Captura Original", command=self.reset_to_original_capture).pack(side=tk.LEFT, padx=5)

    def export_xlsx(self):
        """Exporta candidatos para XLSX"""
        if not self.candidate_extractor.candidates:
            messagebox.showinfo("Exportar XLSX", "Não há candidatos para exportar.")
            return
        
        filename = filedialog.asksaveasfilename(
            defaultextension=".xlsx",
            filetypes=[("Excel files", "*.xlsx"), ("All files", "*.*")],
            initialdir=os.path.join(os.getcwd(), "data"),
            title="Salvar XLSX dos Candidatos"
        )
        
        if filename: 
            try:
                saved_file = self.candidate_extractor.save_to_xlsx(filename)
                if saved_file:
                    messagebox.showinfo("Exportar XLSX", f"Dados exportados com sucesso para {saved_file}")
                    self.log(f"Dados exportados para {saved_file}")
                else:
                    self.log(f"Falha ao exportar para {filename}. Verifique os logs anteriores.")
            except Exception as e_export:
                messagebox.showerror("Erro ao Exportar", f"Não foi possível exportar o arquivo XLSX:\n{e_export}")
                self.log(f"Erro ao exportar XLSX para {filename}: {e_export}")

    def clear_results(self):
        if messagebox.askyesno("Limpar Resultados", "Tem certeza que deseja limpar todos os resultados da tabela e os dados capturados?"):
            self.candidate_extractor.candidates = []
            self.update_results_display()
            self.log("Resultados limpos.")

    def update_results_display(self): 
        """Atualiza a exibição da tabela de resultados."""
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        
        candidates = self.candidate_extractor.candidates
        
        for i, candidate in enumerate(candidates):
            self.results_tree.insert("", "end", iid=str(i), values=(
                candidate.get("name", ""),
                candidate.get("profile", "")
            ))
        
        if candidates:
            stats_text = f"Total de candidatos únicos capturados: {len(candidates)}"
            self.stats_var.set(stats_text)
        else:
            self.stats_var.set("Nenhuma captura realizada ou resultados limpos.")
    
    def setup_settings_tab(self):
        settings_frame = self.settings_tab

        # --- Configurações do Tesseract OCR ---
        ttk.Label(settings_frame, text="--- Configurações do Tesseract OCR ---", 
                font=('Arial', 10, 'bold')).pack(pady=(10, 5), anchor='w', padx=5)

        tesseract_frame = ttk.Frame(settings_frame)
        tesseract_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(tesseract_frame, text="Caminho para tesseract.exe:", width=30).pack(side=tk.LEFT, padx=(0,5))
        self.tesseract_path_entry = ttk.Entry(tesseract_frame, textvariable=self.tesseract_path_var, width=60)
        self.tesseract_path_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(tesseract_frame, text="Procurar...", command=self.browse_tesseract_path).pack(side=tk.LEFT, padx=(5,0))

        

        # --- Configurações de Download de Resumos ---
        ttk.Label(settings_frame, text="--- Configurações de Download de Resumos ---", 
                font=('Arial', 10, 'bold')).pack(pady=(15, 5), anchor='w', padx=5)

        dir_frame = ttk.Frame(settings_frame)
        dir_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(dir_frame, text="Diretório de Download de Resumos:", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.resume_download_dir_entry = ttk.Entry(dir_frame, textvariable=self.resume_download_dir_var, width=50)
        self.resume_download_dir_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        ttk.Button(dir_frame, text="Procurar...", command=self.browse_resume_download_directory).pack(side=tk.LEFT, padx=(5,0))

        link_text_frame = ttk.Frame(settings_frame)
        link_text_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(link_text_frame, text="Texto do Link do Resumo (na página do perfil):", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.resume_link_text_entry = ttk.Entry(link_text_frame, textvariable=self.resume_link_text_var, width=40)
        self.resume_link_text_entry.pack(side=tk.LEFT)

        option_index_frame = ttk.Frame(settings_frame)
        option_index_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(option_index_frame, text="Índice 'Guardar Como' (0=primeira, setas baixo):", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.save_as_option_index_spinbox = ttk.Spinbox(option_index_frame, from_=0, to=15, 
                                                        textvariable=self.save_as_option_index_var, width=5)
        self.save_as_option_index_spinbox.pack(side=tk.LEFT)
        
        # --- Configurações Gerais de Captura ---
        ttk.Label(settings_frame, text="--- Configurações Gerais de Captura ---", 
                font=('Arial', 10, 'bold')).pack(pady=(15, 5), anchor='w', padx=5)

        scroll_iter_frame = ttk.Frame(settings_frame)
        scroll_iter_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(scroll_iter_frame, text="Máximo de Iterações de Scroll:", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.max_scroll_iter_spinbox = ttk.Spinbox(scroll_iter_frame, from_=1, to=100, 
                                                textvariable=self.max_scroll_iter_var, width=5)
        self.max_scroll_iter_spinbox.pack(side=tk.LEFT)

        scroll_interval_frame = ttk.Frame(settings_frame)
        scroll_interval_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(scroll_interval_frame, text="Intervalo entre Scrolls (segundos):", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.scroll_interval_spinbox = ttk.Spinbox(scroll_interval_frame, from_=0.1, to=10.0, increment=0.1,
                                                textvariable=self.scroll_interval_var, width=5, format="%.1f")
        self.scroll_interval_spinbox.pack(side=tk.LEFT)

        # Botão Salvar Configurações
        save_button_settings = ttk.Button(settings_frame, text="Salvar Todas as Configurações", command=self.save_settings)
        save_button_settings.pack(pady=20, padx=10, anchor='center')

    def load_settings_to_ui(self):
        """✅ CORRIGIDO: Carregar todas as configurações incluindo scroll"""
        self.tesseract_path_var.set(self.config_manager.get_setting("tesseract_path", ""))
        

        # Carregar configurações de download
        default_download_dir = os.path.join(os.getcwd(), "downloaded_resumes")
        self.resume_download_dir_var.set(self.config_manager.get_setting("resume_download_directory", default_download_dir))
        
        self.resume_link_text_var.set(self.config_manager.get_setting("resume_link_text", "Latest Resume"))
        
        try:
            save_as_index = int(self.config_manager.get_setting("context_menu_save_as_option_index", 5))
            self.save_as_option_index_var.set(save_as_index)
        except (ValueError, TypeError):
            default_index = 5
            self.save_as_option_index_var.set(default_index)
            self.config_manager.set_setting("context_menu_save_as_option_index", default_index)
        
        # ✅ ADICIONAR ESTAS LINHAS PARA CARREGAR AS CONFIGURAÇÕES DE SCROLL:
        try:
            max_scroll = int(self.config_manager.get_setting("max_scroll_iterations", 20))
            self.max_scroll_iter_var.set(max_scroll)
        except (ValueError, TypeError):
            default_max_scroll = 20
            self.max_scroll_iter_var.set(default_max_scroll)
            self.log(f"AVISO: Configuração 'max_scroll_iterations' inválida, usando default {default_max_scroll}.")
        
        try:
            scroll_interval = float(self.config_manager.get_setting("scroll_interval", 2.0))
            self.scroll_interval_var.set(scroll_interval)
        except (ValueError, TypeError):
            default_interval = 2.0
            self.scroll_interval_var.set(default_interval)
            self.log(f"AVISO: Configuração 'scroll_interval' inválida, usando default {default_interval}.")

        self.log("Configurações carregadas para a UI.")
    
    def browse_tesseract_path(self):
        filetypes = (
            ("Executáveis", "*.exe"),
            ("Todos os ficheiros", "*.*")
        )
        initial_dir = os.getenv("ProgramFiles", "C:/") + "/Tesseract-OCR" 
        if not os.path.exists(initial_dir):
            initial_dir = "C:/"
        filepath = filedialog.askopenfilename(
            title="Selecione o tesseract.exe",
            initialdir=initial_dir,
            filetypes=filetypes
        )
        if filepath:
            self.tesseract_path_var.set(filepath)
            self.log(f"Caminho do Tesseract selecionado: {filepath}")

    def browse_resume_download_directory(self):
        directory = filedialog.askdirectory(title="Selecione o Diretório para Download de Resumos")
        if directory:
            self.resume_download_dir_var.set(directory)
            self.log(f"Diretório de download de resumos selecionado: {directory}")

    def save_settings(self):
        """✅ CORRIGIDO: Salvar todas as configurações incluindo scroll"""
        tesseract_path = self.tesseract_path_var.get()
        self.config_manager.set_setting("tesseract_path", tesseract_path)
        
        # Atualizar a flag tesseract_available
        if tesseract_path:
            if os.path.exists(tesseract_path):
                result = self.image_processor.set_tesseract_path(tesseract_path)
                if result:
                    self.tesseract_available = True
                    self.log("Tesseract configurado e verificado com sucesso.")
                else:
                    self.tesseract_available = False
                    self.log("AVISO: Tesseract configurado mas não passou na verificação.")
                    messagebox.showwarning(
                        "Configuração do Tesseract",
                        "O caminho foi salvo mas o Tesseract pode não estar funcional.\n"
                        "Verifique se o ficheiro está correto e acessível."
                    )
            else:
                self.tesseract_available = False
                self.log(f"AVISO: Ficheiro Tesseract não existe: {tesseract_path}")
                messagebox.showwarning(
                    "Ficheiro não Encontrado",
                    f"O ficheiro não existe:\n{tesseract_path}\n\n"
                    "Por favor, verifique o caminho."
                )
        else:
            try:
                import pytesseract
                pytesseract.get_tesseract_version()
                self.tesseract_available = True
                self.log("Tesseract encontrado no PATH do sistema.")
            except:
                self.tesseract_available = False
                self.log("AVISO: Nenhum caminho configurado e Tesseract não encontrado no PATH.")

        # Salvar outras configurações
        

        # Salvar configurações de download
        self.config_manager.set_setting("resume_download_directory", self.resume_download_dir_var.get())
        self.config_manager.set_setting("resume_link_text", self.resume_link_text_var.get())
        
        try:
            save_as_index = int(self.save_as_option_index_var.get())
            self.config_manager.set_setting("context_menu_save_as_option_index", save_as_index)
        except (ValueError, tk.TclError): 
            default_index = 5
            self.config_manager.set_setting("context_menu_save_as_option_index", default_index)
            self.save_as_option_index_var.set(default_index)
            self.log(f"AVISO: Índice da opção 'Guardar Como' inválido, usando default {default_index}.")
        
        # ✅ ADICIONAR ESTAS LINHAS PARA SALVAR AS CONFIGURAÇÕES DE SCROLL:
        try:
            max_scroll = int(self.max_scroll_iter_var.get())
            self.config_manager.set_setting("max_scroll_iterations", max_scroll)
        except (ValueError, tk.TclError):
            default_max_scroll = 20
            self.config_manager.set_setting("max_scroll_iterations", default_max_scroll)
            self.max_scroll_iter_var.set(default_max_scroll)
            self.log(f"AVISO: Máximo de iterações de scroll inválido, usando default {default_max_scroll}.")
        
        try:
            scroll_interval = float(self.scroll_interval_var.get())
            self.config_manager.set_setting("scroll_interval", scroll_interval)
        except (ValueError, tk.TclError):
            default_interval = 2.0
            self.config_manager.set_setting("scroll_interval", default_interval)
            self.scroll_interval_var.set(default_interval)
            self.log(f"AVISO: Intervalo de scroll inválido, usando default {default_interval}.")

        self.log("Configurações salvas.")
        messagebox.showinfo("Configurações", "Configurações salvas com sucesso!")

    def update_calibration_status(self):
        regions = self.config_manager.get_regions()
        self.calibration_status_text.config(state=tk.NORMAL)
        self.calibration_status_text.delete("1.0", tk.END)
        
        if not regions:
            self.calibration_status_text.insert(tk.END, "Nenhuma região calibrada.\n")
        else:
            for name, region in regions.items():
                if name.endswith("_rel_to_cell") or name.endswith("_offset_from_circle"):
                    self.calibration_status_text.insert(tk.END, f"{name}: offset_x={region.get('offset_x', region.get('left', 0))}, "
                                                            f"offset_y={region.get('offset_y', region.get('top', 0))}, "
                                                            f"w={region.get('width', 0)}, h={region.get('height', 0)}\n")
                else:
                    self.calibration_status_text.insert(tk.END, f"{name}: left={region.get('left', 0)}, "
                                                            f"top={region.get('top', 0)}, "
                                                            f"w={region.get('width', 0)}, h={region.get('height', 0)}\n")
                    
        self.calibration_status_text.config(state=tk.DISABLED)

    def open_calibrator(self):
        self.root.iconify()
        calibrator_win = tk.Toplevel(self.root)
        calibrator = RegionCalibrator(calibrator_win)
        self.root.wait_window(calibrator_win)
        self.root.deiconify()
        self.update_calibration_status()
    
    def log(self, message):
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()
    
    def update_progress(self, value):
        self.progress_var.set(value)
        self.root.update_idletasks()
    
    def update_status(self, message):
        self.status_var.set(message)
        self.root.update_idletasks()
    
    def start_capture(self):
        if self.running:
            messagebox.showinfo("Em execução", "Já existe uma captura em andamento.")
            return
        
        if not self.tesseract_available:
            messagebox.showerror("Tesseract não encontrado", 
                           "O Tesseract OCR não está instalado ou não foi configurado corretamente.\n"
                           "Por favor, verifique o caminho na aba Configurações e tente novamente.")
            return
        
        required_regions = ["Lista de Candidatos"]
        current_calibrated_regions = self.config_manager.get_regions()
        missing_regions = [r for r in required_regions if r not in current_calibrated_regions]
        if missing_regions:
            messagebox.showerror("Erro de Calibração", 
                                 f"As seguintes regiões essenciais precisam ser calibradas primeiro: {', '.join(missing_regions)}.\n"
                                 "Vá para a aba 'Calibração'.")
            return
        
        self.running = True
        self.log("Iniciando captura...")
        self.update_status("Capturando candidatos...")
        self.capture_button.config(text="Capturando...", state=tk.DISABLED)
        
        self.bot.max_scroll_iterations = self.max_scroll_iter_var.get()
        try:
            self.bot.scroll_interval = float(self.scroll_interval_var.get())
        except ValueError:
            self.log("AVISO: Intervalo de scroll inválido, usando padrão de 2.0s.")
            self.bot.scroll_interval = 2.0

        thread = threading.Thread(target=self.capture_thread, name="CaptureThread")
        thread.daemon = True
        thread.start()
    
    def capture_thread(self):
        try:
            debug_mode = self.debug_var.get()
            self.log(f"Modo de depuração: {'Ativado' if debug_mode else 'Desativado'}")
            
            if hasattr(self.image_processor, 'debug'):
                 self.image_processor.debug = debug_mode
            else:
                 setattr(self.image_processor, 'debug', debug_mode)
                 self.log("AVISO: Atributo 'debug' não encontrado em ImageProcessor, foi criado dinamicamente.")
            
            self.log("A captura começará em 3 segundos. Posicione o navegador na página de candidatos e NÃO o mova.")
            time.sleep(1); self.update_status("Capturando em 3..."); self.root.update_idletasks()
            time.sleep(1); self.update_status("Capturando em 2..."); self.root.update_idletasks()
            time.sleep(1); self.update_status("Capturando em 1..."); self.root.update_idletasks()
            
            self.candidate_extractor.candidates = []
            self.original_captured_candidates = []
            self.filtered_candidates = []
            if hasattr(self, 'ai_matched_candidate_details'):
                self.ai_matched_candidate_details = []

            self.update_results_display()

            all_candidates_data = self.bot.capture_candidates_with_cell_strategy()
            
            if self.candidate_extractor.candidates:
                self.original_captured_candidates = list(self.candidate_extractor.candidates)
                self.log(f"Lista original de {len(self.original_captured_candidates)} candidatos guardada para possível reset.")
            else:
                self.log("Nenhum candidato foi capturado pelo bot. Lista original permanece vazia.")

            self.log(f"Captura finalizada pela thread. Total de candidatos únicos encontrados: {len(all_candidates_data)}")
            
            self.update_results_display()
            
            if all_candidates_data:
                output_dir = "data"
                os.makedirs(output_dir, exist_ok=True)
                output_file = os.path.join(output_dir, "candidates_capturados.xlsx")
                try:
                    saved_xlsx = self.candidate_extractor.save_to_xlsx(output_file)
                    if saved_xlsx:
                        self.log(f"Dados salvos automaticamente em {saved_xlsx}")
                except Exception as e_save:
                    self.log(f"Erro ao salvar XLSX automaticamente: {e_save}")
            else:
                self.log("Nenhum candidato capturado para salvar em XLSX.")

        except Exception as e:
            self.log(f"Erro CRÍTICO na thread de captura: {str(e)}")
            self.log(f"Detalhes do erro: {traceback.format_exc()}")
            self.root.after(0, lambda: messagebox.showerror("Erro na Captura", 
                                                             f"Ocorreu um erro crítico durante a captura:\n{str(e)}\n\n"
                                                             "Consulte o log para detalhes."))
        finally:
            self.running = False
            self.root.after(0, lambda: self.capture_button.config(text="Iniciar Captura", state=tk.NORMAL))
            self.root.after(0, lambda: self.update_status("Pronto"))
            self.root.after(0, lambda: self.update_progress(100))

            
    
    def reset_to_original_capture(self):
        if not self.original_captured_candidates:
            messagebox.showinfo("Sem Captura Original", 
                                "Nenhuma lista de captura original foi guardada.")
            return
        
        if self.candidate_extractor.candidates == self.original_captured_candidates:
             messagebox.showinfo("Sem Alterações", 
                                "A lista atual já é a lista original capturada.")
             return

        confirm = messagebox.askyesno("Resetar Lista de Candidatos",
                                      f"Isto irá substituir a lista atual de {len(self.candidate_extractor.candidates)} candidatos "
                                      f"pela lista original capturada de {len(self.original_captured_candidates)} candidatos.\n\n"
                                      "Deseja continuar?")
        if confirm:
            self.candidate_extractor.candidates = list(self.original_captured_candidates)
            self.update_results_display()
            self.log("Lista de candidatos resetada para a captura original.")
            self.stats_var.set(f"Lista resetada para captura original. Total: {len(self.candidate_extractor.candidates)} candidatos.")
            
            self.filter_results_text.delete("1.0", tk.END)
            self.ai_matched_candidate_details = []
            
            self.notebook.select(self.results_tab)

    def reset_calibrations(self):
        result = messagebox.askyesno(
            "Confirmar Reset",
            "Tem certeza que deseja redefinir todas as calibrações?\n"
            "Esta ação não pode ser desfeita.",
            icon='warning'
        )
        
        if result:
            try:
                self.config_manager.reset_calibrations()
                self.update_calibration_status()
                messagebox.showinfo(
                    "Reset Concluído",
                    "As calibrações foram redefinidas com sucesso.\n"
                    "Use a aba 'Calibração' para definir novas regiões."
                )
            except Exception as e:
                messagebox.showerror(
                    "Erro",
                    f"Ocorreu um erro ao redefinir as calibrações:\n{str(e)}"
                )

if __name__ == "__main__":
    DEBUG_OUTPUT_DIR = "debug_files"
    
    os.makedirs("data", exist_ok=True)
    os.makedirs("templates", exist_ok=True)
    os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
    
    root = None
    app_instance = None
    try:
        root = tk.Tk()
        app_instance = SmartRecruiterGUI(root)
        
        def handle_exception(exc_type, exc_value, exc_tb):
            if issubclass(exc_type, KeyboardInterrupt):
                sys.__excepthook__(exc_type, exc_value, exc_tb)
                return
            
            error_msg_trace = ''.join(traceback.format_exception(exc_type, exc_value, exc_tb))
            print(f"EXCEÇÃO NÃO TRATADA:\n{error_msg_trace}")
            
            try:
                if root and app_instance:
                    app_instance.log(f"EXCEÇÃO NÃO TRATADA: {str(exc_value)}")
                    app_instance.log(error_msg_trace)
                    messagebox.showerror("Erro Inesperado na Aplicação", 
                        f"Ocorreu um erro crítico não tratado.\n\n"
                        f"Erro: {str(exc_value)}\n\nConsulte o log para detalhes.")
            except Exception as e_gui_err:
                print(f"Erro ao tentar mostrar exceção na GUI: {e_gui_err}")
        
        sys.excepthook = handle_exception
        
        root.mainloop()
    except Exception as e_main:
        print(f"Erro fatal ao iniciar a aplicação: {e_main}")
        print(traceback.format_exc())
    finally:
        print("Encerrando aplicação...")
