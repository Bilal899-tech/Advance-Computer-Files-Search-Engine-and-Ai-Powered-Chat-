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
import ollama
import time
from datetime import datetime
from pypdf import PdfReader
from pathlib import Path

logger = logging.getLogger(__name__)


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
        self.client = ollama.Client(host=config.ollama['host'])
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
