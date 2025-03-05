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
from utils.cache import cache_coordinator
from embedding.embedding_models import code_embedder, doc_embedder
from ai_tools.graph_capabilities import graph_analysis
from parsers.models import (
    FileType,
    FileClassification
)
from parsers.types import ParserResult, ExtractedFeatures
from utils.error_handling import (
    handle_async_errors,
    handle_errors,
    ProcessingError,
    DatabaseError,
    ErrorBoundary
)
import asyncio

class SearchEngine:
    """[5.1] Handles all search operations combining vector and graph-based search."""
    
    def __init__(self):
        self.code_embedder = code_embedder
        self.doc_embedder = doc_embedder
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_code(
        self,
        query_text: str,
        repo_id: Optional[int] = None,
        limit: int = 5,
        include_similar: bool = True
    ) -> List[Dict]:
        query_embedding = await self.code_embedder.embed_async(query_text)
        vector_literal = self._to_pgvector(query_embedding.tolist())
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
        
        async def enhance_result(result: Dict) -> Dict:
            similar_components, code_metrics = await asyncio.gather(
                graph_analysis.find_similar_components(
                    file_path=result['file_path'],
                    repo_id=result['repo_id'],
                    similarity_cutoff=0.8
                ),
                graph_analysis.get_code_metrics(
                    repo_id=result['repo_id'],
                    file_path=result['file_path']
                )
            )
            result['similar_components'] = similar_components
            result['code_metrics'] = code_metrics
            return result
        
        enhanced_results = await asyncio.gather(*(enhance_result(result) for result in vector_results))
        return enhanced_results
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_docs(
        self,
        query_text: str,
        repo_id: Optional[int] = None,
        limit: int = 5
    ) -> List[Dict]:
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
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def search_patterns(
        self,
        query_text: str,
        repo_id: Optional[int] = None,
        pattern_type: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict]:
        """Search for learned patterns matching the query."""
        query_embedding = await self.code_embedder.embed_async(query_text)
        vector_literal = self._to_pgvector(query_embedding.tolist())
        
        base_sql = """
        SELECT cp.id, cp.pattern_type, cp.content, cp.confidence,
               cp.repo_id, cp.language, cp.example_usage,
               cp.embedding <=> $1::vector AS similarity
        FROM code_patterns cp
        """
        params = [vector_literal]
        conditions = []
        
        if repo_id is not None:
            conditions.append("cp.repo_id = $2")
            params.append(repo_id)
        
        if pattern_type is not None:
            conditions.append(f"cp.pattern_type = ${len(params) + 1}")
            params.append(pattern_type)
        
        if conditions:
            base_sql += " WHERE " + " AND ".join(conditions)
        
        base_sql += " ORDER BY similarity ASC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        
        return await query(base_sql, tuple(params))
    
    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_repository_patterns(
        self,
        repo_id: int,
        pattern_type: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict]:
        """Get patterns from a specific reference repository."""
        sql = """
        SELECT cp.id, cp.pattern_type, cp.content, cp.confidence,
               cp.language, cp.example_usage
        FROM code_patterns cp
        WHERE cp.repo_id = $1
        """
        params = [repo_id]
        
        if pattern_type is not None:
            sql += " AND cp.pattern_type = $2"
            params.append(pattern_type)
        
        sql += " ORDER BY cp.confidence DESC LIMIT $" + str(len(params) + 1)
        params.append(limit)
        
        return await query(sql, tuple(params))
    
    def _to_pgvector(self, embedding: list) -> str:
        # Convert list to PostgreSQL vector literal; adjust implementation as needed.
        return " ".join(map(str, embedding))

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