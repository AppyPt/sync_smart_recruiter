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
from orchestration_chain import CVMatchingOrchestrator

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
        self.azure_endpoint_var = tk.StringVar()
        self.azure_api_key_var = tk.StringVar()
        self.azure_deployment_var = tk.StringVar()
        self.azure_api_version_var = tk.StringVar()
        
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
    
    def setup_cv_analysis_tab(self):
        """Configura a aba de Análise de CVs."""
        cv_analysis_frame = self.cv_analysis_tab
        
        instruction_label = ttk.Label(
            cv_analysis_frame, 
            text="Esta funcionalidade analisa os CVs baixados para identificar os candidatos com melhor match.\n"
                "1. Insira os requisitos na área abaixo (os mesmos usados para filtrar candidatos).\n"
                "2. Selecione a pasta onde os CVs foram baixados.\n"
                "3. Clique em 'Analisar CVs' para iniciar o processo.\n",
            justify=tk.LEFT,
            wraplength=600
        )
        instruction_label.pack(anchor='w', padx=10, pady=10)
        
        # Área de requisitos
        req_frame = ttk.LabelFrame(cv_analysis_frame, text="Requisitos para Análise")
        req_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.cv_analysis_requirements = tk.Text(req_frame, height=5, wrap=tk.WORD)
        self.cv_analysis_requirements.pack(fill=tk.X, padx=5, pady=5)
        
        # Botão para copiar requisitos
        copy_btn = ttk.Button(
            req_frame, 
            text="Copiar Requisitos da Aba 'Filtrar com IA'",
            command=self.copy_filter_requirements
        )
        copy_btn.pack(anchor='e', padx=5, pady=5)
        
        # Seleção do diretório dos CVs
        cv_dir_frame = ttk.Frame(cv_analysis_frame)
        cv_dir_frame.pack(fill=tk.X, padx=10, pady=5)
        
        self.cv_dir_var = tk.StringVar()
        self.cv_dir_var.set(self.config_manager.get_setting("resume_download_directory", ""))
        
        ttk.Label(cv_dir_frame, text="Diretório dos CVs:").pack(side=tk.LEFT, padx=5)
        ttk.Entry(cv_dir_frame, textvariable=self.cv_dir_var, width=60).pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)
        ttk.Button(
            cv_dir_frame, 
            text="Procurar...",
            command=self.browse_cv_directory
        ).pack(side=tk.LEFT, padx=5)
        
        # Botões de ação
        btn_frame = ttk.Frame(cv_analysis_frame)
        btn_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.analyze_cvs_btn = ttk.Button(
            btn_frame, 
            text="Analisar CVs",
            command=self.start_cv_analysis
        )
        self.analyze_cvs_btn.pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            btn_frame,
            text="Abrir Relatório Mais Recente",
            command=self.open_latest_cv_report
        ).pack(side=tk.LEFT, padx=5)
        
        # Área de log/progresso
        log_frame = ttk.LabelFrame(cv_analysis_frame, text="Log de Análise")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        self.cv_analysis_log = tk.Text(log_frame, wrap=tk.WORD, height=15)
        self.cv_analysis_log.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(log_frame, command=self.cv_analysis_log.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.cv_analysis_log.config(yscrollcommand=scrollbar.set)
        
        # Barra de progresso
        progress_frame = ttk.Frame(cv_analysis_frame)
        progress_frame.pack(fill=tk.X, padx=10, pady=10)
        
        self.cv_analysis_progress_var = tk.DoubleVar(value=0)
        self.cv_analysis_progress = ttk.Progressbar(
            progress_frame,
            orient='horizontal',
            length=300,
            mode='indeterminate',
            variable=self.cv_analysis_progress_var
        )
        self.cv_analysis_progress.pack(fill=tk.X)

    def copy_filter_requirements(self):
        """Copia os requisitos da aba de filtro para a aba de análise de CVs."""
        if hasattr(self, 'role_description_text'):
            requirements = self.role_description_text.get("1.0", tk.END).strip()
            if requirements:
                self.cv_analysis_requirements.delete("1.0", tk.END)
                self.cv_analysis_requirements.insert("1.0", requirements)
                self.log("Requisitos copiados da aba 'Filtrar com IA'")
            else:
                messagebox.showinfo("Requisitos Vazios", "Não há requisitos definidos na aba 'Filtrar com IA'")

    def browse_cv_directory(self):
        """Abre diálogo para selecionar o diretório dos CVs."""
        directory = filedialog.askdirectory(
            title="Selecione o Diretório dos CVs",
            initialdir=self.cv_dir_var.get() or os.getcwd()
        )
        if directory:
            self.cv_dir_var.set(directory)
            self.log(f"Diretório de CVs selecionado: {directory}")

    def start_cv_analysis(self):
        """Inicia o processo de análise de CVs."""
        if self.running:
            messagebox.showinfo("Em execução", "Já existe um processo em andamento.")
            return
        
        # Verificar requisitos
        requirements = self.cv_analysis_requirements.get("1.0", tk.END).strip()
        if not requirements:
            messagebox.showwarning("Requisitos Necessários", "Por favor, insira os requisitos para análise.")
            return
        
        # Verificar diretório de CVs
        cv_directory = self.cv_dir_var.get()
        if not cv_directory or not os.path.isdir(cv_directory):
            messagebox.showwarning("Diretório Inválido", "Por favor, selecione um diretório válido com os CVs.")
            return
        
        # Verificar se há PDFs no diretório
        pdf_files = [f for f in os.listdir(cv_directory) if f.lower().endswith('.pdf')]
        if not pdf_files:
            messagebox.showwarning("Sem CVs", "Não foram encontrados arquivos PDF no diretório selecionado.")
            return
        
        # Verificar a configuração do Azure OpenAI
        endpoint = self.config_manager.get_setting("azure_endpoint")
        api_key = self.config_manager.get_setting("azure_api_key")
        deployment = self.config_manager.get_setting("azure_deployment")
        
        if not endpoint or not api_key or not deployment:
            messagebox.showwarning(
                "Configuração do Azure OpenAI",
                "Por favor, configure o Azure OpenAI na aba 'Configurações'"
            )
            return
        
        # Buscar dados de mapeamento de CV para nomes
        cv_mapping = {}
        resume_map_path = os.path.join(cv_directory, "resume_map.json")
        if os.path.exists(resume_map_path):
            try:
                with open(resume_map_path, 'r', encoding='utf-8') as f:
                    resume_map = json.load(f)
                    
                for filename, data in resume_map.items():
                    cv_mapping[filename] = data.get("candidate_name", "Unknown")
                
                self.log_cv_analysis(f"Encontrado mapeamento para {len(cv_mapping)} CVs")
            except Exception as e:
                self.log_cv_analysis(f"Erro ao carregar mapeamento de CVs: {e}")
        else:
            self.log_cv_analysis("Arquivo de mapeamento resume_map.json não encontrado.")
        
        # Inicializar cliente Azure OpenAI
        try:
            from azure_llm_client import AzureLLMClient
            azure_client = AzureLLMClient(
                azure_endpoint=endpoint,
                api_key=api_key,
                deployment_name=deployment,
                api_version=self.config_manager.get_setting("azure_api_version", "2024-05-01-preview")
            )
        except ImportError:
            messagebox.showerror("Erro de Importação", "Módulo azure_llm_client não encontrado.")
            return
        except Exception as e:
            messagebox.showerror("Erro do Cliente Azure", f"Erro ao inicializar o cliente Azure: {e}")
            return
        
        # Iniciar thread de análise
        self.running = True
        self.analyze_cvs_btn.config(state=tk.DISABLED)
        self.cv_analysis_progress.start()
        
        # Preparar parâmetros
        pdf_paths = [os.path.join(cv_directory, f) for f in pdf_files]
        
        # Criar diretório para relatórios
        reports_dir = os.path.join("data", "cv_analysis_reports")
        os.makedirs(reports_dir, exist_ok=True)
        
        # Nome do relatório
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        report_path = os.path.join(reports_dir, f"cv_analysis_{timestamp}.xlsx")
        
        # Iniciar thread
        thread = threading.Thread(
            target=self.cv_analysis_thread,
            args=(azure_client, requirements, pdf_paths, cv_mapping, report_path),
            name="CVAnalysisThread"
        )
        thread.daemon = True
        thread.start()

    def cv_analysis_thread(self, azure_client, requirements, pdf_paths, cv_mapping, report_path):
        """Thread for executing CV analysis."""
        try:
            self.log_cv_analysis("Starting CV analysis...")
            
            orchestrator = CVMatchingOrchestrator(
                azure_llm_client=azure_client,
                output_dir=os.path.dirname(report_path)
            )
            
            # Redirect orchestrator logs to GUI
            original_log_method = orchestrator.log
            orchestrator.log = lambda msg: self.root.after(0, lambda: self.log_cv_analysis(msg))
            
            # Analysis parameters
            analysis_params = {
                "chunk_size": 400,
                "chunk_overlap": 58,
                "similarity_threshold": 0.60,
                "k_neighbors": 7,
                "min_relevance_score": 0.4
            }
            
            self.log_cv_analysis(
                f"Analysis Parameters:\n"
                f"- Chunk Size: {analysis_params['chunk_size']}\n"
                f"- Chunk Overlap: {analysis_params['chunk_overlap']}\n"
                f"- Similarity Threshold: {analysis_params['similarity_threshold']}\n"
                f"- K Neighbors: {analysis_params['k_neighbors']}\n"
                f"- Min Relevance Score: {analysis_params['min_relevance_score']}"
            )

            result = orchestrator.run_full_pipeline(
                job_description=requirements,
                cv_file_paths=pdf_paths,
                cv_mapping=cv_mapping,
                output_path=report_path,
                **analysis_params
            )
            
            # Handle results
            if not result.get("success", False):
                error_msg = result.get("error", result.get("message", "Unknown error during analysis"))
                self.root.after(0, lambda: self.log_cv_analysis(f"ERROR/WARNING: {error_msg}"))
                if result.get("error"):
                    self.root.after(0, lambda: messagebox.showerror("Analysis Error", error_msg))
            else:
                self.config_manager.set_setting("latest_cv_analysis_report", result.get("report_path", ""))
                
                analyses = result.get("analyses", [])
                if analyses:
                    self.root.after(0, lambda: self.log_cv_analysis("\n=== ANALYSIS SUMMARY ==="))
                    for i, analysis in enumerate(analyses[:5], 1):
                        name = analysis.get("candidate_name", "Unknown")
                        score = analysis.get("overall_match_score", 0)
                        recommendation = analysis.get("recommendation", "No recommendation")
                        summary_msg = f"{i}. {name}: Score {score}/100 - {recommendation}"
                        self.root.after(0, lambda msg=summary_msg: self.log_cv_analysis(msg))
                
                success_msg = result.get("message", "Analysis completed!")
                if result.get("report_path"):
                    success_msg += f"\nReport saved at:\n{result.get('report_path', '')}"
                
                self.root.after(0, lambda: self.log_cv_analysis(success_msg))
                self.root.after(0, lambda: messagebox.showinfo("Analysis Complete", success_msg))
                
        except Exception as e:
            error_msg = f"CRITICAL ERROR in CV analysis thread: {str(e)}"
            traceback_str = traceback.format_exc()
            self.root.after(0, lambda: self.log_cv_analysis(error_msg))
            self.root.after(0, lambda: self.log_cv_analysis(traceback_str))
            self.root.after(0, lambda: messagebox.showerror(
                "Analysis Error", 
                f"A critical error occurred during analysis:\n{str(e)}\n\nCheck the log for details."
            ))
        finally:
            self.running = False
            self.root.after(0, lambda: self.analyze_cvs_btn.config(state=tk.NORMAL))
            self.root.after(0, lambda: self.cv_analysis_progress.stop())

    def log_cv_analysis(self, message):
        """Adiciona mensagem ao log de análise de CVs."""
        timestamp = time.strftime("%H:%M:%S")
        self.cv_analysis_log.insert(tk.END, f"[{timestamp}] {message}\n")
        self.cv_analysis_log.see(tk.END)
        self.root.update_idletasks()

    def open_latest_cv_report(self):
        """Abre o relatório de análise de CVs mais recente."""
        report_path = self.config_manager.get_setting("latest_cv_analysis_report", "")
        if not report_path or not os.path.exists(report_path):
            messagebox.showinfo("Relatório não Encontrado", 
                            "Nenhum relatório de análise recente encontrado.")
            return
        
        try:
            import subprocess
            import platform
            
            system = platform.system()
            if system == 'Windows':
                os.startfile(report_path)
            elif system == 'Darwin':
                subprocess.call(['open', report_path])
            else:
                subprocess.call(['xdg-open', report_path])
            
            self.log(f"Relatório aberto: {report_path}")
        except Exception as e:
            messagebox.showerror("Erro ao Abrir Relatório", 
                                f"Não foi possível abrir o relatório: {e}")
            self.log(f"Erro ao abrir relatório: {e}")
    
    def create_widgets(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        self.capture_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.capture_tab, text="Captura")
        
        self.calibration_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.calibration_tab, text="Calibração")
        
        self.results_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.results_tab, text="Resultados")

        self.filter_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.filter_tab, text="Filtrar com IA")
        
        self.cv_analysis_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.cv_analysis_tab, text="Análise de CVs")
        
        self.settings_tab = ttk.Frame(self.notebook)
        self.notebook.add(self.settings_tab, text="Configurações")
        
        self.setup_capture_tab()
        self.setup_calibration_tab()
        self.setup_results_tab()
        self.setup_filter_tab()
        self.setup_cv_analysis_tab()
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

        # --- Configurações do Azure OpenAI ---
        ttk.Label(settings_frame, text="--- Configurações do Azure OpenAI ---", 
                font=('Arial', 10, 'bold')).pack(pady=(15, 5), anchor='w', padx=5)

        azure_endpoint_frame = ttk.Frame(settings_frame)
        azure_endpoint_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(azure_endpoint_frame, text="Azure Endpoint:", width=20).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.azure_endpoint_entry = ttk.Entry(azure_endpoint_frame, textvariable=self.azure_endpoint_var, width=60)
        self.azure_endpoint_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        azure_key_frame = ttk.Frame(settings_frame)
        azure_key_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(azure_key_frame, text="Azure API Key:", width=20).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.azure_api_key_entry = ttk.Entry(azure_key_frame, textvariable=self.azure_api_key_var, width=60, show="*")
        self.azure_api_key_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

        azure_deployment_frame = ttk.Frame(settings_frame)
        azure_deployment_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(azure_deployment_frame, text="Azure Deployment Name:", width=20).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.azure_deployment_entry = ttk.Entry(azure_deployment_frame, textvariable=self.azure_deployment_var, width=60)
        self.azure_deployment_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)
        
        azure_apiversion_frame = ttk.Frame(settings_frame)
        azure_apiversion_frame.pack(fill=tk.X, padx=10, pady=3, anchor='w')
        ttk.Label(azure_apiversion_frame, text="Azure API Version:", width=20).pack(side=tk.LEFT, padx=(0,5), anchor='w')
        self.azure_api_version_entry = ttk.Entry(azure_apiversion_frame, textvariable=self.azure_api_version_var, width=60)
        self.azure_api_version_entry.pack(side=tk.LEFT, expand=True, fill=tk.X)

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
        self.azure_endpoint_var.set(self.config_manager.get_setting("azure_endpoint", ""))
        self.azure_api_key_var.set(self.config_manager.get_setting("azure_api_key", ""))
        self.azure_deployment_var.set(self.config_manager.get_setting("azure_deployment", ""))
        self.azure_api_version_var.set(self.config_manager.get_setting("azure_api_version", "2024-05-01-preview"))

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
        self.config_manager.set_setting("azure_endpoint", self.azure_endpoint_var.get())
        self.config_manager.set_setting("azure_api_key", self.azure_api_key_var.get())
        self.config_manager.set_setting("azure_deployment", self.azure_deployment_var.get())
        self.config_manager.set_setting("azure_api_version", self.azure_api_version_var.get())

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

    def setup_filter_tab(self):
        filter_frame = self.filter_tab
        
        description_frame = ttk.LabelFrame(filter_frame, text="Descrição/Keywords para Filtro")
        description_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.role_description_text = tk.Text(description_frame, height=5, wrap=tk.WORD)
        self.role_description_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        example_text = "Exemplo: Especialista em IAM (Identity Access Management) com experiência em Azure AD, OKTA ou solução similar"
        self.role_description_text.insert("1.0", example_text)
        self.role_description_text.bind("<FocusIn>", lambda e: self.role_description_text.delete("1.0", tk.END) if self.role_description_text.get("1.0", tk.END).strip() == example_text else None)
        
        btn_frame = ttk.Frame(filter_frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Filtrar com IA", command=self.filter_candidates).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(filter_frame, text="Aplicar Filtro de IA à Lista Principal", 
                command=self.apply_ai_filter_to_main_list).pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(filter_frame, text="Iniciar Interação com Perfis de IA",
                command=self.start_profile_interaction_thread).pack(fill=tk.X, padx=5, pady=(10,5))
        
        results_label = ttk.Label(filter_frame, text="Resultados do Filtro:")
        results_label.pack(anchor='w', padx=5, pady=(10,2))
        
        results_frame = ttk.Frame(filter_frame)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        self.filter_results_text = tk.Text(results_frame, wrap=tk.WORD, height=10)
        self.filter_results_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        filter_scrollbar = ttk.Scrollbar(results_frame, command=self.filter_results_text.yview)
        filter_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.filter_results_text.config(yscrollcommand=filter_scrollbar.set)

    def start_profile_interaction_thread(self):
        if self.running:
            messagebox.showinfo("Captura em Andamento", "Por favor, aguarde a conclusão da captura de tela antes de iniciar a interação com perfis.")
            return

        if self.interacting_with_profiles:
            messagebox.showinfo("Em Execução", "A interação com perfis já está em andamento.")
            return

        if not hasattr(self, 'ai_matched_candidate_details') or not self.ai_matched_candidate_details:
            messagebox.showinfo("Sem Candidatos da IA",
                                "Nenhum candidato foi selecionado pelo filtro de IA para interação.\n"
                                "Execute o filtro na aba 'Filtrar com IA' primeiro.")
            return

        required_regions_for_interaction = ["Lista de Candidatos", "Nome (Dentro da Célula)_rel_to_cell"]
        current_calibrated_regions = self.config_manager.get_regions()
        missing_regions = [r for r in required_regions_for_interaction if r not in current_calibrated_regions]

        if missing_regions:
            messagebox.showerror("Erro de Calibração para Interação",
                                 f"As seguintes regiões essenciais precisam ser calibradas: {', '.join(missing_regions)}.\n"
                                 "Vá para a aba 'Calibração'.")
            return

        self.interacting_with_profiles = True
        self.log("Iniciando interação com perfis da IA...")
        self.update_status("Interagindo com perfis...")

        candidates_to_process = list(self.ai_matched_candidate_details)

        thread = threading.Thread(target=self.profile_interaction_thread, args=(candidates_to_process,), name="ProfileInteractionThread")
        thread.daemon = True
        thread.start()

    def profile_interaction_thread(self, candidates_to_process):
        try:
            self.bot.interact_with_ai_filtered_candidates(candidates_to_process, self.log)
            self.root.after(0, lambda: self.log("Interação com perfis da IA concluída."))
        except Exception as e:
            error_msg = f"Erro CRÍTICO na thread de interação com perfis: {str(e)}"
            detailed_error = traceback.format_exc()
            self.root.after(0, lambda: self.log(error_msg))
            self.root.after(0, lambda: self.log(detailed_error))
            self.root.after(0, lambda: messagebox.showerror("Erro na Interação",
                                                             f"Ocorreu um erro crítico durante a interação:\n{str(e)}\n\n"
                                                             "Consulte o log para detalhes."))
        finally:
            self.interacting_with_profiles = False
            self.root.after(0, lambda: self.update_status("Pronto"))

    def filter_candidates(self):
        if not self.candidate_extractor.candidates:
            messagebox.showinfo("Sem Candidatos",
                            "Não há candidatos para filtrar. Faça uma captura primeiro.")
            return

        role_description = self.role_description_text.get("1.0", tk.END).strip()

        example_text = "Exemplo: Especialista em IAM (Identity Access Management) com experiência em Azure AD, OKTA ou solução similar"
        if role_description == example_text or not role_description:
            messagebox.showwarning("Descrição Necessária",
                                "Por favor, insira uma descrição ou keywords para filtrar os candidatos.")
            return

        endpoint = self.config_manager.get_setting("azure_endpoint")
        api_key = self.config_manager.get_setting("azure_api_key")
        deployment = self.config_manager.get_setting("azure_deployment")
        api_version = self.config_manager.get_setting("azure_api_version", "2024-05-01-preview")

        if not endpoint or not api_key or not deployment:
            messagebox.showwarning("Configuração Necessária",
                                "Configure o Azure OpenAI primeiro na aba 'Configurações'")
            return

        try:
            from azure_llm_client import AzureLLMClient
        except ImportError:
            messagebox.showerror("Erro de Importação", "Não foi possível encontrar o ficheiro 'azure_llm_client.py'.")
            self.log("ERRO: Falha ao importar AzureLLMClient.")
            return
            
        llm_client = AzureLLMClient(
            azure_endpoint=endpoint,
            api_key=api_key,
            deployment_name=deployment,
            api_version=api_version
        )

        self.filter_results_text.delete("1.0", tk.END)
        self.filter_results_text.insert(tk.END, "A contactar a IA para filtrar os candidatos... Por favor aguarde.")
        self.root.update_idletasks()

        result = llm_client.filter_candidates_by_description(
            self.candidate_extractor.candidates,
            role_description
        )

        self.filter_results_text.delete("1.0", tk.END)

        if "error" in result:
            self.filter_results_text.insert(tk.END, f"Erro ao filtrar com IA: {result['error']}\n")
            if "raw_response" in result and result["raw_response"]:
                self.filter_results_text.insert(tk.END, f"\n--- Resposta Bruta da API ---\n{result['raw_response']}")
            self.filtered_candidates = []
            if hasattr(self, 'ai_matched_candidate_details'):
                self.ai_matched_candidate_details = []
            return

        matched_profiles = result.get("matched_profiles", [])

        if not matched_profiles:
            self.filter_results_text.insert(tk.END, "Nenhum candidato correspondente encontrado com alta probabilidade pela IA.\n")
            self.filtered_candidates = []
            if hasattr(self, 'ai_matched_candidate_details'):
                self.ai_matched_candidate_details = []
            return

        self.filter_results_text.insert(tk.END, f"Candidatos com alta probabilidade de correspondência (segundo IA): {len(matched_profiles)}\n\n")

        extracted_names_for_show_filtered = []
        for candidate_profile in matched_profiles:
            name = candidate_profile.get("name", "Nome Desconhecido")
            profile_text = candidate_profile.get("profile", "Perfil não disponível")
            self.filter_results_text.insert(tk.END, f"Nome: {name}\nPerfil: {profile_text}\n\n")
            extracted_names_for_show_filtered.append(name)

        self.filtered_candidates = extracted_names_for_show_filtered

        if hasattr(self, 'ai_matched_candidate_details'):
            self.ai_matched_candidate_details = matched_profiles
        else:
            self.ai_matched_candidate_details = matched_profiles
            self.log("AVISO: self.ai_matched_candidate_details não foi inicializado no __init__.")

        raw_response = result.get("raw_response")
        if raw_response:
            self.filter_results_text.insert(tk.END, f"\n--- Resposta Bruta da API ---\n{raw_response}")

    def apply_ai_filter_to_main_list(self):
        if not hasattr(self, 'ai_matched_candidate_details') or not self.ai_matched_candidate_details:
            messagebox.showinfo("Nenhum Filtro da IA", 
                            "Nenhum candidato foi selecionado pelo filtro de IA para aplicar.\n"
                            "Execute o filtro na aba 'Filtrar com IA' primeiro.")
            return

        if not self.candidate_extractor.candidates:
            messagebox.showinfo("Lista Principal Vazia", 
                                "A lista principal de candidatos já está vazia.")
            return

        confirm = messagebox.askyesno("Confirmar Aplicação de Filtro à Lista Principal",
                                      f"Isto irá REFINAR a lista principal atual de {len(self.candidate_extractor.candidates)} candidatos, "
                                      f"mantendo APENAS os {len(self.ai_matched_candidate_details)} candidatos identificados pela IA.\n\n"
                                      "Deseja continuar?")
        if not confirm:
            return

        new_main_candidate_list = []
        current_candidates_map = {
            cand.get("name", "").strip().lower(): cand 
            for cand in self.candidate_extractor.candidates if cand.get("name", "").strip()
        }

        for candidate_from_ia in self.ai_matched_candidate_details:
            name_from_ia = candidate_from_ia.get("name", "").strip()
            profile_from_ia = candidate_from_ia.get("profile", "").strip()

            matched_in_current = current_candidates_map.get(name_from_ia.lower())

            if matched_in_current:
                new_main_candidate_list.append(matched_in_current)
            else:
                self.log(f"INFO: Candidato '{name_from_ia}' da IA não encontrado na lista atual. Adicionando com dados da IA.")
                new_main_candidate_list.append({"name": name_from_ia, "profile": profile_from_ia})
        
        if not new_main_candidate_list and self.ai_matched_candidate_details:
            messagebox.showwarning("Nenhuma Correspondência Efetiva",
                                   "Embora a IA tenha retornado candidatos, nenhum pôde ser mapeado.")
            return
        
        previous_count = len(self.candidate_extractor.candidates)
        self.candidate_extractor.candidates = new_main_candidate_list
        
        self.log(f"Filtro de IA aplicado à lista principal. Lista atualizada de {previous_count} para {len(self.candidate_extractor.candidates)} candidatos.")
        
        self.update_results_display()
        
        self.filter_results_text.delete("1.0", tk.END)
        self.filter_results_text.insert("1.0", "Filtro de IA aplicado à lista principal. "
                                               "A lista de resultados na aba 'Resultados' foi atualizada.")
        self.ai_matched_candidate_details = []
        
        self.notebook.select(self.results_tab)
        self.stats_var.set(f"Lista principal REFINADA pela IA. Total: {len(self.candidate_extractor.candidates)} candidatos.")
    
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
