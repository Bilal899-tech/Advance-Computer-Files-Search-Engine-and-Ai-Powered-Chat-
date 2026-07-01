"""
Smolagent Integration for PDF Chat Assistant
"""
import logging
from typing import List, Dict, Any, Optional
from core import Config, VectorStore, Database, DocumentProcessor

logger = logging.getLogger(__name__)


class KnowledgeAgent:
    """
    A smolagent-inspired RAG agent for handling multi-format knowledge base queries
    """
    
    def __init__(self, config: Config):
        self.config = config
        self.vector_store = VectorStore(config)
        self.db = Database(config.paths['database'])
    
    def search_knowledge(self, query: str, top_k: Optional[int] = None, filter_pdf_name: Optional[str] = None) -> tuple[List[Dict[str, Any]], float]:
        """
        Search the vector store for relevant context
        
        Args:
            query: User's question
            top_k: Number of results to retrieve (uses config default if not provided)
            filter_pdf_name: Only search within this specific document
            
        Returns:
            Tuple of (List of relevant context chunks, retrieval latency)
        """
        if top_k is None:
            top_k = self.config.vector_store.get('top_k', 3)
        
        results, latency = self.vector_store.search(query, k=top_k, filter_pdf_name=filter_pdf_name)
        logger.info(f"Search completed, found {len(results)} relevant chunks in {latency:.2f}s")
        return results, latency
    
    def format_context(self, search_results: List[Dict[str, Any]]) -> str:
        """
        Format search results into a clean context string
        
        Args:
            search_results: List of search result dicts
            
        Returns:
            Formatted context string
        """
        if not search_results:
            return "No relevant context available"
        
        context_parts = []
        for i, result in enumerate(search_results, 1):
            context_parts.append(f"--- Source {i} (Page {result['page']}, {result['pdf_name']}) ---")
            context_parts.append(result['chunk'])
        
        return "\n".join(context_parts)
    
    def build_prompt(self, query: str, context: str) -> str:
        """
        Build the prompt for the LLM
        
        Args:
            query: User's question
            context: Retrieved context
            
        Returns:
            Formatted prompt string
        """
        prompt = f"""You are a helpful, friendly AI assistant. Use ONLY the provided context to answer the user's question. 

Relevant context from uploaded documents:
{context}

If you cannot find the answer in the context, say: "I don't have information about that in the uploaded documents."

User Question: {query}

Answer in clear, natural language:"""
        
        return prompt
    
    def calculate_confidence(self, search_results: List[Dict[str, Any]]) -> float:
        """
        Calculate confidence score from search results
        
        Args:
            search_results: List of search result dicts
            
        Returns:
            Confidence score as percentage (0-100)
        """
        if not search_results:
            return 0.0
        
        # Use top result's score as confidence
        top_score = search_results[0]['score']
        # Normalize to 0-100 (assuming scores are between 0 and 1 for normalized embeddings)
        confidence = min(100, max(0, top_score * 100))
        return confidence
    
    def keyword_search_documents(self, keyword: str) -> List[Dict[str, Any]]:
        """
        Search documents by keyword
        
        Args:
            keyword: Search term
            
        Returns:
            List of matching document chunks
        """
        results = self.vector_store.keyword_search(keyword)
        logger.info(f"Keyword search for '{keyword}' found {len(results)} results")
        return results
