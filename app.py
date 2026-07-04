import os
import logging
import ollama
import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
from pathlib import Path
from datetime import datetime
import threading
import webbrowser
from core import Config, VectorStore, Database, DocumentProcessor, detect_hardware
from smolagent_helper import KnowledgeAgent
from search_engine import DualSearchEngine, CrossLocationFinder

os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# Design System Colors from DESIGN.md
COLORS = {
    'surface': '#faf8ff',
    'surface_container_low': '#f3f3fe',
    'surface_container': '#ededf9',
    'surface_container_high': '#e7e7f3',
    'surface_container_highest': '#e1e2ed',
    'on_surface': '#191b23',
    'on_surface_variant': '#434655',
    'outline': '#737686',
    'outline_variant': '#c3c6d7',
    'primary': '#004ac6',
    'on_primary': '#ffffff',
    'primary_container': '#2563eb',
    'on_primary_container': '#eeefff',
    'secondary_container': '#d5e3fd',
    'background': '#faf8ff',
    'error': '#ba1a1a',
    'on_error': '#ffffff',
    'white': '#ffffff',
    'success': '#22c55e'
}


class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Cognitive AI - Local Knowledge Workspace")
        self.root.geometry("1400x900")
        self.root.minsize(1200, 700)
        self.root.configure(bg=COLORS['background'])
        
        self.config = Config()
        self._auto_configure_model()
        self.db = Database(self.config.paths['database'])
        self.vector_store = VectorStore(self.config)
        self.doc_processor = DocumentProcessor(self.config)
        self.ollama_client = ollama.Client(host=self.config.ollama['host'])
        self.knowledge_agent = KnowledgeAgent(self.config)
        self.search_engine = DualSearchEngine(self.config)
        self.cross_finder = CrossLocationFinder(self.config)
        self._cached_search_results = []
        
        # Active document for chat context
        self.active_document = None
        self._drag_data = None
        
        # Status flags
        self.ollama_connected = False
        self.faiss_ready = False
        self.db_ready = False
        self.folder_watcher_ready = False
        self.documents_cache = []
        
        self.setup_ui()
        self.check_system_status()
        self.refresh_document_list()
    
    def setup_ui(self):
        # Main container
        main_container = tk.Frame(self.root, bg=COLORS['background'])
        main_container.pack(fill=tk.BOTH, expand=True)
        
        # Top header bar
        self.create_header_bar(main_container)
        
        # Content area with split view
        content_area = tk.Frame(main_container, bg=COLORS['background'])
        content_area.pack(fill=tk.BOTH, expand=True, padx=16, pady=(0, 16))
        
        # Left: Sidebar
        self.create_sidebar(content_area)
        
        # Right: PanedWindow for split view
        self.right_pane = ttk.PanedWindow(content_area, orient=tk.HORIZONTAL)
        self.right_pane.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Right: Left panel - Document Viewer
        self.viewer_frame = tk.Frame(self.right_pane, bg=COLORS['surface'])
        self.right_pane.add(self.viewer_frame, weight=1)
        self.create_document_viewer(self.viewer_frame)
        self.viewer_visible = True
        
        # Right: Right panel - Chat
        chat_frame = tk.Frame(self.right_pane, bg=COLORS['surface'])
        self.right_pane.add(chat_frame, weight=2)
        self.create_chat_area(chat_frame)
        
        # Status bar at bottom
        self.create_status_bar(main_container)
    
    def create_header_bar(self, parent):
        header = tk.Frame(parent, bg=COLORS['white'], height=70, 
                         highlightbackground=COLORS['outline_variant'],
                         highlightthickness=1)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        
        # Logo and title
        logo_frame = tk.Frame(header, bg=COLORS['white'])
        logo_frame.pack(side=tk.LEFT, padx=24, pady=16)
        
        logo_icon = tk.Canvas(logo_frame, width=36, height=36, bg=COLORS['primary'], 
                             highlightthickness=0)
        logo_icon.create_oval(8, 8, 28, 28, fill=COLORS['white'], outline='')
        logo_icon.pack(side=tk.LEFT)
        
        tk.Label(logo_frame, text="Cognitive AI", 
                font=("Inter", 18, "bold"), fg=COLORS['primary'],
                bg=COLORS['white']).pack(side=tk.LEFT, padx=(12, 4))
        
        tk.Label(logo_frame, text="Knowledge Partner", 
                font=("Inter", 12), fg=COLORS['on_surface_variant'],
                bg=COLORS['white']).pack(side=tk.LEFT)
        
        # Search box
        search_frame = tk.Frame(header, bg=COLORS['surface_container_low'], 
                               highlightbackground=COLORS['outline_variant'],
                               highlightthickness=1)
        search_frame.pack(side=tk.LEFT, padx=40, pady=16, fill=tk.X, expand=True)
        
        self.search_var = tk.StringVar()
        self.search_var.trace('w', self.on_search_change)
        
        self.search_entry = tk.Entry(search_frame, 
                                    textvariable=self.search_var,
                                    bg=COLORS['surface_container_low'],
                                    fg=COLORS['on_surface'],
                                    font=("Inter", 12),
                                    insertbackground=COLORS['primary'],
                                    relief=tk.FLAT,
                                    borderwidth=0)
        self.search_entry.pack(side=tk.LEFT, padx=16, pady=8, fill=tk.X, expand=True)
        self.search_entry.insert(0, "🔍 Search documents...")
        self.search_entry.config(fg=COLORS['outline'])
        self.search_entry.bind('<FocusIn>', self._clear_search_placeholder)
        self.search_entry.bind('<FocusOut>', self._restore_search_placeholder)
        self.search_entry.bind('<Return>', self.perform_search)
        
        # Action buttons
        buttons_frame = tk.Frame(header, bg=COLORS['white'])
        buttons_frame.pack(side=tk.RIGHT, padx=24, pady=16)
        
        add_folder_btn = tk.Button(buttons_frame, text="📁 Import Folder", 
                                  command=self.add_folder,
                                  bg=COLORS['primary'], fg=COLORS['white'],
                                  font=("Inter", 11, "bold"),
                                  activebackground=COLORS['primary_container'],
                                  activeforeground=COLORS['white'],
                                  relief=tk.FLAT, cursor='hand2',
                                  padx=16, pady=10)
        add_folder_btn.pack(side=tk.LEFT, padx=(0, 12))
        
        add_file_btn = tk.Button(buttons_frame, text="+ Add File", 
                                command=self.add_file,
                                bg=COLORS['surface_container'], fg=COLORS['primary'],
                                font=("Inter", 11, "bold"),
                                activebackground=COLORS['surface_container_high'],
                                activeforeground=COLORS['primary'],
                                relief=tk.FLAT, cursor='hand2',
                                padx=16, pady=10)
        add_file_btn.pack(side=tk.LEFT, padx=(0, 12))
        
        reset_btn = tk.Button(buttons_frame, text="Reset", 
                             command=self.reset_store,
                             bg=COLORS['surface_container_low'], fg=COLORS['error'],
                             font=("Inter", 10),
                             activebackground=COLORS['surface_container_high'],
                             activeforeground=COLORS['error'],
                             relief=tk.FLAT, cursor='hand2',
                             padx=16, pady=10)
        reset_btn.pack(side=tk.LEFT)
        
        toggle_viewer_btn = tk.Button(buttons_frame, text="📖 Viewer", 
                                     command=self.toggle_viewer,
                                     bg=COLORS['surface_container'], fg=COLORS['primary'],
                                     font=("Inter", 10),
                                     activebackground=COLORS['surface_container_high'],
                                     activeforeground=COLORS['primary'],
                                     relief=tk.FLAT, cursor='hand2',
                                     padx=16, pady=10)
        toggle_viewer_btn.pack(side=tk.RIGHT, padx=(12, 0))
    
    def create_sidebar(self, parent):
        sidebar = tk.Frame(parent, bg=COLORS['surface_container_low'], width=280,
                          highlightbackground=COLORS['outline_variant'],
                          highlightthickness=1)
        sidebar.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 16))
        sidebar.pack_propagate(False)
        
        # ── Search Section ──
        search_header = tk.Frame(sidebar, bg=COLORS['surface_container_low'])
        search_header.pack(fill=tk.X, padx=16, pady=(16, 8))
        tk.Label(search_header, text="Search Files", 
                font=("Inter", 13, "bold"), fg=COLORS['on_surface'],
                bg=COLORS['surface_container_low']).pack(side=tk.LEFT)
        
        # Search input
        search_input_frame = tk.Frame(sidebar, bg=COLORS['white'],
                                     highlightbackground=COLORS['outline_variant'],
                                     highlightthickness=1)
        search_input_frame.pack(fill=tk.X, padx=12, pady=(0, 6))
        
        self.search_entry = tk.Entry(search_input_frame,
                                    bg=COLORS['white'], fg=COLORS['on_surface'],
                                    font=("Inter", 11),
                                    relief=tk.FLAT, borderwidth=0)
        self.search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=12, pady=10)
        self.search_entry.insert(0, "Search keyword...")
        self.search_entry.config(fg=COLORS['outline'])
        self.search_entry.bind('<FocusIn>', lambda e: self._search_focus_in())
        self.search_entry.bind('<FocusOut>', lambda e: self._search_focus_out())
        self.search_entry.bind('<Return>', lambda e: self._run_search())
        
        search_btn = tk.Button(search_input_frame, text="🔍",
                              command=self._run_search,
                              bg=COLORS['white'], fg=COLORS['primary'],
                              font=("Inter", 12),
                              relief=tk.FLAT, cursor='hand2',
                              padx=10, pady=6)
        search_btn.pack(side=tk.RIGHT)
        
        # Search mode toggle
        mode_frame = tk.Frame(sidebar, bg=COLORS['surface_container_low'])
        mode_frame.pack(fill=tk.X, padx=12, pady=(0, 4))
        
        self.search_mode = tk.StringVar(value=self.config.search.get('default_mode', 'quick'))
        
        quick_rb = tk.Radiobutton(mode_frame, text="Quick (no AI)", variable=self.search_mode,
                                 value='quick', font=("Inter", 9),
                                 fg=COLORS['on_surface_variant'],
                                 bg=COLORS['surface_container_low'],
                                 selectcolor=COLORS['white'],
                                 activebackground=COLORS['surface_container_low'])
        quick_rb.pack(side=tk.LEFT, padx=(0, 8))
        
        smart_rb = tk.Radiobutton(mode_frame, text="Smart (+AI summary)", variable=self.search_mode,
                                 value='smart', font=("Inter", 9),
                                 fg=COLORS['on_surface_variant'],
                                 bg=COLORS['surface_container_low'],
                                 selectcolor=COLORS['white'],
                                 activebackground=COLORS['surface_container_low'])
        smart_rb.pack(side=tk.LEFT)
        
        # Browse storage button
        browse_btn = tk.Button(sidebar, text="📂 Browse Storage",
                              command=self._browse_storage,
                              bg=COLORS['surface_container'], fg=COLORS['primary'],
                              font=("Inter", 10),
                              relief=tk.FLAT, cursor='hand2',
                              padx=12, pady=6)
        browse_btn.pack(fill=tk.X, padx=12, pady=(0, 8))
        
        # Search results list
        results_container = tk.Frame(sidebar, bg=COLORS['surface_container'])
        results_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 4))
        
        self.search_results_list = tk.Listbox(results_container, bg=COLORS['white'],
                                             fg=COLORS['on_surface_variant'],
                                             font=("Inter", 9),
                                             selectbackground=COLORS['secondary_container'],
                                             selectforeground=COLORS['primary'],
                                             relief=tk.FLAT,
                                             borderwidth=0, highlightthickness=0,
                                             activestyle='none')
        self.search_results_list.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)
        self.search_results_list.bind('<Double-Button-1>', self._open_search_result)
        
        self.search_status = tk.Label(sidebar, text="", font=("Inter", 8),
                                     fg=COLORS['on_surface_variant'],
                                     bg=COLORS['surface_container_low'])
        self.search_status.pack(fill=tk.X, padx=12, pady=(0, 4))
        
        # ── Separator ──
        sep = tk.Frame(sidebar, bg=COLORS['outline_variant'], height=1)
        sep.pack(fill=tk.X, padx=12, pady=4)
        
        # Documents section header
        docs_header = tk.Frame(sidebar, bg=COLORS['surface_container_low'])
        docs_header.pack(fill=tk.X, padx=16, pady=(8, 12))
        
        tk.Label(docs_header, text="Documents", 
                font=("Inter", 14, "bold"), fg=COLORS['on_surface'],
                bg=COLORS['surface_container_low']).pack(side=tk.LEFT)
        
        # Document list
        list_container = tk.Frame(sidebar, bg=COLORS['surface_container'])
        list_container.pack(fill=tk.BOTH, expand=True, padx=12, pady=(0, 12))
        
        self.doc_listbox = tk.Listbox(list_container, bg=COLORS['white'], 
                                     fg=COLORS['on_surface_variant'],
                                     font=("Inter", 11),
                                     selectbackground=COLORS['secondary_container'],
                                     selectforeground=COLORS['primary'],
                                     relief=tk.FLAT,
                                     borderwidth=0, highlightthickness=0,
                                     activestyle='none')
        self.doc_listbox.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.doc_listbox.bind('<<ListboxSelect>>', self.connect_document)
        self.doc_listbox.bind('<Double-Button-1>', self.open_document)
        # Drag-and-drop: track drag start for visual feedback
        self.doc_listbox.bind('<ButtonPress-1>', self._drag_start)
        self.doc_listbox.bind('<B1-Motion>', self._drag_motion)
        self.doc_listbox.bind('<ButtonRelease-1>', self._drag_end)
    
    def create_chat_area(self, parent):
        chat_container = tk.Frame(parent, bg=COLORS['surface'])
        chat_container.pack(fill=tk.BOTH, expand=True)
        
        # Chat display area
        chat_display_frame = tk.Frame(chat_container, bg=COLORS['surface'])
        chat_display_frame.pack(fill=tk.BOTH, expand=True, padx=24, pady=24)
        
        # Chat canvas with scrollbar
        self.chat_canvas = tk.Canvas(chat_display_frame, bg=COLORS['surface'], highlightthickness=0)
        scrollbar = tk.Scrollbar(chat_display_frame, orient=tk.VERTICAL, command=self.chat_canvas.yview)
        self.chat_frame = tk.Frame(self.chat_canvas, bg=COLORS['surface'])
        
        self.chat_frame.bind(
            "<Configure>",
            lambda e: self.chat_canvas.configure(scrollregion=self.chat_canvas.bbox("all"))
        )
        
        self.chat_canvas.create_window((0, 0), window=self.chat_frame, anchor="nw", width=950)
        self.chat_canvas.configure(yscrollcommand=scrollbar.set)
        
        self.chat_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Input area
        input_container = tk.Frame(parent, bg=COLORS['background'],
                                  highlightbackground=COLORS['outline_variant'],
                                  highlightthickness=1)
        input_container.pack(fill=tk.X, side=tk.BOTTOM)
        
        input_inner_frame = tk.Frame(input_container, bg=COLORS['background'])
        input_inner_frame.pack(fill=tk.X, padx=24, pady=(8, 16))
        
        # Connected document label
        self.connected_doc_label = tk.Label(input_inner_frame, text="", 
                                           font=("Inter", 9), fg=COLORS['primary'],
                                           bg=COLORS['background'], anchor=tk.W,
                                           cursor="hand2")
        self.connected_doc_label.bind('<Button-1>', lambda e: self._disconnect_document())
        self.connected_doc_label.pack(fill=tk.X, pady=(0, 4))
        
        input_field_container = tk.Frame(input_inner_frame, bg=COLORS['white'],
                                        highlightbackground=COLORS['outline_variant'],
                                        highlightthickness=1)
        input_field_container.pack(fill=tk.X)
        
        self.user_input = tk.Entry(input_field_container, 
                                  bg=COLORS['white'],
                                  fg=COLORS['on_surface'],
                                  font=("Inter", 12),
                                  insertbackground=COLORS['primary'],
                                  relief=tk.FLAT,
                                  borderwidth=0)
        self.user_input.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=16, pady=14)
        self.user_input.bind('<Return>', lambda e: self.send_message())
        self.placeholder_text = "Ask a question about your documents..."
        self.user_input.insert(0, self.placeholder_text)
        self.user_input.config(fg=COLORS['outline'])
        self.user_input.bind('<FocusIn>', self._clear_placeholder)
        self.user_input.bind('<FocusOut>', self._restore_placeholder)
        
        send_btn = tk.Button(input_field_container, text="Send →", 
                            command=self.send_message,
                            bg=COLORS['primary'], fg=COLORS['white'],
                            font=("Inter", 11, "bold"),
                            activebackground=COLORS['primary_container'],
                            activeforeground=COLORS['white'],
                            relief=tk.FLAT, cursor='hand2',
                            padx=20, pady=12)
        send_btn.pack(side=tk.RIGHT, padx=8, pady=8)
    
    def create_status_bar(self, parent):
        status_bar = tk.Frame(parent, bg=COLORS['surface_container_low'], height=100,
                             highlightbackground=COLORS['outline_variant'],
                             highlightthickness=1)
        status_bar.pack(fill=tk.X, side=tk.BOTTOM)
        status_bar.pack_propagate(False)
        
        # Left section: system status
        left_status = tk.Frame(status_bar, bg=COLORS['surface_container_low'])
        left_status.pack(side=tk.LEFT, padx=20, pady=12)
        
        tk.Label(left_status, text="System Status", 
                font=("Inter", 11, "bold"), fg=COLORS['on_surface'],
                bg=COLORS['surface_container_low']).pack(anchor=tk.W)
        
        status_items = tk.Frame(left_status, bg=COLORS['surface_container_low'])
        status_items.pack(anchor=tk.W, pady=(8, 0))
        
        # Ollama status
        self.ollama_status_label = tk.Label(status_items, text="🔴 Ollama", 
                                           font=("Inter", 10), fg=COLORS['error'],
                                           bg=COLORS['surface_container_low'])
        self.ollama_status_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # FAISS status
        self.faiss_status_label = tk.Label(status_items, text="🔴 FAISS", 
                                          font=("Inter", 10), fg=COLORS['error'],
                                          bg=COLORS['surface_container_low'])
        self.faiss_status_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # Database status
        self.db_status_label = tk.Label(status_items, text="🔴 Database", 
                                       font=("Inter", 10), fg=COLORS['error'],
                                       bg=COLORS['surface_container_low'])
        self.db_status_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # Folder Watcher status
        self.folder_watcher_status_label = tk.Label(status_items, text="🔴 Folder Watcher", 
                                                   font=("Inter", 10), fg=COLORS['error'],
                                                   bg=COLORS['surface_container_low'])
        self.folder_watcher_status_label.pack(side=tk.LEFT, padx=(0, 20))
        
        # Model info
        tier = self.config.search.get('model_tier', 'low')
        model_name = self.config.models.get('search_chat', self.config.models['chat'])
        self.model_label = tk.Label(status_items, 
                                    text=f"Model: {model_name} ({tier})", 
                                    font=("Inter", 10), fg=COLORS['on_surface_variant'],
                                    bg=COLORS['surface_container_low'])
        self.model_label.pack(side=tk.LEFT, padx=(0, 8))
        
        self.auto_detect_btn = tk.Button(status_items, text="Auto-Detect",
                                        command=self._run_auto_detect,
                                        bg=COLORS['surface_container'], fg=COLORS['primary'],
                                        font=("Inter", 9, "bold"),
                                        relief=tk.FLAT, cursor='hand2',
                                        padx=8, pady=2)
        self.auto_detect_btn.pack(side=tk.LEFT)
        
        # Right section: stats
        right_status = tk.Frame(status_bar, bg=COLORS['surface_container_low'])
        right_status.pack(side=tk.RIGHT, padx=20, pady=12)
        
        self.doc_count_label = tk.Label(right_status, text="0 Documents", 
                                       font=("Inter", 11, "bold"), fg=COLORS['primary'],
                                       bg=COLORS['surface_container_low'])
        self.doc_count_label.pack(side=tk.LEFT, padx=(0, 24))
        
        self.chunk_count_label = tk.Label(right_status, text="0 Chunks", 
                                         font=("Inter", 11, "bold"), fg=COLORS['primary'],
                                         bg=COLORS['surface_container_low'])
        self.chunk_count_label.pack(side=tk.LEFT, padx=(0, 24))
        
        self.last_index_label = tk.Label(right_status, text="Last Index: --", 
                                        font=("Inter", 10), fg=COLORS['on_surface_variant'],
                                        bg=COLORS['surface_container_low'])
        self.last_index_label.pack(side=tk.LEFT)
    
    def check_system_status(self):
        # Check Ollama connection
        try:
            self.ollama_client.list()
            self.ollama_connected = True
            self.ollama_status_label.config(text="🟢 Ollama", fg=COLORS['success'])
        except:
            self.ollama_connected = False
            self.ollama_status_label.config(text="🔴 Ollama", fg=COLORS['error'])
        
        # Check FAISS
        if self.vector_store.index is not None:
            self.faiss_ready = True
            self.faiss_status_label.config(text="🟢 FAISS", fg=COLORS['success'])
        else:
            self.faiss_ready = False
            self.faiss_status_label.config(text="🔴 FAISS", fg=COLORS['error'])
        
        # Check Database
        try:
            docs = self.db.get_documents()
            self.db_ready = True
            self.db_status_label.config(text="🟢 Database", fg=COLORS['success'])
        except:
            self.db_ready = False
            self.db_status_label.config(text="🔴 Database", fg=COLORS['error'])
        
        # Folder Watcher (currently manual import, but status indicator is ready)
        self.folder_watcher_ready = True
        self.folder_watcher_status_label.config(text="🟢 Folder Watcher", fg=COLORS['success'])
        
        # Update model display
        self._update_model_display()
        # Update stats
        self.update_stats()
    
    def _auto_configure_model(self):
        """Auto-detect hardware and select the best model for this system."""
        try:
            profile = detect_hardware()
            tier = self.config.auto_select_model(profile)
            self.config.auto_select_search_tier(tier)
            self._detected_profile = profile
            logger.info(f"Auto-configured model: {self.config.models['chat']} (tier: {tier})")
        except Exception as e:
            logger.warning(f"Auto-config failed, using defaults: {e}")
            self._detected_profile = None

    def _run_auto_detect(self):
        """Run auto-detection in a background thread and update UI."""
        def task():
            self.root.after(0, lambda: self.auto_detect_btn.config(text="Detecting...", state=tk.DISABLED))
            try:
                profile = detect_hardware()
                tier = self.config.auto_select_model(profile)
                self.config.auto_select_search_tier(tier)
                self._detected_profile = profile
                self.root.after(0, self._update_model_display)
                self.root.after(0, lambda: messagebox.showinfo(
                    "Auto-Detect Complete",
                    f"Hardware: {profile['cpu_cores']} cores, {profile['ram_gb']}GB RAM\n"
                    f"GPU: {profile['gpu_name'] or 'None'} ({profile['gpu_vram_mb']}MB VRAM)\n"
                    f"Selected Model: {self.config.models['chat']} ({tier} tier)"
                ))
            except Exception as e:
                logger.exception("Auto-detect failed")
                self.root.after(0, lambda: messagebox.showerror("Auto-Detect Error", str(e)))
            finally:
                self.root.after(0, lambda: self.auto_detect_btn.config(text="Auto-Detect", state=tk.NORMAL))

        thread = threading.Thread(target=task)
        thread.daemon = True
        thread.start()

    def _update_model_display(self):
        """Update the model label in the status bar."""
        tier = self.config.search.get('model_tier', 'low')
        model_name = self.config.models.get('search_chat', self.config.models['chat'])
        self.model_label.config(text=f"Model: {model_name} ({tier})")

    def update_stats(self):
        doc_count = self.db.get_document_count()
        chunk_count = self.vector_store.get_chunk_count()
        last_index, _ = self.db.get_system_stats()
        
        self.doc_count_label.config(text=f"{doc_count} Document{'s' if doc_count != 1 else ''}")
        self.chunk_count_label.config(text=f"{chunk_count} Chunk{'s' if chunk_count != 1 else ''}")
        
        if last_index:
            try:
                dt = datetime.fromisoformat(last_index)
                self.last_index_label.config(text=f"Last Index: {dt.strftime('%H:%M:%S')}")
            except:
                self.last_index_label.config(text="Last Index: --")
    
    # ── Search Methods ──
    def _search_focus_in(self):
        if self.search_entry.get() == "Search keyword...":
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(fg=COLORS['on_surface'])
    
    def _search_focus_out(self):
        if not self.search_entry.get().strip():
            self.search_entry.insert(0, "Search keyword...")
            self.search_entry.config(fg=COLORS['outline'])
    
    def _run_search(self):
        keyword = self.search_entry.get().strip()
        if not keyword or keyword == "Search keyword...":
            return
        
        self.search_results_list.delete(0, tk.END)
        self.search_status.config(text="Searching...")
        self.root.update_idletasks()
        
        mode = self.search_mode.get()
        thread = threading.Thread(target=self._do_search, args=(keyword, mode))
        thread.daemon = True
        thread.start()
    
    def _do_search(self, keyword, mode):
        try:
            # Use indexed documents as search scope
            docs = self.db.get_documents()
            file_paths = [doc[1] for doc in docs]
            
            if not file_paths:
                self.root.after(0, lambda: self.search_status.config(text="No documents to search"))
                return
            
            result = self.search_engine.search(keyword, file_paths, mode)
            
            self.root.after(0, lambda: self._display_search_results(result, mode))
        except Exception as e:
            logger.exception("Search failed")
            self.root.after(0, lambda: self.search_status.config(text=f"Error: {str(e)[:50]}"))
    
    def _display_search_results(self, result, mode):
        self.search_results_list.delete(0, tk.END)
        self._cached_search_results = result['results']
        
        if not result['results']:
            self.search_results_list.insert(tk.END, "  No matches found")
            self.search_status.config(text="0 matches")
            return
        
        timing = result['timing']
        ai_pct = result.get('ai_usage_pct', 0)
        
        status_parts = [f"{result['total_matches']} matches"]
        if 'rule_search' in timing:
            status_parts.append(f"search: {timing['rule_search']}s")
        if 'ai_summary' in timing:
            status_parts.append(f"AI: {timing['ai_summary']}s")
        status_parts.append(f"AI: {ai_pct}%")
        self.search_status.config(text=" | ".join(status_parts))
        
        seen = set()
        for r in result['results'][:20]:
            key = (r['filename'], r.get('page', 0))
            if key in seen:
                continue
            seen.add(key)
            
            label = f"  {r['filename']} (p.{r.get('page', 1)})"
            self.search_results_list.insert(tk.END, label)
            
            if mode == 'smart' and 'ai_summary' in r:
                summary = r['ai_summary'][:120]
                self.search_results_list.insert(tk.END, f"     ↳ {summary}...")
    
    def _open_search_result(self, event):
        selection = self.search_results_list.curselection()
        if not selection or not hasattr(self, '_cached_search_results'):
            return
        
        idx = selection[0] // 2  # each result takes 2 listbox lines
        results = self._cached_search_results
        if idx >= len(results):
            return
        
        r = results[idx]
        if not self.viewer_visible:
            self.toggle_viewer()
        ext = 'pdf' if r['file_path'].endswith('.pdf') else 'markdown'
        self.display_document(r['filename'], r['file_path'], ext)
    
    def _browse_storage(self):
        folder = filedialog.askdirectory(title="Select folder to search")
        if not folder:
            return
        self.search_results_list.delete(0, tk.END)
        self.search_status.config(text="Scanning...")
        self.root.update_idletasks()
        thread = threading.Thread(target=self._do_browse, args=(folder,))
        thread.daemon = True
        thread.start()
    
    def _do_browse(self, folder):
        try:
            keyword = self.search_entry.get().strip()
            if keyword and keyword != "Search keyword...":
                roots = self.config.search.get('search_roots', [])
                if folder not in roots:
                    roots = [folder] + roots
                result = self.cross_finder.find_files_by_content(keyword, roots)
                self.root.after(0, lambda: self._display_browse_results(result, keyword))
            else:
                files = self.search_engine.scanner.scan_folder(folder)
                self.root.after(0, lambda: self._display_browse_results_files(files))
        except Exception as e:
            logger.exception("Browse failed")
            self.root.after(0, lambda: self.search_status.config(text=f"Error: {str(e)[:50]}"))
    
    def _display_browse_results(self, results, keyword):
        self.search_results_list.delete(0, tk.END)
        self._cached_search_results = results
        
        if not results:
            self.search_results_list.insert(tk.END, f"  No files contain '{keyword}'")
            self.search_status.config(text="0 files")
            return
        
        self.search_status.config(text=f"{len(results)} files contain '{keyword}'")
        for r in results[:15]:
            self.search_results_list.insert(tk.END, f"  📄 {r['filename']} ({r['match_count']} matches)")
            if r.get('excerpts'):
                self.search_results_list.insert(tk.END, f"     ↳ {r['excerpts'][0][:100]}...")
    
    def _display_browse_results_files(self, files):
        self.search_results_list.delete(0, tk.END)
        if not files:
            self.search_results_list.insert(tk.END, "  No supported files found")
            self.search_status.config(text="0 files")
            return
        self.search_status.config(text=f"{len(files)} files found")
        for f in files[:20]:
            ext_icon = "📄" if f['ext'] == '.pdf' else "📝"
            self.search_results_list.insert(tk.END, f"  {ext_icon} {f['filename']} ({f['size_kb']}KB)")
    
    def add_file(self):
        file_path = filedialog.askopenfilename(
            filetypes=[("Supported Files", "*.pdf *.md *.txt"), ("PDF Files", "*.pdf"), 
                      ("Markdown Files", "*.md"), ("Text Files", "*.txt")]
        )
        if file_path:
            thread = threading.Thread(target=self._process_file_thread, args=(file_path,))
            thread.daemon = True
            thread.start()
    
    def add_folder(self):
        folder_path = filedialog.askdirectory()
        if folder_path:
            files = self.doc_processor.process_folder(folder_path)
            if not files:
                messagebox.showwarning("Warning", "No PDF, MD, or TXT files found in folder")
                return
            self._show_folder_import_dialog(folder_path, files)
    
    def _process_file_thread(self, file_path):
        try:
            filename = os.path.basename(file_path)
            logger.info(f"Processing file: {filename}")
            
            # Check if already exists
            existing_docs = self.db.get_documents()
            if any(filename == doc[0] for doc in existing_docs):
                self.root.after(0, lambda: messagebox.showwarning("Warning", f"File {filename} already added!"))
                return
            
            all_chunks, all_metadata, filetype = self.doc_processor.process_file(file_path)
            
            if all_chunks:
                self.vector_store.add_chunks(all_chunks, all_metadata)
                self.db.add_document(filename, file_path, filetype, len(all_chunks))
                self.db.update_system_stats(self.vector_store.get_chunk_count())
                
                self.root.after(0, self.refresh_document_list)
                self.root.after(0, self.update_stats)
                self.root.after(0, self.check_system_status)
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    f"Added {filename} ({len(all_chunks)} chunks)"))
                logger.info(f"Added {len(all_chunks)} chunks from {filename}")
            else:
                self.root.after(0, lambda: messagebox.showwarning("Warning", 
                    f"No content found in {filename}"))
        except Exception as e:
            logger.exception("Error processing file")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to process file: {str(e)}"))
    
    def _show_folder_import_dialog(self, folder_path, files):
        dialog = tk.Toplevel(self.root)
        dialog.title("Select Files to Import")
        dialog.geometry("600x450")
        dialog.configure(bg=COLORS['background'])
        dialog.transient(self.root)
        dialog.grab_set()
        
        header = tk.Frame(dialog, bg=COLORS['white'], padx=20, pady=16)
        header.pack(fill=tk.X)
        
        folder_name = os.path.basename(folder_path) or folder_path
        tk.Label(header, text=f"📁 {folder_name}", 
                font=("Inter", 14, "bold"), fg=COLORS['on_surface'],
                bg=COLORS['white']).pack(anchor=tk.W)
        tk.Label(header, text=f"{len(files)} files detected", 
                font=("Inter", 11), fg=COLORS['on_surface_variant'],
                bg=COLORS['white']).pack(anchor=tk.W, pady=(4, 0))
        
        # Select All / Deselect All bar
        control_bar = tk.Frame(dialog, bg=COLORS['surface_container_low'], padx=20, pady=10)
        control_bar.pack(fill=tk.X)
        
        select_all_btn = tk.Button(control_bar, text="Select All", 
                                  font=("Inter", 10), fg=COLORS['primary'],
                                  bg=COLORS['surface_container_low'],
                                  relief=tk.FLAT, cursor='hand2',
                                  activebackground=COLORS['surface_container_high'],
                                  activeforeground=COLORS['primary'])
        select_all_btn.pack(side=tk.LEFT, padx=(0, 12))
        
        deselect_all_btn = tk.Button(control_bar, text="Deselect All", 
                                    font=("Inter", 10), fg=COLORS['on_surface_variant'],
                                    bg=COLORS['surface_container_low'],
                                    relief=tk.FLAT, cursor='hand2',
                                    activebackground=COLORS['surface_container_high'],
                                    activeforeground=COLORS['on_surface_variant'])
        deselect_all_btn.pack(side=tk.LEFT)
        
        # Scrollable check list
        list_frame = tk.Frame(dialog, bg=COLORS['background'])
        list_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=12)
        
        canvas = tk.Canvas(list_frame, bg=COLORS['background'], highlightthickness=0)
        scrollbar = tk.Scrollbar(list_frame, orient=tk.VERTICAL, command=canvas.yview)
        scrollable = tk.Frame(canvas, bg=COLORS['background'])
        
        scrollable.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=scrollable, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)
        
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Populate checkboxes
        var_map = {}
        existing_docs = self.db.get_documents()
        existing_names = {doc[0] for doc in existing_docs}
        
        for file_path in files:
            filename = os.path.basename(file_path)
            file_ext = os.path.splitext(filename)[1].lower()
            icon = "📄" if file_ext == '.pdf' else "📝"
            
            already_imported = filename in existing_names
            var = tk.BooleanVar(value=not already_imported)
            var_map[file_path] = (var, filename)
            
            cb = tk.Checkbutton(scrollable, text=f"  {icon} {filename}", 
                               variable=var,
                               font=("Inter", 11),
                               fg=COLORS['on_surface'],
                               bg=COLORS['background'],
                               activebackground=COLORS['background'],
                               anchor=tk.W, padx=12, pady=4,
                               selectcolor=COLORS['white'])
            cb.pack(fill=tk.X, pady=1)
            
            if already_imported:
                cb.config(fg=COLORS['outline'], state=tk.DISABLED)
                tk.Label(scrollable, text=" (already imported)", 
                        font=("Inter", 9), fg=COLORS['outline'],
                        bg=COLORS['background']).pack(anchor=tk.W, padx=(40, 0))
                var.set(False)
        
        # Actions
        action_frame = tk.Frame(dialog, bg=COLORS['background'], padx=20, pady=16)
        action_frame.pack(fill=tk.X)
        
        def toggle_all(select):
            for file_path, (v, fn) in var_map.items():
                if fn not in existing_names:
                    v.set(select)
        
        select_all_btn.config(command=lambda: toggle_all(True))
        deselect_all_btn.config(command=lambda: toggle_all(False))
        
        def on_import():
            selected = [fp for fp, (v, _) in var_map.items() if v.get()]
            dialog.destroy()
            if selected:
                thread = threading.Thread(target=self._process_selected_files, args=(selected,))
                thread.daemon = True
                thread.start()
        
        def on_cancel():
            dialog.destroy()
        
        tk.Button(action_frame, text="Import Selected", 
                 command=on_import,
                 bg=COLORS['primary'], fg=COLORS['white'],
                 font=("Inter", 11, "bold"),
                 relief=tk.FLAT, cursor='hand2',
                 padx=24, pady=10).pack(side=tk.RIGHT, padx=(12, 0))
        
        tk.Button(action_frame, text="Cancel", 
                 command=on_cancel,
                 bg=COLORS['surface_container'], fg=COLORS['on_surface_variant'],
                 font=("Inter", 11),
                 relief=tk.FLAT, cursor='hand2',
                 padx=24, pady=10).pack(side=tk.RIGHT)
    
    def _process_selected_files(self, files):
        try:
            added_count = 0
            total_chunks = 0
            
            for file_path in files:
                filename = os.path.basename(file_path)
                
                existing_docs = self.db.get_documents()
                if any(filename == doc[0] for doc in existing_docs):
                    continue
                
                try:
                    all_chunks, all_metadata, filetype = self.doc_processor.process_file(file_path)
                    
                    if all_chunks:
                        self.vector_store.add_chunks(all_chunks, all_metadata)
                        self.db.add_document(filename, file_path, filetype, len(all_chunks))
                        added_count += 1
                        total_chunks += len(all_chunks)
                        logger.info(f"Added {filename} ({len(all_chunks)} chunks)")
                except Exception as e:
                    logger.error(f"Failed to process {filename}: {e}")
                    continue
            
            if added_count > 0:
                self.db.update_system_stats(self.vector_store.get_chunk_count())
                self.root.after(0, self.refresh_document_list)
                self.root.after(0, self.update_stats)
                self.root.after(0, self.check_system_status)
                self.root.after(0, lambda: messagebox.showinfo("Success", 
                    f"Added {added_count} files ({total_chunks} chunks)"))
            else:
                self.root.after(0, lambda: messagebox.showinfo("Info", 
                    "No new files were added"))
        except Exception as e:
            logger.exception("Error processing folder")
            self.root.after(0, lambda: messagebox.showerror("Error", f"Failed to process folder: {str(e)}"))
    
    def reset_store(self):
        confirm = messagebox.askyesno("Reset", "Are you sure you want to reset everything? This will delete all stored data.")
        if confirm:
            try:
                index_file = Path(self.config.vector_store['index_file'])
                meta_file = Path(self.config.vector_store['metadata_file'])
                if index_file.exists():
                    index_file.unlink()
                if meta_file.exists():
                    meta_file.unlink()
                
                db_path = Path(self.config.paths['database'])
                if db_path.exists():
                    db_path.unlink()
                
                self.db = Database(self.config.paths['database'])
                self.vector_store = VectorStore(self.config)
                
                self.doc_listbox.delete(0, tk.END)
                
                for widget in self.chat_frame.winfo_children():
                    widget.destroy()
                
                self.update_stats()
                self.check_system_status()
                
                messagebox.showinfo("Reset", "Successfully reset everything!")
            except Exception as e:
                logger.exception("Error resetting store")
                messagebox.showerror("Error", f"Failed to reset: {str(e)}")
    
    def create_document_viewer(self, parent):
        viewer_container = tk.Frame(parent, bg=COLORS['surface_container_low'],
                                    highlightbackground=COLORS['outline_variant'],
                                    highlightthickness=1)
        viewer_container.pack(fill=tk.BOTH, expand=True)
        
        # Viewer header
        header = tk.Frame(viewer_container, bg=COLORS['surface_container'])
        header.pack(fill=tk.X, padx=8, pady=8)
        
        self.viewer_title = tk.Label(header, text="Document Viewer", 
                                    font=("Inter", 12, "bold"), fg=COLORS['on_surface'],
                                    bg=COLORS['surface_container'])
        self.viewer_title.pack(side=tk.LEFT, fill=tk.X, expand=True)
        
        # Close button
        close_btn = tk.Button(header, text="✕", 
                             command=self.toggle_viewer,
                             bg=COLORS['surface_container'], fg=COLORS['on_surface_variant'],
                             font=("Inter", 12, "bold"),
                             activebackground=COLORS['surface_container_high'],
                             activeforeground=COLORS['error'],
                             relief=tk.FLAT, cursor='hand2',
                             padx=8, pady=2)
        close_btn.pack(side=tk.RIGHT)
        
        # Viewer content
        self.viewer_text = scrolledtext.ScrolledText(viewer_container, 
                                                    wrap=tk.WORD,
                                                    font=("Inter", 11),
                                                    bg=COLORS['white'],
                                                    fg=COLORS['on_surface'],
                                                    relief=tk.FLAT,
                                                    highlightthickness=0,
                                                    borderwidth=0)
        self.viewer_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)
        self.viewer_text.config(state=tk.DISABLED)
        
        self.current_document = None
        
    def toggle_viewer(self):
        if self.viewer_visible:
            self.right_pane.forget(self.viewer_frame)
            self.viewer_visible = False
        else:
            self.right_pane.insert(0, self.viewer_frame, weight=1)
            self.viewer_visible = True
    
    def _get_doc_from_selection(self, index):
        """Helper to get document info from listbox index"""
        search_text = self.search_var.get().strip()
        # Check if we're in search mode
        if search_text and search_text != "🔍 Search documents...":
            # Try to extract filename from search result line
            line = self.doc_listbox.get(index)
            for doc in self.documents_cache:
                filename = doc[0]
                if filename in line:
                    return doc
            return None
        else:
            # Normal mode
            docs = self.db.get_documents()
            if index < len(docs):
                return docs[index]
        return None
    
    def connect_document(self, event=None):
        selection = self.doc_listbox.curselection()
        if not selection:
            return
        index = selection[0]
        doc = self._get_doc_from_selection(index)
        if not doc:
            return
        filename, filepath, filetype, _, _ = doc
        if self.active_document == filepath:
            self.active_document = None
            self.connected_doc_label.config(text="")
            self.doc_listbox.selection_clear(0, tk.END)
        else:
            self.active_document = filepath
            icon = "📄" if filetype == 'pdf' else "📝"
            self.connected_doc_label.config(
                text=f"{icon} Connected: {filename}  (click to disconnect)")
    
    def open_document(self, event):
        selection = self.doc_listbox.curselection()
        if selection:
            index = selection[0]
            doc = self._get_doc_from_selection(index)
            if doc:
                filename, filepath, filetype, _, _ = doc
                if not self.viewer_visible:
                    self.toggle_viewer()
                self.display_document(filename, filepath, filetype)
    
    def _drag_start(self, event):
        index = self.doc_listbox.nearest(event.y)
        if index >= 0:
            docs = self.db.get_documents()
            if index < len(docs):
                self._drag_data = docs[index]
                self.doc_listbox.config(cursor="hand2")
    
    def _drag_motion(self, event):
        if self._drag_data:
            pass  # visual feedback could go here
    
    def _drag_end(self, event):
        if self._drag_data:
            # Check if dropped near chat area (bottom-right region)
            chat_x = self.chat_canvas.winfo_rootx()
            chat_y = self.chat_canvas.winfo_rooty()
            chat_w = self.chat_canvas.winfo_width()
            chat_h = self.chat_canvas.winfo_height()
            if chat_x <= event.x_root <= chat_x + chat_w and chat_y <= event.y_root <= chat_y + chat_h:
                filename, filepath, filetype, _, _ = self._drag_data
                self.active_document = filepath
                icon = "📄" if filetype == 'pdf' else "📝"
                self.connected_doc_label.config(
                    text=f"{icon} Connected: {filename}  (dragged to chat)")
                self.append_message("System", f"📎 Connected document: {filename} as chat context")
            self._drag_data = None
            self.doc_listbox.config(cursor="")
    
    def display_document(self, filename, filepath, filetype):
        self.current_document = filepath
        self.viewer_title.config(text=f"Viewing: {filename}")
        
        if filetype == 'pdf':
            self.viewer_text.config(state=tk.NORMAL)
            self.viewer_text.delete(1.0, tk.END)
            self.viewer_text.insert(tk.END, 
                f"PDF Document: {filename}\n\n"
                "PDF files are opened in your default PDF viewer.\n"
                "Click here to open in external viewer.")
            self.viewer_text.config(state=tk.DISABLED)
            
            try:
                webbrowser.open(os.path.normpath(filepath))
            except:
                messagebox.showerror("Error", f"Could not open {filename}")
        else:
            try:
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.viewer_text.config(state=tk.NORMAL)
                self.viewer_text.delete(1.0, tk.END)
                self.viewer_text.insert(tk.END, content)
                self.viewer_text.config(state=tk.DISABLED)
            except Exception as e:
                messagebox.showerror("Error", f"Could not read file: {str(e)}")
    
    def refresh_document_list(self):
        self.doc_listbox.delete(0, tk.END)
        docs = self.db.get_documents()
        self.documents_cache = docs
        for doc in docs:
            filename, _, filetype, _, chunk_count = doc
            icon = "📄" if filetype == 'pdf' else "📝"
            self.doc_listbox.insert(tk.END, f"  {icon} {filename} ({chunk_count} chunks)")
    
    def _clear_search_placeholder(self, event=None):
        if self.search_entry.get() == "🔍 Search documents...":
            self.search_entry.delete(0, tk.END)
            self.search_entry.config(fg=COLORS['on_surface'])
    
    def _restore_search_placeholder(self, event=None):
        if not self.search_entry.get().strip():
            self.search_entry.insert(0, "🔍 Search documents...")
            self.search_entry.config(fg=COLORS['outline'])
            self.refresh_document_list()
    
    def on_search_change(self, *args):
        # Debounce search - only search after user stops typing
        if hasattr(self, 'search_timer'):
            self.root.after_cancel(self.search_timer)
        self.search_timer = self.root.after(300, self.perform_search)
    
    def perform_search(self, event=None):
        search_text = self.search_var.get().strip()
        
        if not search_text or search_text == "🔍 Search documents...":
            self.refresh_document_list()
            return
        
        # Perform keyword search in background thread
        thread = threading.Thread(target=self._search_thread, args=(search_text,))
        thread.daemon = True
        thread.start()
    
    def _search_thread(self, search_text):
        try:
            results = self.knowledge_agent.keyword_search_documents(search_text)
            
            # Group results by document
            doc_results = {}
            for result in results:
                doc = result['pdf_name']
                if doc not in doc_results:
                    doc_results[doc] = []
                doc_results[doc].append(result)
            
            # Update UI
            self.root.after(0, self._update_search_results, doc_results, search_text)
        except Exception as e:
            logger.exception(f"Search error: {e}")
    
    def _update_search_results(self, doc_results, search_text):
        self.doc_listbox.delete(0, tk.END)
        
        if not doc_results:
            self.doc_listbox.insert(tk.END, "  No matching documents found")
            return
        
        # Show search results grouped by document
        for doc_name, chunks in doc_results.items():
            icon = "📄" if doc_name.lower().endswith('.pdf') else "📝"
            self.doc_listbox.insert(tk.END, f"  {icon} {doc_name} ({len(chunks)} matches)")
            
            # Show preview of first chunk
            first_chunk = chunks[0]['chunk'][:100]
            preview = first_chunk.replace('\n', ' ')
            self.doc_listbox.insert(tk.END, f"    → Preview: {preview}...")
            self.doc_listbox.insert(tk.END, "")
    
    def _disconnect_document(self):
        self.active_document = None
        self.connected_doc_label.config(text="")
        self.doc_listbox.selection_clear(0, tk.END)
    
    def _clear_placeholder(self, event=None):
        if self.user_input.get() == self.placeholder_text:
            self.user_input.delete(0, tk.END)
            self.user_input.config(fg=COLORS['on_surface'])
    
    def _restore_placeholder(self, event=None):
        if not self.user_input.get().strip():
            self.user_input.insert(0, self.placeholder_text)
            self.user_input.config(fg=COLORS['outline'])
    
    def send_message(self):
        user_text = self.user_input.get().strip()
        if not user_text or user_text == self.placeholder_text:
            return
        
        self.user_input.delete(0, tk.END)
        self.append_message("You", user_text)
        
        # If a document is connected, prepend context reference
        query = user_text
        if self.active_document:
            doc_name = os.path.basename(self.active_document)
            query = f"[Context: {doc_name}] {query}"
        
        self.thinking_id = self.append_message("AI", "Thinking...", is_thinking=True)
        
        thread = threading.Thread(target=self._process_message, args=(query,))
        thread.daemon = True
        thread.start()
    
    def _process_message(self, user_text):
        try:
            # Get filter filename if document is connected
            filter_filename = None
            if self.active_document:
                filter_filename = os.path.basename(self.active_document)
            
            search_results, latency = self.knowledge_agent.search_knowledge(user_text, filter_pdf_name=filter_filename)
            context = self.knowledge_agent.format_context(search_results)
            prompt = self.knowledge_agent.build_prompt(user_text, context)
            confidence = self.knowledge_agent.calculate_confidence(search_results)
            
            try:
                model_name = self.config.models.get('chat_lora', self.config.models['chat'])
                
                response = self.ollama_client.generate(
                    model=model_name, 
                    prompt=prompt,
                    options={
                        'temperature': 0.7,
                        'max_tokens': 1024,
                        'top_p': 0.9
                    }
                )
                ai_response = response['response'].strip()
            except Exception as e:
                logger.error(f"Error calling Ollama: {e}")
                ai_response = f"Sorry, I couldn't connect to the local model. Error: {str(e)}"
                confidence = 0
                latency = 0
                search_results = []
            
            self.root.after(0, self._update_chat_response, ai_response, confidence, latency, search_results)
            self.db.add_memory(user_text, ai_response)
        except Exception as e:
            logger.exception("Error in _process_message")
            error_msg = f"An error occurred: {str(e)}"
            self.root.after(0, self._update_chat_response, f"System: {error_msg}", 0, 0, [])
    
    def _update_chat_response(self, message, confidence, latency, search_results):
        if hasattr(self, 'thinking_id'):
            for widget in self.chat_frame.winfo_children():
                if hasattr(widget, 'is_thinking'):
                    widget.destroy()
        
        self.append_message("AI", message, confidence=confidence, latency=latency, sources=search_results)
    
    def append_message(self, sender, message, is_thinking=False, confidence=None, latency=None, sources=None):
        timestamp = datetime.now().strftime("%H:%M")
        
        message_frame = tk.Frame(self.chat_frame, bg=COLORS['surface'])
        message_frame.pack(fill=tk.X, pady=(0, 20))
        
        if sender == "You":
            # User message - aligned right
            align_frame = tk.Frame(message_frame, bg=COLORS['surface'])
            align_frame.pack(fill=tk.X)
            
            time_label = tk.Label(align_frame, text=f"You • {timestamp}", 
                                 font=("Inter", 9, "bold"), fg=COLORS['outline'],
                                 bg=COLORS['surface'])
            time_label.pack(anchor=tk.E, padx=(0, 8))
            
            bubble_frame = tk.Frame(align_frame, bg=COLORS['surface'])
            bubble_frame.pack(anchor=tk.E)
            
            bubble = tk.Label(bubble_frame, text=message, 
                             wraplength=600, justify=tk.LEFT,
                             bg=COLORS['primary'], fg=COLORS['white'],
                             font=("Inter", 12),
                             padx=20, pady=12)
            bubble.pack(anchor=tk.E)
        else:
            # AI message - aligned left
            header_frame = tk.Frame(message_frame, bg=COLORS['surface'])
            header_frame.pack(fill=tk.X, anchor=tk.W)
            
            # AI avatar/icon
            avatar_frame = tk.Frame(header_frame, bg=COLORS['secondary_container'])
            avatar_frame.pack(side=tk.LEFT)
            
            tk.Label(avatar_frame, text="AI", 
                    font=("Inter", 9, "bold"), fg=COLORS['primary'],
                    bg=COLORS['secondary_container'], padx=6, pady=4).pack()
            
            tk.Label(header_frame, text=f"  Cognitive Assistant • {timestamp}", 
                    font=("Inter", 9, "bold"), fg=COLORS['primary'],
                    bg=COLORS['surface']).pack(side=tk.LEFT)
            
            bubble_frame = tk.Frame(message_frame, bg=COLORS['surface'])
            bubble_frame.pack(fill=tk.X, anchor=tk.W, pady=(8, 0))
            
            bubble = tk.Label(bubble_frame, text=message, 
                             wraplength=700, justify=tk.LEFT,
                             bg=COLORS['white'], fg=COLORS['on_surface'],
                             font=("Inter", 12),
                             padx=20, pady=16,
                             highlightbackground=COLORS['outline_variant'],
                             highlightthickness=1)
            bubble.pack(anchor=tk.W)
            
            # Add metadata (confidence, latency, sources) if available
            if confidence is not None or latency is not None or sources:
                meta_frame = tk.Frame(message_frame, bg=COLORS['surface'])
                meta_frame.pack(fill=tk.X, anchor=tk.W, pady=(12, 0))
                
                if confidence is not None:
                    conf_color = COLORS['success'] if confidence > 70 else (COLORS['primary'] if confidence > 40 else COLORS['error'])
                    tk.Label(meta_frame, text=f"Confidence: {confidence:.0f}%", 
                            font=("Inter", 10, "bold"), fg=conf_color,
                            bg=COLORS['surface']).pack(side=tk.LEFT, padx=(0, 20))
                
                if latency is not None:
                    tk.Label(meta_frame, text=f"Retrieval: {latency:.2f}s", 
                            font=("Inter", 10), fg=COLORS['on_surface_variant'],
                            bg=COLORS['surface']).pack(side=tk.LEFT, padx=(0, 20))
                
                if sources and len(sources) > 0:
                    tk.Label(meta_frame, text=f"Sources: {len(sources)}", 
                            font=("Inter", 10), fg=COLORS['on_surface_variant'],
                            bg=COLORS['surface']).pack(side=tk.LEFT)
            
            # Show sources if available
            if sources and len(sources) > 0:
                sources_frame = tk.Frame(message_frame, bg=COLORS['surface'])
                sources_frame.pack(fill=tk.X, anchor=tk.W, pady=(12, 0))
                
                tk.Label(sources_frame, text="Sources:", 
                        font=("Inter", 10, "bold"), fg=COLORS['on_surface'],
                        bg=COLORS['surface']).pack(anchor=tk.W)
                
                for i, source in enumerate(sources, 1):
                    source_text = f"  {i}. {source['pdf_name']} • Page {source['page']} (score: {source['score']:.2f})"
                    tk.Label(sources_frame, text=source_text, 
                            font=("Inter", 9), fg=COLORS['on_surface_variant'],
                            bg=COLORS['surface']).pack(anchor=tk.W)
            
            if is_thinking:
                message_frame.is_thinking = True
        
        self.chat_canvas.update_idletasks()
        self.chat_canvas.yview_moveto(1.0)


if __name__ == "__main__":
    root = tk.Tk()
    app = ChatApp(root)
    root.mainloop()
