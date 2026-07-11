"""
Core components for the PDF Chat Assistant
"""
import os
import yaml
import json
import sqlite3
import logging
import faiss
import numpy as np
import time
import subprocess
import psutil
from datetime import datetime
from pypdf import PdfReader
from pathlib import Path
from openai import OpenAI
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


class LLMClient:
    """Dual-provider client with probe-once dispatch.

    Probes SPUR at first call. If available → uses it as primary.
    If unavailable → silently uses local Ollama for the entire session
    without repeated fallback attempts.
    Call probe_spur() or recheck_spur() to re-evaluate.
    """

    def __init__(self, local_ollama_host="http://localhost:11434"):
        self.spur = OpenAI(
            base_url=os.getenv("OPENAI_BASE_URL", "https://ai.spuric.com/v1"),
            api_key=os.getenv("OPENAI_API_KEY", ""),
        )
        self.local = OpenAI(
            base_url=f"{local_ollama_host}/v1",
            api_key="ollama",
        )
        self._active_provider = "local"
        self._spur_available = None
        self._probe_logged = False

    @property
    def active_provider(self):
        return self._active_provider

    @property
    def spur_available(self):
        if self._spur_available is None:
            self.probe_spur()
        return self._spur_available

    def probe_spur(self):
        """Probe SPUR once. Returns True if reachable."""
        try:
            self.spur.models.list()
            self._spur_available = True
            self._active_provider = "spur"
            if not self._probe_logged:
                logger.info("SPUR API is reachable — using SPUR as primary provider")
                self._probe_logged = True
            return True
        except Exception:
            self._spur_available = False
            self._active_provider = "local"
            if not self._probe_logged:
                logger.info("SPUR API is unavailable — using local Ollama as primary provider")
                self._probe_logged = True
            return False

    def recheck_spur(self):
        """Re-probe SPUR. Returns True if it just became reachable."""
        was = self._spur_available
        self._probe_logged = False
        result = self.probe_spur()
        return result and not was

    def generate(self, model, prompt, options=None, fallback_model=None):
        """Chat completion: uses SPUR if available, else local Ollama directly."""
        options = options or {}
        self.probe_spur()
        if self._spur_available:
            try:
                response = self.spur.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=options.get("temperature", 0.7),
                    max_tokens=options.get("max_tokens", 1024),
                    top_p=options.get("top_p", 0.9),
                )
                self._active_provider = "spur"
                return {"response": response.choices[0].message.content}
            except Exception as e:
                logger.warning(f"SPUR request failed, marking unavailable: {e}")
                self._spur_available = False
        local_model = fallback_model or model
        try:
            response = self.local.chat.completions.create(
                model=local_model,
                messages=[{"role": "user", "content": prompt}],
                temperature=options.get("temperature", 0.7),
                max_tokens=options.get("max_tokens", 1024),
                top_p=options.get("top_p", 0.9),
            )
            self._active_provider = "local"
            return {"response": response.choices[0].message.content}
        except Exception as e2:
            logger.error(f"Local Ollama failed: {e2}")
            raise

    def embeddings(self, model, prompt, fallback_model=None):
        """Embeddings: uses SPUR if available, else local Ollama directly."""
        self.probe_spur()
        if self._spur_available:
            try:
                response = self.spur.embeddings.create(model=model, input=prompt)
                self._active_provider = "spur"
                return {"embedding": response.data[0].embedding}
            except Exception as e:
                logger.warning(f"SPUR embeddings failed, marking unavailable: {e}")
                self._spur_available = False
        local_model = fallback_model or model
        try:
            response = self.local.embeddings.create(model=local_model, input=prompt)
            self._active_provider = "local"
            return {"embedding": response.data[0].embedding}
        except Exception as e2:
            logger.error(f"Local Ollama embeddings failed: {e2}")
            raise

    def list(self):
        """Return available models from the active provider."""
        self.probe_spur()
        if self._spur_available:
            return {"models": [{"name": "spur-cortex"}]}
        try:
            self.local.models.list()
            return {"models": [{"name": "ollama"}]}
        except Exception:
            return {"models": []}


def detect_hardware():
    """Detect system hardware and return a capability profile.

    Returns:
        dict with keys: tier ('low'|'high'), gpu_name, gpu_vram_mb,
                        cpu_cores, ram_gb, models_available
    """
    profile = {
        'tier': 'low',
        'gpu_name': None,
        'gpu_vram_mb': 0,
        'cpu_cores': psutil.cpu_count(logical=True) or 0,
        'ram_gb': round(psutil.virtual_memory().total / (1024**3), 1),
        'models_available': [],
    }

    # Check for NVIDIA GPU via nvidia-smi
    try:
        result = subprocess.run(
            ['nvidia-smi', '--query-gpu=name,memory.total', '--format=csv,noheader,nounits'],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0 and result.stdout.strip():
            lines = result.stdout.strip().splitlines()
            if lines:
                parts = lines[0].split(',')
                profile['gpu_name'] = parts[0].strip()
                try:
                    profile['gpu_vram_mb'] = int(parts[1].strip())
                except (ValueError, IndexError):
                    pass
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    # Check available models via SPUR API
    try:
        client = LLMClient()
        models = client.list()
        profile['models_available'] = [m['name'] for m in models.get('models', [])]
    except Exception:
        pass

    # Determine tier: high if GPU >= 4GB VRAM, or CPU >= 8GB RAM + 4 cores
    if profile['gpu_vram_mb'] >= 4096:
        profile['tier'] = 'high'
    elif profile['ram_gb'] >= 8 and profile['cpu_cores'] >= 4:
        profile['tier'] = 'high'

    logger.info(
        f"Hardware detected: tier={profile['tier']}, "
        f"gpu={profile['gpu_name'] or 'none'} ({profile['gpu_vram_mb']}MB), "
        f"cpu={profile['cpu_cores']} cores, ram={profile['ram_gb']}GB"
    )
    return profile


class Config:
    def __init__(self, config_path='config.yaml'):
        with open(config_path, 'r', encoding='utf-8') as f:
            self.data = yaml.safe_load(f)
        self.models = self.data['models']
        self.ollama = self.data.get('ollama', {'host': 'http://localhost:11434'})
        self.paths = self.data['paths']
        self.chunking = self.data['chunking']
        self.vector_store = self.data.get('vector_store', {})
        self.rag = self.data.get('rag', {})
        self.search = self.data.get('search', {})
        # Defaults
        self.vector_store['top_k'] = self.vector_store.get('top_k', 3)
        self.vector_store['use_normalized_embeddings'] = self.vector_store.get('use_normalized_embeddings', True)

    def auto_select_model(self, profile=None):
        """Auto-detect hardware and select the best model tier.

        Args:
            profile: Optional hardware profile from detect_hardware().
                     If None, runs detection.

        Returns:
            The selected tier: 'low' or 'high'
        """
        if profile is None:
            profile = detect_hardware()
        tier = profile['tier']
        logger.info(f"Auto-selected model tier: {tier}")
        return tier

    def auto_select_search_tier(self, tier):
        """Set the search model tier based on hardware detection."""
        self.search['model_tier'] = tier
        logger.info(f"Auto-selected search model tier: {tier}")


class Database:
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_db()
    
    def init_db(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS memories
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             query TEXT NOT NULL,
             response TEXT NOT NULL,
             timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS document_metadata
            (id INTEGER PRIMARY KEY AUTOINCREMENT,
             filename TEXT NOT NULL UNIQUE,
             filepath TEXT NOT NULL,
             filetype TEXT NOT NULL,
             uploaded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
             chunk_count INTEGER DEFAULT 0)
        ''')
        c.execute('''
            CREATE TABLE IF NOT EXISTS system_stats
            (id INTEGER PRIMARY KEY,
             last_indexing_time DATETIME,
             total_chunks INTEGER DEFAULT 0)
        ''')
        conn.commit()
        conn.close()
    
    def add_memory(self, query, response):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('INSERT INTO memories (query, response) VALUES (?, ?)',
                 (query, response))
        conn.commit()
        conn.close()
    
    def get_memories(self, limit=10):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT query, response, timestamp FROM memories ORDER BY timestamp DESC LIMIT ?',
                 (limit,))
        memories = c.fetchall()
        conn.close()
        return memories
    
    def add_document(self, filename, filepath, filetype, chunk_count=0):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        try:
            c.execute('INSERT INTO document_metadata (filename, filepath, filetype, chunk_count) VALUES (?, ?, ?, ?)',
                     (filename, filepath, filetype, chunk_count))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False
        finally:
            conn.close()
    
    def get_documents(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT filename, filepath, filetype, uploaded_at, chunk_count FROM document_metadata ORDER BY uploaded_at DESC')
        docs = c.fetchall()
        conn.close()
        return docs
    
    def get_document_count(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT COUNT(*) FROM document_metadata')
        count = c.fetchone()[0]
        conn.close()
        return count
    
    def update_system_stats(self, total_chunks):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('REPLACE INTO system_stats (id, last_indexing_time, total_chunks) VALUES (1, ?, ?)',
                 (datetime.now().isoformat(), total_chunks))
        conn.commit()
        conn.close()
    
    def get_system_stats(self):
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute('SELECT last_indexing_time, total_chunks FROM system_stats WHERE id = 1')
        stats = c.fetchone()
        conn.close()
        return stats if stats else (None, 0)


class VectorStore:
    def __init__(self, config):
        self.config = config
        self.dimension = 384
        self.index = None
        self.metadata = []
        self.client = LLMClient()
        self.load_or_create_index()
    
    def get_chunk_count(self):
        return len(self.metadata)
    
    def normalize_embedding(self, embedding):
        """Normalize embedding to unit length"""
        norm = np.linalg.norm(embedding)
        if norm == 0:
            return embedding
        return embedding / norm
    
    def load_or_create_index(self):
        index_path = Path(self.config.vector_store['index_file'])
        metadata_path = Path(self.config.vector_store['metadata_file'])
        
        if index_path.exists() and metadata_path.exists():
            self.index = faiss.read_index(str(index_path))
            with open(metadata_path, 'r', encoding='utf-8') as f:
                self.metadata = json.load(f)
            logger.info(f"Loaded index with {len(self.metadata)} chunks")
        else:
            # Use IndexFlatIP for inner product (works better with normalized embeddings)
            if self.config.vector_store.get('use_normalized_embeddings', True):
                self.index = faiss.IndexFlatIP(self.dimension)
            else:
                self.index = faiss.IndexFlatL2(self.dimension)
            self.metadata = []
            logger.info("Created new index")
    
    def save_index(self):
        Path(self.config.vector_store['index_file']).parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, self.config.vector_store['index_file'])
        with open(self.config.vector_store['metadata_file'], 'w', encoding='utf-8') as f:
            json.dump(self.metadata, f)
        logger.info(f"Saved index with {len(self.metadata)} chunks")
    
    def add_chunks(self, chunks, metadata_list):
        if not chunks:
            return
        
        embeddings = []
        for chunk in chunks:
            embedding = self.get_embedding(chunk)
            if self.config.vector_store.get('use_normalized_embeddings', True):
                embedding = self.normalize_embedding(embedding)
            embeddings.append(embedding)
        
        embeddings_np = np.array(embeddings).astype('float32')
        self.index.add(embeddings_np)
        self.metadata.extend(metadata_list)
        self.save_index()
    
    def get_embedding(self, text):
        response = self.client.embeddings(model=self.config.models['embedding'], prompt=text)
        return np.array(response['embedding'], dtype='float32')
    
    def search(self, query, k=None, filter_pdf_name=None):
        start_time = time.time()
        
        if len(self.metadata) == 0:
            return [], 0.0
        
        if k is None:
            k = self.config.vector_store.get('top_k', 3)
        
        query_embedding = self.get_embedding(query)
        if self.config.vector_store.get('use_normalized_embeddings', True):
            query_embedding = self.normalize_embedding(query_embedding)
        
        query_np = np.array([query_embedding]).astype('float32')
        # Search more results initially to account for filtering
        search_k = k * 3 if filter_pdf_name else k
        distances, indices = self.index.search(query_np, search_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(self.metadata):
                meta = self.metadata[idx]
                # Apply filter if specified
                if filter_pdf_name:
                    # Check if this chunk belongs to the filtered document
                    if meta['pdf_name'] != filter_pdf_name:
                        continue
                results.append({
                    'chunk': meta['chunk'],
                    'pdf_name': meta['pdf_name'],
                    'page': meta['page'],
                    'score': float(distances[0][i])
                })
                # Stop once we have enough results
                if len(results) >= k:
                    break
        
        latency = time.time() - start_time
        return results, latency
    
    def keyword_search(self, keyword, k=None):
        """
        Simple keyword search across all chunks
        
        Args:
            keyword: Search term
            k: Max results to return
            
        Returns:
            List of matching chunks with document info
        """
        if len(self.metadata) == 0:
            return []
        
        if k is None:
            k = 20
        
        keyword_lower = keyword.lower()
        results = []
        
        # First pass: check if keyword is in chunk
        for meta in self.metadata:
            chunk_lower = meta['chunk'].lower()
            if keyword_lower in chunk_lower:
                # Count occurrences for ranking
                count = chunk_lower.count(keyword_lower)
                results.append({
                    'chunk': meta['chunk'],
                    'pdf_name': meta['pdf_name'],
                    'page': meta['page'],
                    'score': count
                })
        
        # Sort by occurrence count (descending)
        results.sort(key=lambda x: x['score'], reverse=True)
        
        # Group by document and show top chunks per document
        doc_groups = {}
        for result in results:
            doc = result['pdf_name']
            if doc not in doc_groups:
                doc_groups[doc] = []
            doc_groups[doc].append(result)
        
        # Flatten, keeping at most 5 chunks per document
        final_results = []
        for doc, chunks in doc_groups.items():
            final_results.extend(chunks[:5])
            if len(final_results) >= k:
                break
        
        return final_results[:k]


class DocumentProcessor:
    def __init__(self, config):
        self.config = config
    
    def extract_text_from_pdf(self, pdf_path):
        reader = PdfReader(pdf_path)
        text_by_page = []
        for i, page in enumerate(reader.pages):
            text = page.extract_text()
            if text:
                text_by_page.append((i + 1, text))
        return text_by_page
    
    def extract_text_from_markdown(self, md_path):
        with open(md_path, 'r', encoding='utf-8') as f:
            text = f.read()
        return [(1, text)]  # Treat markdown as single page
    
    def chunk_text(self, text, page_num, filename):
        chunk_size = self.config.chunking['chunk_size']
        overlap = self.config.chunking['chunk_overlap']
        
        chunks = []
        start = 0
        text_len = len(text)
        
        if text_len == 0:
            return chunks
        
        while start < text_len:
            end = min(start + chunk_size, text_len)
            chunk = text[start:end]
            chunks.append({
                'chunk': chunk,
                'pdf_name': filename,  # Keep pdf_name for compatibility
                'page': page_num,
                'start_pos': start,
                'end_pos': end
            })
            next_start = end - overlap
            if next_start <= start:
                start = end
            else:
                start = next_start
        
        return chunks
    
    def process_file(self, file_path):
        filename = os.path.basename(file_path)
        file_ext = filename.lower()
        
        if file_ext.endswith('.pdf'):
            text_by_page = self.extract_text_from_pdf(file_path)
            filetype = 'pdf'
        elif file_ext.endswith('.md') or file_ext.endswith('.txt'):
            text_by_page = self.extract_text_from_markdown(file_path)
            filetype = 'markdown'
        else:
            return [], filetype
        
        all_chunks = []
        all_metadata = []
        
        for page_num, text in text_by_page:
            chunks = self.chunk_text(text, page_num, filename)
            all_chunks.extend([c['chunk'] for c in chunks])
            all_metadata.extend(chunks)
        
        return all_chunks, all_metadata, filetype
    
    def process_folder(self, folder_path):
        all_files = []
        
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_ext = file.lower()
                if file_ext.endswith('.pdf') or file_ext.endswith('.md') or file_ext.endswith('.txt'):
                    all_files.append(os.path.join(root, file))
        
        return all_files
