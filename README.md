# Cognitive AI – Hybrid SPUR + Local Knowledge Workspace

An AI-powered knowledge workspace with an **auto-adaptive hybrid inference layer**: prioritizes SPUR sovereign compute endpoints, with automatic fallback to local Ollama models when the API is unavailable.

## Key Features
- Multi-format document support (PDF, Markdown, TXT)
- Recursive folder import with automatic scanning
- Text chunking and embedding with `all-minilm:l6-v2` (local, consistent)
- FAISS vector store for fast similarity search (cosine/IP)
- SQLite for conversation memory, document metadata, and system stats
- Knowledge Agent (RAG pipeline with confidence scoring + source citations)
- Retrieval latency display and system status indicators
- Project statistics (document count, chunk count, last index time)
- Conversation memory across sessions
- **Dual search engine** — Rule-based keyword search (0% AI) + AI-assisted smart search (<20% AI)
- **Cross-location file retrieval** — Search for files across folders by name or content
- **PDF keyword localization** — Find exact keyword positions with surrounding context
- **Hybrid inference** — SPUR API (`spur-cortex`) with automatic fallback to local Ollama (`qwen2.5:3b`)
- YAML configuration system
- Logging and caching
- Desktop UI with tkinter
- Comprehensive evaluation system with structured test cases

## Why these choices
- **Hybrid architecture**: SPUR API is the primary inference provider; if unavailable (e.g., zero balance, network issues), the system auto-adapts to local Ollama models with zero downtime.
- **Embeddings always local**: Uses `all-minilm:l6-v2` via Ollama for consistent 384-dim vectors regardless of active provider.
- **Lightweight libraries**: pypdf, faiss-cpu, numpy, openai — simple stack.
- **FAISS**: Fast vector similarity search with normalized embeddings + IndexFlatIP.
- **SQLite**: Simple, file-based database for metadata and memories.
- **tkinter**: Built-in Python GUI library for desktop applications.

## How to use

### Prerequisites
1. **Python 3.8+** installed
2. **Ollama** (required for local embeddings and fallback): Download from https://ollama.com/download
3. **Pull the required local models**:
   ```bash
   ollama pull qwen2.5:3b
   ollama pull qwen3:0.6b
   ollama pull all-minilm:l6-v2
   ```
4. **Start Ollama**: Launch the Ollama app (or `ollama serve` on Linux/Mac)
5. **(Optional) A SPUR account** with an API key from https://ai.spuric.com — the system auto-detects SPUR and falls back to local if unavailable.

### Setup
1. Clone or download this repository
2. (Optional) Copy `.env.example` to `.env` and fill in your SPUR API key:
   ```env
   OPENAI_BASE_URL="https://ai.spuric.com/v1"
   OPENAI_API_KEY="your_spur_api_key_here"
   ```
   Without `.env`, the system runs entirely on local Ollama.
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

### Run the Application
```bash
python app.py
```
Or double-click `run_app.bat` on Windows.

Click **Import Folder** to scan a directory (recursively finds PDF, MD, TXT files) or **+ Add File** for individual files, then start chatting with the AI about your documents!

The status bar shows which provider is active: **SPUR API** (primary) or **Ollama (fallback)**.

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
Embeddings (all-minilm:l6-v2 via Ollama — always local)
      ↓
FAISS (IndexFlatIP with normalized vectors)
      ↓
Metadata + Stats (SQLite)
      ↓
KnowledgeAgent (RAG pipeline)
      ↓
SPUR API (spur-cortex) ──┬── success ──→ Answer
      │                    │
      └── failure ─────────┤
                           ▼
                    Ollama (qwen2.5:3b) [fallback]
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
                              (spur-cortex)
                              Only on top-N segments
                                        ▼
                              Results + Citations
```

### Memory-Enhanced Query Flow (with Auto-Fallback)
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
             │
             ▼
      SPUR API ──┬── success ──→ Answer
        │        │
        └── fail ─┤
                  ▼
           Ollama (fallback)
                  │
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
├── core.py                # Config, Database, VectorStore, DocumentProcessor, LLMClient
├── search_engine.py       # DualSearchEngine, CrossLocationFinder, RuleBasedSearcher
├── smolagent_helper.py    # KnowledgeAgent (RAG pipeline)
├── eval.py                # Evaluation system
├── config.yaml            # Configuration file
├── requirements.txt       # Dependencies
├── .env.example           # Environment variable template
├── .gitignore             # Git ignore rules
├── README.md              # This file
├── GITHUB_GUIDE.md        # GitHub upload guide
├── run_app.bat            # Windows: Run the app
├── run_eval.bat           # Windows: Run the evaluation
├── evals/                 # Evaluation files
│   ├── dataset.json       # Evaluation dataset with 20 test cases
│   └── results.json       # Evaluation results (generated)
├── data/                  # Data directory
│   ├── embeddings/        # FAISS index and metadata
│   ├── cache/             # Cache directory
│   ├── app.db             # SQLite database
│   └── test_documents/    # Test PDF document
│       └── sample_report.pdf
├── logs/                  # Log files
└── frontend/              # Frontend design files
    └── DESIGN.md          # Design system documentation
```

## Configuration

All settings are in `config.yaml`:

```yaml
models:
  chat: spur-cortex                # Primary: SPUR API chat model
  chat_fallback: qwen2.5:3b        # Fallback: local Ollama chat model
  embedding: all-minilm:l6-v2      # Embedding (always local, 384-dim)
  search_chat: spur-cortex         # Primary: SPUR search model
  search_chat_fallback: qwen3:0.6b # Fallback: local Ollama search model
```

Set your SPUR API credentials in `.env` (see `.env.example` for the template).
Without `.env`, the system runs entirely on local Ollama models.

## Future Roadmap
- **Knowledge Graph** — Entity extraction and relationship mapping across documents
- **Hybrid Retrieval** — Combine dense (FAISS) + sparse (BM25) search for better recall
- **Gradio Web Interface** — Browser-based UI alternative to tkinter

## Honest Limitations
- The model's accuracy depends on the quality of text extraction from files
- May hallucinate if the prompt is too vague
- SPUR API requires an internet connection and valid API key
- Local Ollama fallback requires the models to be pulled and Ollama running
- Local models (0.6B–3B params) have limited reasoning capability

---

*This capstone was built by Bilal Asif, with deep appreciation for SPUR's exceptional courses and transformative teaching style, and verified running successfully via the SPUR sovereign inference endpoints.*
