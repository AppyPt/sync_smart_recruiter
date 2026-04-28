# main.py
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import threading
import time
import os
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
        self.root.title("SmartRecruiters ETL Control Center")
        
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
        
        # Configurações de download de resumos
        # self.resume_download_dir_var = tk.StringVar()
        # (Removida para limpeza de código)
        self.resume_link_text_var = tk.StringVar()

        # Variáveis para configurações gerais de captura
        self.scroll_interval_var = tk.DoubleVar(value=2.0)
        
        # Variáveis do ETL (Filtro de Datas)
        self.start_date_var = tk.StringVar()
        self.end_date_var = tk.StringVar()

        # ---> NOVAS VARIÁVEIS DE STORAGE:
        self.mongo_conn_str_var = tk.StringVar()
        self.mongo_db_name_var = tk.StringVar(value="deliveryai_etl")
        self.blob_conn_str_var = tk.StringVar()
        self.blob_container_var = tk.StringVar(value="cv-uploads")

        self.config_manager = ConfigManager()
        self.image_processor = ImageProcessor()
        
        # Verificar se o Tesseract está disponível nativamente no Linux (via PATH)
        self.tesseract_available = False
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

        self.original_captured_candidates = []
        
        self.running = False
        self.debug_var = tk.BooleanVar(value=False)

        self.create_widgets()
        self.load_settings_to_ui()
        self.update_status("Pronto")
    
    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.capture_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.capture_tab, text="Captura (ETL)")
        
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
            text="Pipeline de Extração de Candidatos (ETL).\n"
                "1. Configure os parâmetros do período que deseja extrair.\n"
                "2. Garanta que a região da lista está calibrada.\n"
                "3. Clique em 'Iniciar Captura' e não mova o rato.\n",
            justify=tk.LEFT,
            wraplength=600
        )
        instruction_label.pack(anchor='w', padx=10, pady=10)

        main_capture_frame = ttk.Frame(capture_frame)
        main_capture_frame.pack(fill=tk.BOTH, padx=10, pady=10, expand=True)
        
        # --- PARÂMETROS DO ETL ---
        etl_frame = ttk.LabelFrame(main_capture_frame, text="Parâmetros de Extração")
        etl_frame.pack(fill=tk.X, pady=(0, 15))
        
        date_frame = ttk.Frame(etl_frame)
        date_frame.pack(fill=tk.X, padx=10, pady=10)
        
        ttk.Label(date_frame, text="Data Início (DD/MM/AAAA):").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        ttk.Entry(date_frame, textvariable=self.start_date_var, width=15).grid(row=0, column=1, padx=5, pady=5)
        
        ttk.Label(date_frame, text="Data Fim (DD/MM/AAAA):").grid(row=0, column=2, padx=15, pady=5, sticky=tk.W)
        ttk.Entry(date_frame, textvariable=self.end_date_var, width=15).grid(row=0, column=3, padx=5, pady=5)

        # --- BOTÕES ---
        top_options_frame = ttk.Frame(main_capture_frame)
        top_options_frame.pack(fill=tk.X, pady=(0, 10))
        
        buttons_frame = ttk.Frame(top_options_frame)
        buttons_frame.pack(side=tk.LEFT, padx=(0, 10))
        
        self.capture_button = ttk.Button(buttons_frame, text="Iniciar Captura", command=self.start_capture)
        self.capture_button.pack(side=tk.LEFT, padx=(0, 5))
        
        # ---> NOVO BOTÃO AQUI:
        self.stop_button = ttk.Button(buttons_frame, text="Parar Captura", command=self.stop_capture, state=tk.DISABLED)
        self.stop_button.pack(side=tk.LEFT, padx=5)
        
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
        
        log_frame = ttk.LabelFrame(main_capture_frame, text="Logs do Sistema")
        log_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        self.log_text = tk.Text(log_frame, wrap=tk.WORD, height=15)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        log_scrollbar = ttk.Scrollbar(log_frame, command=self.log_text.yview)
        log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=log_scrollbar.set)

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
        
        table_frame = ttk.LabelFrame(main_frame, text="Candidatos Capturados")
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
        
        ttk.Button(buttons_frame, text="Limpar Resultados", command=self.clear_results).pack(side=tk.LEFT, padx=5)
        ttk.Button(buttons_frame, text="Atualizar Tabela", command=self.update_results_display).pack(side=tk.LEFT, padx=5)


    def clear_results(self):
        if messagebox.askyesno("Limpar Resultados", "Tem certeza que deseja limpar todos os resultados?"):
            self.candidate_extractor.candidates = []
            self.update_results_display()
            self.log("Resultados limpos.")

    def update_results_display(self): 
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

        ttk.Label(settings_frame, text="--- Configurações de Download de CVs ---", 
                font=('Arial', 10, 'bold')).pack(pady=(15, 5), anchor='w', padx=5)

        # dir_frame = ttk.Frame(settings_frame)
        # dir_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        # ttk.Label(dir_frame, text="Diretório de Download:", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        # self.resume_download_dir_entry = ttk.Entry(dir_frame, textvariable=self.resume_download_dir_var, width=50)
        # self.resume_download_dir_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        # ttk.Button(dir_frame, text="Procurar...", command=self.browse_resume_download_directory).pack(side=tk.LEFT, padx=(5,0))

        link_text_frame = ttk.Frame(settings_frame)
        link_text_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(link_text_frame, text="Texto do Link do Resumo:", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.resume_link_text_entry = ttk.Entry(link_text_frame, textvariable=self.resume_link_text_var, width=40)
        self.resume_link_text_entry.pack(side=tk.LEFT)

        
        ttk.Label(settings_frame, text="--- Configurações Gerais de Captura ---", 
                font=('Arial', 10, 'bold')).pack(pady=(15, 5), anchor='w', padx=5)


        scroll_interval_frame = ttk.Frame(settings_frame)
        scroll_interval_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(scroll_interval_frame, text="Intervalo entre Scrolls (segundos):", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.scroll_interval_spinbox = ttk.Spinbox(scroll_interval_frame, from_=0.1, to=10.0, increment=0.1,
                                                textvariable=self.scroll_interval_var, width=5, format="%.1f")
        self.scroll_interval_spinbox.pack(side=tk.LEFT)

        # --- NOVO BLOCO: CREDENCIAIS DE STORAGE ---
        ttk.Label(settings_frame, text="--- Credenciais de Armazenamento (ETL) ---", 
                font=('Arial', 10, 'bold')).pack(pady=(20, 5), anchor='w', padx=5)

        # MongoDB Connection String
        mongo_frame = ttk.Frame(settings_frame)
        mongo_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(mongo_frame, text="MongoDB Connection String:", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.mongo_conn_entry = ttk.Entry(mongo_frame, textvariable=self.mongo_conn_str_var, width=60, show="*") # show="*" esconde a password
        self.mongo_conn_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # MongoDB Database Name
        db_frame = ttk.Frame(settings_frame)
        db_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(db_frame, text="MongoDB Database Name:", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.mongo_db_entry = ttk.Entry(db_frame, textvariable=self.mongo_db_name_var, width=30)
        self.mongo_db_entry.pack(side=tk.LEFT)

        # Azure Blob Connection String
        blob_frame = ttk.Frame(settings_frame)
        blob_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(blob_frame, text="Azure Blob Connection String:", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.blob_conn_entry = ttk.Entry(blob_frame, textvariable=self.blob_conn_str_var, width=60, show="*")
        self.blob_conn_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        # Azure Blob Container Name
        container_frame = ttk.Frame(settings_frame)
        container_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(container_frame, text="Azure Blob Container Name:", width=30).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.blob_container_entry = ttk.Entry(container_frame, textvariable=self.blob_container_var, width=30)
        self.blob_container_entry.pack(side=tk.LEFT)
        # ------------------------------------------

        save_button_settings = ttk.Button(settings_frame, text="Salvar Todas as Configurações", command=self.save_settings)
        save_button_settings.pack(pady=20, padx=10, anchor='center')

    def load_settings_to_ui(self):
        self.start_date_var.set(self.config_manager.get_setting("etl_start_date", ""))
        self.end_date_var.set(self.config_manager.get_setting("etl_end_date", ""))

        default_download_dir = os.path.join(os.getcwd(), "downloaded_resumes")
        # self.resume_download_dir_var.set(self.config_manager.get_setting("resume_download_directory", default_download_dir))
        self.resume_link_text_var.set(self.config_manager.get_setting("resume_link_text", "Latest Resume"))
        
        
        try:
            self.scroll_interval_var.set(float(self.config_manager.get_setting("scroll_interval", 2.0)))
        except (ValueError, TypeError):
            self.scroll_interval_var.set(2.0)

        # ---> CARREGAR STORAGE
        self.mongo_conn_str_var.set(self.config_manager.get_setting("mongo_connection_string", ""))
        self.mongo_db_name_var.set(self.config_manager.get_setting("mongo_db_name", "deliveryai_etl"))
        self.blob_conn_str_var.set(self.config_manager.get_setting("azure_blob_connection_string", ""))
        self.blob_container_var.set(self.config_manager.get_setting("azure_blob_container_name", "cv-uploads"))

        self.log("Configurações carregadas para a UI.")

    def browse_resume_download_directory(self):
        directory = filedialog.askdirectory(title="Selecione o Diretório para Download de Resumos")
        if directory:
            self.resume_download_dir_var.set(directory)
            self.log(f"Diretório selecionado: {directory}")

    def save_settings(self):
        # Guardar as datas no config manager
        self.config_manager.set_setting("etl_start_date", self.start_date_var.get())
        self.config_manager.set_setting("etl_end_date", self.end_date_var.get())
        
        # Validar se o Tesseract continua acessível no sistema
        try:
            import pytesseract
            pytesseract.get_tesseract_version()
            self.tesseract_available = True
        except Exception:
            self.tesseract_available = False
            messagebox.showwarning("Aviso", "O Tesseract OCR não foi encontrado no sistema.\nPor favor, certifique-se de que o instalou com: sudo apt-get install tesseract-ocr")

        # self.config_manager.set_setting("resume_download_directory", self.resume_download_dir_var.get())
        self.config_manager.set_setting("resume_link_text", self.resume_link_text_var.get())
        
        
        try:
            self.config_manager.set_setting("scroll_interval", float(self.scroll_interval_var.get()))
        except ValueError:
            pass

        # ---> GUARDAR STORAGE
        self.config_manager.set_setting("mongo_connection_string", self.mongo_conn_str_var.get())
        self.config_manager.set_setting("mongo_db_name", self.mongo_db_name_var.get())
        self.config_manager.set_setting("azure_blob_connection_string", self.blob_conn_str_var.get())
        self.config_manager.set_setting("azure_blob_container_name", self.blob_container_var.get())

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
                    self.calibration_status_text.insert(tk.END, f"{name}: offset_x={region.get('offset_x', region.get('left', 0))}, offset_y={region.get('offset_y', region.get('top', 0))}, w={region.get('width', 0)}, h={region.get('height', 0)}\n")
                else:
                    self.calibration_status_text.insert(tk.END, f"{name}: left={region.get('left', 0)}, top={region.get('top', 0)}, w={region.get('width', 0)}, h={region.get('height', 0)}\n")
                    
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
    
    def show_panic_window(self):
        """Cria um botão de pânico flutuante e sempre no topo."""
        if hasattr(self, 'panic_win') and self.panic_win and self.panic_win.winfo_exists():
            return

        self.panic_win = tk.Toplevel(self.root)
        self.panic_win.title("Pânico")
        self.panic_win.geometry("160x50+10+10") # Canto superior esquerdo
        self.panic_win.attributes("-topmost", True) # Fica por cima do Chrome
        self.panic_win.overrideredirect(True) # Remove barra superior

        frame = tk.Frame(self.panic_win, highlightbackground="darkred", highlightthickness=3)
        frame.pack(fill=tk.BOTH, expand=True)

        self.panic_btn = tk.Button(
            frame, text="🛑 PARAR ROBÔ", bg="red", fg="white", 
            font=("Arial", 10, "bold"), command=self.stop_capture
        )
        self.panic_btn.pack(fill=tk.BOTH, expand=True)

    def hide_panic_window(self):
        """Esconde e destrói o botão flutuante de pânico."""
        if hasattr(self, 'panic_win') and self.panic_win and self.panic_win.winfo_exists():
            self.panic_win.destroy()
            self.panic_win = None

    def stop_capture(self):
        """Sinaliza a thread do bot para parar a execução."""
        if self.running:
            self.bot.stop_requested = True
            self.log("🛑 SINAL DE PARAGEM ENVIADO! O robô vai parar no próximo ciclo...")
            self.update_status("A parar...")
            self.stop_button.config(state=tk.DISABLED)
            
            if hasattr(self, 'panic_btn') and self.panic_btn.winfo_exists():
                self.panic_btn.config(text="A PARAR...", bg="orange", state=tk.DISABLED)

    def start_capture(self):
        if self.running:
            messagebox.showinfo("Em execução", "Já existe uma captura em andamento.")
            return
        
        if not self.tesseract_available:
            messagebox.showerror("Tesseract não encontrado", "Configure o Tesseract OCR.")
            return
        
        required_regions = ["Lista de Candidatos"]
        current_calibrated_regions = self.config_manager.get_regions()
        missing_regions = [r for r in required_regions if r not in current_calibrated_regions]
        if missing_regions:
            messagebox.showerror("Erro de Calibração", f"Regiões em falta: {', '.join(missing_regions)}.")
            return
            
        start_date = self.start_date_var.get().strip()
        end_date = self.end_date_var.get().strip()
        
        self.log(f"Iniciando ETL. Período: {start_date if start_date else 'Início'} a {end_date if end_date else 'Fim'}")
        
        # Guarda as datas na config antes de correr para o bot poder aceder se necessário
        self.config_manager.set_setting("etl_start_date", start_date)
        self.config_manager.set_setting("etl_end_date", end_date)
        
        self.running = True
        self.bot.stop_requested = False # <--- GARANTIR QUE A VARIÁVEL ESTÁ LIMPA
        self.update_status("Capturando candidatos...")
        self.capture_button.config(text="Capturando...", state=tk.DISABLED)
        self.stop_button.config(state=tk.NORMAL) # <--- ATIVAR O BOTÃO DE PARAR NORMAL
        self.update_status("Capturando candidatos...")
        self.capture_button.config(text="Capturando...", state=tk.DISABLED)
        
        try:
            self.bot.scroll_interval = float(self.scroll_interval_var.get())
        except ValueError:
            self.bot.scroll_interval = 2.0

        thread = threading.Thread(target=self.capture_thread, name="CaptureThread")
        thread.daemon = True
        thread.start()
    
    def capture_thread(self):
        try:
            debug_mode = self.debug_var.get()
            if hasattr(self.image_processor, 'debug'):
                 self.image_processor.debug = debug_mode
            else:
                 setattr(self.image_processor, 'debug', debug_mode)
            
            self.log("A captura começará em 3 segundos. NÃO mova o rato.")
            time.sleep(1); self.update_status("Capturando em 3..."); self.root.update_idletasks()
            time.sleep(1); self.update_status("Capturando em 2..."); self.root.update_idletasks()
            time.sleep(1); self.update_status("Capturando em 1..."); self.root.update_idletasks()
            
            # ---> MOSTRAR O BOTÃO DE PÂNICO NO ECRÃ
            self.root.after(0, self.show_panic_window)
            
            self.candidate_extractor.candidates = []
            self.update_results_display()

            all_candidates_data = self.bot.capture_candidates_with_cell_strategy()
            
            # TODO: Mais tarde, aqui podemos injetar a lógica de ler a Data da linha do candidato
            # para decidir se a iteração/scroll deve parar com base no start_date e end_date.

            self.log(f"Captura finalizada. Total de candidatos: {len(all_candidates_data)}")
            self.update_results_display()
            
            if all_candidates_data:
                # Onde futuramente vamos chamar a lógica para enviar para o MongoDB
                self.log("Dados mantidos em memória. Prontos para a próxima fase do ETL.")

        except Exception as e:
            self.log(f"Erro CRÍTICO: {str(e)}")
            self.root.after(0, lambda: messagebox.showerror("Erro na Captura", str(e)))
        finally:
            self.running = False
            self.root.after(0, lambda: self.capture_button.config(text="Iniciar Captura", state=tk.NORMAL))
            self.root.after(0, lambda: self.stop_button.config(state=tk.DISABLED)) # <--- DESATIVA O BOTÃO NORMAL
            self.root.after(0, self.hide_panic_window) # <--- DESTRÓI A JANELA DE PÂNICO
            self.root.after(0, lambda: self.update_status("Pronto"))
            self.root.after(0, lambda: self.update_progress(100))

    def reset_calibrations(self):
        result = messagebox.askyesno(
            "Confirmar Reset",
            "Tem certeza que deseja redefinir todas as calibrações?\nEsta ação não pode ser desfeita.",
            icon='warning'
        )
        if result:
            try:
                self.config_manager.reset_calibrations()
                self.update_calibration_status()
                messagebox.showinfo("Reset Concluído", "Calibrações redefinidas.")
            except Exception as e:
                messagebox.showerror("Erro", str(e))

if __name__ == "__main__":
    DEBUG_OUTPUT_DIR = "debug_files"
    os.makedirs("data", exist_ok=True)
    os.makedirs(DEBUG_OUTPUT_DIR, exist_ok=True)
    
    root = tk.Tk()
    app_instance = SmartRecruiterGUI(root)
    root.mainloop()