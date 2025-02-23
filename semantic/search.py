"""[5.0] Unified search functionality using embeddings and vector search.

Flow:
1. Search Capabilities:
   - Code search with vector similarity
   - Doc search with vector similarity
   - Graph-enhanced results
   
2. Integration Points:
   - Uses embeddings stored by FileProcessor
   - Uses graph analysis for enhanced results
   - Provides backward compatibility APIs

3. Search Pipeline:
   - Query embedding generation
   - Vector similarity search
   - Result enhancement and ranking
"""

from db.psql import query
from typing import List, Dict, Optional
import torch
from utils.logger import log
from utils.cache import cache
from embedding.embedding_models import code_embedder, doc_embedder
from ai_tools.graph_capabilities import graph_analysis
from parsers.models import (
    FileType,
    FileClassification,
    ParserResult,
    ExtractedFeatures
)
from utils.error_handling import (
    handle_async_errors,
    handle_errors,
    ProcessingError,
    DatabaseError,
    ErrorBoundary
)

class SearchEngine:
    """[5.1] Handles all search operations combining vector and graph-based search."""
    
    def __init__(self):
        self.code_embedder = code_embedder  # Same embedder as FileProcessor
        self.doc_embedder = doc_embedder    # Same embedder as FileProcessor
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_code(
        self,
        query_text: str,
        repo_id: Optional[int] = None,
        limit: int = 5,
        include_similar: bool = True
    ) -> List[Dict]:
        """[5.2] Search code using vector similarity and graph analysis.
        
        Flow:
        1. Generate query embedding
        2. Perform vector similarity search
        3. Enhance results with graph analysis
        4. Return ranked results
        """
        # Generate query embedding
        query_embedding = await self.code_embedder.embed_async(query_text)
        vector_literal = self._to_pgvector(query_embedding.tolist())
        
        # Perform vector search
        base_sql = """
        SELECT cs.id, cs.repo_id, cs.file_path, cs.ast,
               cs.embedding <=> $1::vector AS similarity
        FROM code_snippets cs
        """
        params = [vector_literal]
        if repo_id is not None:
            base_sql += " WHERE cs.repo_id = $2"
            params.append(repo_id)
        base_sql += " ORDER BY similarity ASC LIMIT $3;"
        params.append(limit)
        
        vector_results = await query(base_sql, tuple(params))
        
        if not include_similar or not vector_results:
            return vector_results
            
        # Enhance results with graph analysis
        enhanced_results = []
        for result in vector_results:
            similar_components = await graph_analysis.find_similar_components(
                file_path=result['file_path'],
                repo_id=result['repo_id'],
                similarity_cutoff=0.8
            )
            result['similar_components'] = similar_components
            result['code_metrics'] = await graph_analysis.get_code_metrics(
                repo_id=result['repo_id'],
                file_path=result['file_path']
            )
            enhanced_results.append(result)
            
        return enhanced_results
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_docs(
        self,
        query_text: str,
        repo_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict]:
        """[5.3] Search documentation using vector similarity."""
        query_embedding = await self.doc_embedder.embed_async(query_text)
        vector_literal = self._to_pgvector(query_embedding.tolist())
        
        base_sql = """
        SELECT rd.id, rd.file_path, rd.content, rd.doc_type,
               rd.embedding <=> $1::vector AS similarity
        FROM repo_docs rd
        """
        params = [vector_literal]
        if repo_id is not None:
            base_sql += " WHERE rd.repo_id = $2"
            params.append(repo_id)
        base_sql += " ORDER BY similarity ASC LIMIT $3;"
        params.append(limit)
        
        return await query(base_sql, tuple(params))
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_repo_docs(self, repo_id: int) -> List[Dict]:
        """Get all documents for a repository."""
        sql = """
        SELECT rd.* FROM repo_docs rd
        JOIN repo_doc_relations rdr ON rd.id = rdr.doc_id
        WHERE rdr.repo_id = %s
        """
        return await query(sql, (repo_id,))
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def create_doc_cluster(
        self,
        docs: List[Dict],
        cluster_name: str
    ) -> Dict:
        """Create a document cluster."""
        sql = """
        INSERT INTO doc_clusters (name, docs)
        VALUES (%s, %s)
        RETURNING id
        """
        result = await query(sql, (cluster_name, docs))
        return {"id": result[0]["id"], "name": cluster_name}
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def update_doc_version(
        self,
        doc_id: int,
        new_content: str
    ) -> Dict:
        """Update document version."""
        sql = """
        UPDATE repo_docs
        SET content = %s,
            updated_at = NOW()
        WHERE id = %s
        RETURNING id, file_path, content
        """
        return await query(sql, (new_content, doc_id))
    
    def _to_pgvector(self, vector_list: list) -> str:
        """[5.4] Convert vector to PGVector format."""
        return "[" + ", ".join(map(str, vector_list)) + "]"

# Global instance
search_engine = SearchEngine()

# Convenience functions for backward compatibility
async def search_code(*args, **kwargs) -> List[Dict]:
    return await search_engine.search_code(*args, **kwargs)

async def search_docs(*args, **kwargs) -> List[Dict]:
    return await search_engine.search_docs(*args, **kwargs)

@handle_async_errors(error_types=(ProcessingError, DatabaseError))
async def search_docs_common(query_embedding: torch.Tensor, repo_id: Optional[int] = None, limit: int = 5) -> List[Dict]:
    """Common document search functionality using embeddings."""
    vector_literal = search_engine._to_pgvector(query_embedding.tolist())
    
    base_sql = """
    SELECT rd.id, rd.file_path, rd.content, rd.doc_type,
           rd.embedding <=> $1::vector AS similarity
    FROM repo_docs rd
    """
    params = [vector_literal]
    if repo_id is not None:
        base_sql += """
        JOIN repo_doc_relations rdr ON rd.id = rdr.doc_id
        WHERE rdr.repo_id = $2
        """
        params.append(repo_id)
    base_sql += " ORDER BY similarity ASC LIMIT $3;"
    params.append(limit)
    
    return await query(base_sql, tuple(params))