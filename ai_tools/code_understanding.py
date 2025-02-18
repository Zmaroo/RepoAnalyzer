from typing import Dict, List, Optional
from transformers import AutoTokenizer, AutoModel
import torch
import numpy as np
from utils.logger import log
from db.neo4j import run_query
from db.psql import query
from db.neo4j_projections import Neo4jProjections

class CodeUnderstanding:
    def __init__(self):
        # Content understanding
        self.tokenizer = AutoTokenizer.from_pretrained("microsoft/graphcodebert-base")
        self.model = AutoModel.from_pretrained("microsoft/graphcodebert-base")
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model.to(self.device)
        
        # Initialize graph projections
        self.graph_projections = Neo4jProjections()
        
    def analyze_codebase(self, repo_id: int) -> Dict:
        """
        Comprehensive codebase analysis combining:
        1. Graph structure (Neo4j)
        2. Code embeddings (PostgreSQL)
        3. Community detection
        4. Centrality analysis
        """
        # Create/update graph projection
        graph_name = f"code-repo-{repo_id}"
        self.graph_projections.create_code_dependency_projection(graph_name)
        
        # Get community structure
        communities = self.graph_projections.run_community_detection(graph_name)
        
        # Get central components
        central_components = self.graph_projections.run_centrality_analysis(graph_name)
        
        # Get embeddings from PostgreSQL
        embeddings_query = """
            SELECT file_path, embedding 
            FROM code_snippets 
            WHERE repo_id = %s AND embedding IS NOT NULL
        """
        code_embeddings = query(embeddings_query, (repo_id,))
        
        return {
            "communities": communities,
            "central_components": central_components,
            "embedded_files": len(code_embeddings) if code_embeddings else 0
        }

    def get_code_context(self, file_path: str, repo_id: int) -> Dict:
        """Get comprehensive context about a code file"""
        # Get graph-based relationships
        deps_query = """
        MATCH (n:Code {file_path: $file_path, repo_id: $repo_id})-[r]-(m:Code)
        RETURN type(r) as relationship_type,
               m.file_path as related_file,
               m.type as component_type
        """
        relationships = run_query(deps_query, {'file_path': file_path, 'repo_id': repo_id})
        
        # Get content-based similarities from PostgreSQL
        similar_query = """
            WITH target AS (
                SELECT embedding 
                FROM code_snippets 
                WHERE repo_id = %s AND file_path = %s
            )
            SELECT cs.file_path, 
                   1 - (cs.embedding <=> (SELECT embedding FROM target)) as similarity
            FROM code_snippets cs
            WHERE cs.repo_id = %s 
              AND cs.file_path != %s
              AND cs.embedding IS NOT NULL
            ORDER BY similarity DESC
            LIMIT 5
        """
        similar_files = query(similar_query, (repo_id, file_path, repo_id, file_path))
        
        return {
            "relationships": relationships,
            "similar_files": similar_files
        }

    def update_embeddings(self, file_path: str, repo_id: int, code_content: str):
        """Update both graph and content embeddings"""
        # Update content embedding in PostgreSQL
        embedding = self._get_content_embedding(code_content)
        update_query = """
            UPDATE code_snippets 
            SET embedding = %s 
            WHERE repo_id = %s AND file_path = %s
        """
        query(update_query, (embedding.tolist(), repo_id, file_path))
        
        # Ensure graph projection is up to date
        graph_name = f"code-repo-{repo_id}"
        self.graph_projections.create_code_dependency_projection(graph_name)

    def _get_content_embedding(self, code_content: str) -> np.ndarray:
        """Get semantic understanding of code content"""
        inputs = self.tokenizer(code_content, return_tensors="pt", 
                              truncation=True, max_length=512)
        inputs = {k: v.to(self.device) for k, v in inputs.items()}
        
        with torch.no_grad():
            outputs = self.model(**inputs)
        return outputs.last_hidden_state[:, 0, :].cpu().numpy() 