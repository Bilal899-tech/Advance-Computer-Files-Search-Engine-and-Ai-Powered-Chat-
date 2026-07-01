# Cognitive AI – Local Knowledge Workspace

A local-first AI workspace that automatically indexes documents, performs semantic retrieval, remembers conversations, and answers questions with grounded citations using on-device language models.

## Key Features
- Multi-format document support (PDF, Markdown, TXT)
- Recursive folder import with automatic scanning
- Text chunking and embedding with all-minilm:l6-v2
- FAISS vector store for fast similarity search (cosine/IP)
- SQLite for conversation memory, document metadata, and system stats
- Knowledge Agent (RAG pipeline with confidence scoring + source citations)
- Retrieval latency display and system status indicators
- Project statistics (document count, chunk count, last index time)
- Conversation memory across sessions
- **Dual search engine** — Rule-based keyword search (0% AI) + AI-assisted smart search (<20% AI)
- **Cross-location file retrieval** — Search for files across folders by name or content
- **PDF keyword localization** — Find exact keyword positions with surrounding context
- **Dual model tier** — Qwen3:0.6B (low-resource) / Qwen2.5:3B (high-resource)
- YAML configuration system
- Logging and caching
- Desktop UI with tkinter
- Local model usage with Ollama (qwen2.5:3b for chat)
- Comprehensive evaluation system with structured test cases

## Why these choices
- **Local models only**: Uses qwen2.5:3b (capable) and all-minilm:l6-v2 for zero token cost, low latency, and full data sovereignty.
- **Lightweight libraries**: pypdf, faiss-cpu, numpy, ollama, pyyaml - no heavy frameworks.
- **FAISS**: Fast vector similarity search with normalized embeddings + IndexFlatIP.
- **SQLite**: Simple, file-based database for metadata and memories.
- **tkinter**: Built-in Python GUI library for desktop applications.

## How to use

### Prerequisites
1. **Install Ollama**: Download from https://ollama.com/download
2. **Pull the required models**:
   ```bash
   ollama pull qwen2.5:3b
   ollama pull all-minilm:l6-v2
   ```
3. **Start Ollama**:
   - On Windows: Launch the Ollama app
   - On macOS/Linux: Run `ollama serve`

### Run the Application
1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Run the application:
   ```bash
   python app.py
   ```
   Or double-click `run_app.bat` on Windows
3. Click **Import Folder** to scan a directory (recursively finds PDF, MD, TXT files) or **+ Add File** for individual files
4. Start chatting with the AI about your documents!

### Run the Evaluation
```bash
python eval.py
```
Or double-click `run_eval.bat` on Windows

This will:
- Automatically load the test PDF document
- Run 20 structured test cases
- Measure pass rate, score, and response times
- Show detailed results and summary metrics
- Save results to `evals/results.json`

## Architecture

### Data Flow
```
User Folder
      ↓
Folder Watcher
      ↓
Document Processor (PDF / MD / TXT)
      ↓
Chunking (with configurable size + overlap)
      ↓
Embeddings (all-minilm:l6-v2 via Ollama)
      ↓
FAISS (IndexFlatIP with normalized vectors)
      ↓
Metadata + Stats (SQLite)
      ↓
KnowledgeAgent (RAG pipeline)
      ↓
Ollama (qwen2.5:3b)
      ↓
Grounded Answer + Citations
```

### Search System (Low-Resource Design)
```
User Query
      │
      ├── Mode: Quick ──────────────────┐
      │   (0% AI, rule-based)           │
      │                                 ▼
      ▼                         FileScanner → Extract Text
  Search Entry                    → Regex Match
      │                                 │
      ├── Mode: Smart ─────────────────┘
      │   (~20% AI)                     │
      │                                 ▼
      │                     Locate + Rank Results
      │                                 │
      └─────────────────────────────────┘
                                        ▼
                              LightweightSummarizer
                              (Qwen3:0.6B / Qwen2.5:3B)
                              Only on top-N segments
                                        ▼
                              Results + Citations
```

### Memory-Enhanced Query Flow
```
User Question
      │
      ├──────────────────┐
      ▼                  ▼
Conversation Memory    FAISS Search
      │                  │
      └──────┬───────────┘
             ▼
      KnowledgeAgent
             ▼
          Ollama
             ▼
     Answer + Citations
```

### Project Workspace Model
```
Projects (e.g. AI Research)
      ↓
Folder (watched directory)
      ↓
Settings (YAML configuration)
      ↓
Index (FAISS vector store)
      ↓
Memory (SQLite conversation history)
```

## Project Structure
```
Third Try/
├── app.py                 # Main GUI application
├── core.py                # Config, Database, VectorStore, DocumentProcessor
├── search_engine.py       # DualSearchEngine, CrossLocationFinder, RuleBasedSearcher
├── smolagent_helper.py    # KnowledgeAgent (RAG pipeline)
├── eval.py                # Evaluation system
├── config.yaml            # Configuration file
├── requirements.txt       # Dependencies
├── README.md              # This file
├── run_app.bat            # Windows: Run the app
├── run_eval.bat           # Windows: Run the evaluation
├── report.json            # Project report / metadata
├── evals/                 # Evaluation files
│   ├── dataset.json       # Evaluation dataset with 20 test cases
│   └── results.json       # Evaluation results (generated)
├── data/                  # Data directory
│   ├── embeddings/        # FAISS index and metadata
│   ├── cache/             # Cache directory
│   ├── app.db             # SQLite database
│   └── test_documents/    # Test PDF document
│       └── sample_report.pdf
└── logs/                  # Log files
```

## Future Roadmap
- **Knowledge Graph** — Entity extraction and relationship mapping across documents
- **Hybrid Retrieval** — Combine dense (FAISS) + sparse (BM25) search for better recall
- **LoRA Fine-Tuning** — Fine-tune the chat model on indexed document corpora
- **Cloud Sync (Optional)** — Encrypted sync of indexes across devices
- **Gradio Web Interface** — Browser-based UI alternative to tkinter

## Honest Limitations
- The model's accuracy depends on the quality of text extraction from files
- May hallucinate if the prompt is too vague
- Performance depends on your local hardware
- Requires Ollama to be running locally
