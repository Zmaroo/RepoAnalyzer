"""[4.4] Reference Repository Learning

Flow:
1. Learning Operations:
   - Extract patterns from reference repositories
   - Identify best practices and conventions
   - Create learning vectors for patterns
   - Identify similarities between current project and reference repos

2. Integration Points:
   - CodeEmbedder [3.1]: Code embeddings
   - Neo4jProjections [6.2]: Graph operations
   - AIAssistant [4.1]: AI interface
   - CodeUnderstanding [4.2]: Code analysis

3. Error Handling:
   - ProcessingError: Learning operations
   - DatabaseError: Storage operations
"""
from typing import Dict, List, Optional, Any, Tuple
import asyncio
import numpy as np
from utils.logger import log
from db.neo4j_ops import run_query, Neo4jProjections, Neo4jTools
from db.psql import query
from embedding.embedding_models import code_embedder, DocEmbedder
from utils.error_handling import handle_errors, handle_async_errors, ProcessingError, DatabaseError, ErrorBoundary, AsyncErrorBoundary, TransactionError
from parsers.models import FileType, FileClassification
from parsers.types import Documentation, ComplexityMetrics, ExtractedFeatures, ParserResult
from ai_tools.code_understanding import CodeUnderstanding
import os
from db.graph_sync import graph_sync
from neo4j.exceptions import Neo4jError


class ReferenceRepositoryLearning:
    """[4.4.1] Reference repository learning capabilities."""

    def __init__(self):
        with ErrorBoundary(error_types=ProcessingError, operation_name=
            'model initialization'):
            self.graph_projections = Neo4jProjections()
            self.code_understanding = CodeUnderstanding()
            self.embedder = code_embedder
            self.doc_embedder = DocEmbedder()
            self.neo4j_tools = Neo4jTools()

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def learn_from_repository(self, reference_repo_id: int) ->Dict[
        str, Any]:
        """[4.4.2] Learn patterns and best practices from a reference repository."""
        async with AsyncErrorBoundary(operation_name=
            'reference repository learning'):
            code_patterns = await self._extract_code_patterns(reference_repo_id
                )
            doc_patterns = await self._extract_doc_patterns(reference_repo_id)
            arch_patterns = await self._extract_architecture_patterns(
                reference_repo_id)
            pattern_ids = await self._store_patterns(reference_repo_id,
                code_patterns, doc_patterns, arch_patterns)
            await graph_sync.ensure_pattern_projection(reference_repo_id)
            similarity_results = (await self.graph_projections.
                run_pattern_similarity(f'pattern-repo-{reference_repo_id}'))
            pattern_clusters = (await self.graph_projections.
                find_pattern_clusters(f'pattern-repo-{reference_repo_id}'))
            return {'code_patterns': len(code_patterns), 'doc_patterns':
                len(doc_patterns), 'architecture_patterns': len(
                arch_patterns), 'pattern_similarities': len(
                similarity_results), 'pattern_clusters': len(
                pattern_clusters), 'repository_id': reference_repo_id}

    @handle_async_errors(error_types=ProcessingError)
    async def _extract_code_patterns(self, repo_id: int) ->List[Dict[str, Any]
        ]:
        """Extract code patterns from repository."""
        patterns = []
        files_query = """
            SELECT file_path, file_content, language 
            FROM file_metadata 
            WHERE repo_id = $repo_id AND file_type = 'CODE'
        """
        files = await query(files_query, {'repo_id': repo_id})
        for file in files:
            structure_query = """
                MATCH (f:Code {repo_id: $repo_id, file_path: $file_path})-[:CONTAINS]->(n)
                RETURN n.type as node_type, n.name as name, COUNT(n) as count
                ORDER BY count DESC
                LIMIT 20
            """
            structure = await run_query(structure_query, {'repo_id':
                repo_id, 'file_path': file['file_path']})
            if structure:
                common_nodes = [node for node in structure if node['count'] > 3
                    ]
                if common_nodes:
                    pattern_text = file['file_content'][:1000]
                    from utils.error_handling import ErrorBoundary
                    embedding_list = None

@handle_errors(error_types=(Exception,))
                    def create_embedding():
                        nonlocal embedding_list
                        embedding = self.embedder.embed(pattern_text)
                        embedding_list = embedding.tolist() if isinstance(
                            embedding, np.ndarray) else None
                    try:
                        with AsyncErrorBoundary(error_types=(ValueError,
                            ImportError, ProcessingError), operation_name=
                            'pattern embedding'):
                            create_embedding()
                    except Exception:
                        pass
                    pattern = {'file_path': file['file_path'], 'language':
                        file['language'], 'pattern_type': 'code_structure',
                        'elements': common_nodes, 'sample': pattern_text,
                        'embedding': embedding_list}
                    patterns.append(pattern)
        return patterns

    @handle_async_errors(error_types=ProcessingError)
    async def _extract_doc_patterns(self, repo_id: int) ->List[Dict[str, Any]]:
        """Extract documentation patterns from repository."""
        patterns = []
        docs_query = """
            SELECT d.doc_id, d.title, d.content, d.doc_type, f.file_path 
            FROM documentation d
            JOIN file_metadata f ON d.file_id = f.file_id
            WHERE f.repo_id = $repo_id
        """
        docs = await query(docs_query, {'repo_id': repo_id})
        doc_types = {}
        for doc in docs:
            doc_type = doc['doc_type']
            if doc_type not in doc_types:
                doc_types[doc_type] = []
            doc_types[doc_type].append(doc)
        for doc_type, type_docs in doc_types.items():
            if len(type_docs) > 3:
                sample_texts = [doc['content'][:500] for doc in type_docs[:3]]
                combined_text = '\n'.join(sample_texts)
                try:
                    embedding = self.doc_embedder.embed(combined_text)
                    embedding_list = embedding.tolist() if isinstance(embedding
                        , np.ndarray) else None
                except Exception as e:
                    log(f'Error creating embedding for doc pattern: {e}',
                        level='error')
                    embedding_list = None
                pattern = {'doc_type': doc_type, 'pattern_type':
                    'documentation', 'count': len(type_docs), 'samples':
                    sample_texts, 'common_structure': self.
                    _analyze_doc_structure(type_docs), 'embedding':
                    embedding_list}
                patterns.append(pattern)
        return patterns

    @handle_async_errors(error_types=ProcessingError)
    async def _extract_architecture_patterns(self, repo_id: int) ->List[Dict
        [str, Any]]:
        """Extract architecture patterns from repository."""
        patterns = []
        structure_query = """
            SELECT file_path 
            FROM file_metadata 
            WHERE repo_id = $repo_id
            ORDER BY file_path
        """
        files = await query(structure_query, {'repo_id': repo_id})
        directories = {}
        for file in files:
            path = file['file_path']
            parts = path.split('/')
            current = directories
            for i, part in enumerate(parts[:-1]):
                if part not in current:
                    current[part] = {}
                current = current[part]
        if directories:
            pattern = {'pattern_type': 'architecture',
                'directory_structure': directories, 'top_level_dirs': list(
                directories.keys())}
            patterns.append(pattern)
            graph_name = f'code-repo-{repo_id}'
            try:
                dependencies = (await self.graph_projections.
                    get_component_dependencies(graph_name))
                if dependencies:
                    pattern = {'pattern_type': 'component_dependencies',
                        'dependencies': dependencies}
                    patterns.append(pattern)
            except Exception as e:
                log(f'Error getting component dependencies: {e}', level='error'
                    )
        return patterns

    @handle_errors(error_types=ProcessingError)
    def _analyze_doc_structure(self, docs: List[Dict]) ->Dict[str, Any]:
        """Analyze the common structure of documentation."""
        headings = []
        for doc in docs:
            content = doc['content']
            doc_headings = []
            for line in content.split('\n'):
                line = line.strip()
                if line.startswith('#'):
                    level = 0
                    while level < len(line) and line[level] == '#':
                        level += 1
                    if level < len(line) and line[level] == ' ':
                        heading = line[level + 1:].strip()
                        doc_headings.append({'level': level, 'text': heading})
            if doc_headings:
                headings.append(doc_headings)
        common_headings = []
        if headings:
            all_first_level = []
            for doc_headings in headings:
                first_level = [h for h in doc_headings if h['level'] == 1]
                if first_level:
                    all_first_level.extend(first_level)
            heading_counts = {}
            for heading in all_first_level:
                text = heading['text'].lower()
                if text not in heading_counts:
                    heading_counts[text] = 0
                heading_counts[text] += 1
            common_headings = sorted([{'text': text, 'count': count} for 
                text, count in heading_counts.items()], key=lambda x: x[
                'count'], reverse=True)[:5]
        return {'common_headings': common_headings, 'avg_heading_count': 
            sum(len(h) for h in headings) / max(1, len(headings))}

    @handle_async_errors(error_types=DatabaseError)
    async def _store_patterns(self, repo_id: int, code_patterns: List[Dict],
        doc_patterns: List[Dict], arch_patterns: List[Dict]) ->List[int]:
        """Store extracted patterns in database and Neo4j."""
        pattern_ids = []
        for pattern in code_patterns:
            pattern_query = """
                INSERT INTO code_patterns (
                    repo_id, file_path, language, pattern_type, elements, sample
                ) VALUES (
                    $repo_id, $file_path, $language, $pattern_type, $elements, $sample
                )
                ON CONFLICT (repo_id, file_path, pattern_type)
                DO UPDATE SET
                    elements = $elements,
                    sample = $sample
                RETURNING pattern_id
            """
            result = await query(pattern_query, {'repo_id': repo_id,
                'file_path': pattern['file_path'], 'language': pattern[
                'language'], 'pattern_type': pattern['pattern_type'],
                'elements': pattern['elements'], 'sample': pattern['sample']})
            if result and result[0]:
                pattern_id = result[0]['pattern_id']
                pattern_ids.append(pattern_id)
                pattern_node = {'repo_id': repo_id, 'pattern_id':
                    pattern_id, 'pattern_type': pattern['pattern_type'],
                    'language': pattern['language'], 'file_path': pattern[
                    'file_path'], 'embedding': pattern.get('embedding'),
                    'elements': pattern['elements']}
                await self.neo4j_tools.store_pattern_node(pattern_node)
        for pattern in doc_patterns:
            pattern_query = """
                INSERT INTO doc_patterns (
                    repo_id, doc_type, pattern_type, count, samples, common_structure
                ) VALUES (
                    $repo_id, $doc_type, $pattern_type, $count, $samples, $common_structure
                )
                ON CONFLICT (repo_id, doc_type, pattern_type)
                DO UPDATE SET
                    count = $count,
                    samples = $samples,
                    common_structure = $common_structure
                RETURNING pattern_id
            """
            result = await query(pattern_query, {'repo_id': repo_id,
                'doc_type': pattern['doc_type'], 'pattern_type': pattern[
                'pattern_type'], 'count': pattern['count'], 'samples':
                pattern['samples'], 'common_structure': pattern[
                'common_structure']})
            if result and result[0]:
                pattern_id = result[0]['pattern_id']
                pattern_ids.append(pattern_id)
                pattern_node = {'repo_id': repo_id, 'pattern_id':
                    pattern_id, 'pattern_type': pattern['pattern_type'],
                    'doc_type': pattern['doc_type'], 'count': pattern[
                    'count'], 'embedding': pattern.get('embedding'),
                    'common_structure': pattern['common_structure']}
                await self.neo4j_tools.store_pattern_node(pattern_node)
        for pattern in arch_patterns:
            if pattern['pattern_type'] == 'architecture':
                pattern_query = """
                    INSERT INTO arch_patterns (
                        repo_id, pattern_type, directory_structure, top_level_dirs
                    ) VALUES (
                        $repo_id, $pattern_type, $directory_structure, $top_level_dirs
                    )
                    ON CONFLICT (repo_id, pattern_type)
                    DO UPDATE SET
                        directory_structure = $directory_structure,
                        top_level_dirs = $top_level_dirs
                    RETURNING pattern_id
                """
                result = await query(pattern_query, {'repo_id': repo_id,
                    'pattern_type': pattern['pattern_type'],
                    'directory_structure': pattern['directory_structure'],
                    'top_level_dirs': pattern['top_level_dirs']})
                if result and result[0]:
                    pattern_id = result[0]['pattern_id']
                    pattern_ids.append(pattern_id)
                    pattern_node = {'repo_id': repo_id, 'pattern_id':
                        pattern_id, 'pattern_type': pattern['pattern_type'],
                        'directory_structure': pattern[
                        'directory_structure'], 'top_level_dirs': pattern[
                        'top_level_dirs']}
                    await self.neo4j_tools.store_pattern_node(pattern_node)
            elif pattern['pattern_type'] == 'component_dependencies':
                pattern_query = """
                    INSERT INTO arch_patterns (
                        repo_id, pattern_type, dependencies
                    ) VALUES (
                        $repo_id, $pattern_type, $dependencies
                    )
                    ON CONFLICT (repo_id, pattern_type)
                    DO UPDATE SET
                        dependencies = $dependencies
                    RETURNING pattern_id
                """
                result = await query(pattern_query, {'repo_id': repo_id,
                    'pattern_type': pattern['pattern_type'], 'dependencies':
                    pattern['dependencies']})
                if result and result[0]:
                    pattern_id = result[0]['pattern_id']
                    pattern_ids.append(pattern_id)
                    pattern_node = {'repo_id': repo_id, 'pattern_id':
                        pattern_id, 'pattern_type': pattern['pattern_type'],
                        'dependencies': pattern['dependencies']}
                    await self.neo4j_tools.store_pattern_node(pattern_node)
        await self.neo4j_tools.link_patterns_to_repository(repo_id,
            pattern_ids, is_reference=True)
        return pattern_ids

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def apply_patterns_to_project(self, reference_repo_id: int,
        target_repo_id: int) ->Dict[str, Any]:
        """[4.4.3] Apply learned patterns to a target project."""
        async with AsyncErrorBoundary(operation_name=
            'applying reference patterns'):
            code_patterns = await self._get_code_patterns(reference_repo_id)
            doc_patterns = await self._get_doc_patterns(reference_repo_id)
            arch_patterns = await self._get_arch_patterns(reference_repo_id)
            target_analysis = await self.code_understanding.analyze_codebase(
                target_repo_id)
            comparison_results = (await graph_sync.
                compare_repository_structures(active_repo_id=target_repo_id,
                reference_repo_id=reference_repo_id))
            log(f"Repository structure comparison complete with {comparison_results.get('similarity_count', 0)} similarities found"
                , level='info')
            code_recommendations = (await self.
                _generate_enhanced_code_recommendations(code_patterns,
                target_repo_id, target_analysis, comparison_results))
            doc_recommendations = self._generate_doc_recommendations(
                doc_patterns, target_repo_id)
            arch_recommendations = self._generate_arch_recommendations(
                arch_patterns, target_repo_id, target_analysis)
            pattern_ids = [rec['pattern_id'] for rec in 
                code_recommendations + doc_recommendations +
                arch_recommendations if 'pattern_id' in rec]
            if pattern_ids:
                await self.neo4j_tools.link_patterns_to_repository(
                    target_repo_id, pattern_ids, is_reference=False)
            return {'code_recommendations': code_recommendations,
                'doc_recommendations': doc_recommendations,
                'arch_recommendations': arch_recommendations,
                'reference_repo_id': reference_repo_id, 'target_repo_id':
                target_repo_id, 'applied_patterns': len(pattern_ids),
                'similarity_score': comparison_results.get(
                'similarity_count', 0) / 20 if comparison_results.get(
                'similarity_count') else 0}

    @handle_async_errors(error_types=DatabaseError)
    async def _get_code_patterns(self, repo_id: int) ->List[Dict]:
        """Get code patterns from database."""
        patterns_query = """
            SELECT * FROM code_patterns WHERE repo_id = $repo_id
        """
        return await query(patterns_query, {'repo_id': repo_id})

    @handle_async_errors(error_types=DatabaseError)
    async def _get_doc_patterns(self, repo_id: int) ->List[Dict]:
        """Get documentation patterns from database."""
        patterns_query = """
            SELECT * FROM doc_patterns WHERE repo_id = $repo_id
        """
        return await query(patterns_query, {'repo_id': repo_id})

    @handle_async_errors(error_types=DatabaseError)
    async def _get_arch_patterns(self, repo_id: int) ->List[Dict]:
        """Get architecture patterns from database."""
        patterns_query = """
            SELECT * FROM arch_patterns WHERE repo_id = $repo_id
        """
        return await query(patterns_query, {'repo_id': repo_id})

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def _generate_enhanced_code_recommendations(self, patterns: List[
        Dict], target_repo_id: int, target_analysis: Dict,
        comparison_results: Dict[str, Any]) ->List[Dict]:
        """Generate code recommendations based on patterns using graph comparison results."""
        recommendations = []
        if 'similarities' in comparison_results and comparison_results[
            'similarities']:
            for similarity in comparison_results['similarities']:
                active_file = similarity.get('active_file')
                reference_file = similarity.get('reference_file')
                similarity_score = similarity.get('similarity')
                matching_patterns = []
                for pattern in patterns:
                    if pattern.get('file_path') == reference_file:
                        matching_patterns.append(pattern)
                for pattern in matching_patterns:
                    recommendation = {'pattern_type': pattern[
                        'pattern_type'], 'language': pattern['language'],
                        'target_file': active_file, 'reference_file':
                        reference_file, 'recommendation':
                        f"Apply {pattern['pattern_type']} pattern from {reference_file} to {active_file}"
                        , 'similarity': similarity_score, 'confidence': 
                        0.85, 'sample': pattern['sample'], 'pattern_id':
                        pattern['pattern_id']}
                    recommendations.append(recommendation)
        if not recommendations:
            files_query = """
                SELECT file_path, language FROM file_metadata 
                WHERE repo_id = $repo_id AND file_type = 'CODE'
            """
            files = await query(files_query, {'repo_id': target_repo_id})
            for file in files:
                pattern_recs = await self.neo4j_tools.find_similar_patterns(
                    target_repo_id, file['file_path'], limit=3)
                for pattern in pattern_recs:
                    if any(p['pattern_id'] == pattern['pattern_id'] for p in
                        patterns):
                        recommendation = {'pattern_type': pattern[
                            'pattern_type'], 'language': pattern['language'
                            ], 'target_file': file['file_path'],
                            'recommendation':
                            f"Consider using this {pattern['language']} pattern"
                            , 'sample': pattern['sample'], 'confidence': 
                            0.75, 'pattern_id': pattern['pattern_id']}
                        recommendations.append(recommendation)
        if not recommendations:
            languages_query = """
                SELECT DISTINCT language FROM file_metadata 
                WHERE repo_id = $repo_id AND language IS NOT NULL
            """
            languages = await query(languages_query, {'repo_id':
                target_repo_id})
            target_languages = [lang['language'] for lang in languages]
            filtered_patterns = [p for p in patterns if p['language'] in
                target_languages]
            for pattern in filtered_patterns[:5]:
                recommendation = {'pattern_type': pattern['pattern_type'],
                    'language': pattern['language'], 'recommendation':
                    f"Consider using this {pattern['language']} pattern",
                    'sample': pattern['sample'], 'confidence': 0.7,
                    'pattern_id': pattern['pattern_id']}
                recommendations.append(recommendation)
        return recommendations

    @handle_errors(error_types=ProcessingError)
    def _generate_doc_recommendations(self, patterns: List[Dict],
        target_repo_id: int) ->List[Dict]:
        """Generate documentation recommendations based on patterns."""
        recommendations = []
        try:
            for pattern in patterns:
                recommendation = {'doc_type': pattern['doc_type'],
                    'pattern_type': pattern['pattern_type'],
                    'recommendation':
                    f"Consider using this documentation pattern for {pattern['doc_type']}"
                    , 'structure': pattern['common_structure'],
                    'confidence': 0.8, 'pattern_id': pattern['pattern_id']}
                recommendations.append(recommendation)
        except Exception as e:
            log(f'Error generating doc recommendations: {e}', level='error')
        return recommendations

    @handle_errors(error_types=ProcessingError)
    def _generate_arch_recommendations(self, patterns: List[Dict],
        target_repo_id: int, target_analysis: Dict) ->List[Dict]:
        """Generate architecture recommendations based on patterns."""
        recommendations = []
        try:
            for pattern in patterns:
                if pattern['pattern_type'] == 'architecture':
                    recommendation = {'pattern_type': pattern[
                        'pattern_type'], 'recommendation':
                        'Consider this directory structure',
                        'top_level_dirs': pattern['top_level_dirs'],
                        'confidence': 0.8, 'pattern_id': pattern['pattern_id']}
                    recommendations.append(recommendation)
                elif pattern['pattern_type'] == 'component_dependencies':
                    recommendation = {'pattern_type': pattern[
                        'pattern_type'], 'recommendation':
                        'Consider these component relationships',
                        'dependencies': pattern['dependencies'],
                        'confidence': 0.7, 'pattern_id': pattern['pattern_id']}
                    recommendations.append(recommendation)
        except Exception as e:
            log(f'Error generating arch recommendations: {e}', level='error')
        return recommendations

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def analyze_pattern_relationships(self, repo_id: int) ->Dict[str, Any
        ]:
        """[4.4.4] Analyze relationships between patterns using graph algorithms."""
        await graph_sync.ensure_pattern_projection(repo_id)
        pattern_graph_name = f'pattern-repo-{repo_id}'
        similarity_results = (await self.graph_projections.
            run_pattern_similarity(pattern_graph_name))
        pattern_clusters = await self.graph_projections.find_pattern_clusters(
            pattern_graph_name)
        return {'pattern_similarities': similarity_results,
            'pattern_clusters': pattern_clusters, 'total_similarities': len
            (similarity_results), 'total_clusters': len(pattern_clusters)}

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def compare_with_reference_repository(self, active_repo_id: int,
        reference_repo_id: int) ->Dict[str, Any]:
        """[4.4.5] Compare active repository with reference repository using graph projections."""
        await graph_sync.ensure_projection(active_repo_id)
        await graph_sync.ensure_projection(reference_repo_id)
        comparison_results = await graph_sync.compare_repository_structures(
            active_repo_id=active_repo_id, reference_repo_id=reference_repo_id)
        patterns_query = """
            SELECT COUNT(*) as pattern_count 
            FROM (
                SELECT pattern_id FROM code_patterns WHERE repo_id = $repo_id
                UNION
                SELECT pattern_id FROM doc_patterns WHERE repo_id = $repo_id
                UNION
                SELECT pattern_id FROM arch_patterns WHERE repo_id = $repo_id
            ) AS patterns
        """
        active_patterns = await query(patterns_query, {'repo_id':
            active_repo_id})
        reference_patterns = await query(patterns_query, {'repo_id':
            reference_repo_id})
        comparison_results['active_patterns_count'] = active_patterns[0][
            'pattern_count'] if active_patterns else 0
        comparison_results['reference_patterns_count'] = reference_patterns[0][
            'pattern_count'] if reference_patterns else 0
        return comparison_results

    @handle_errors(error_types=ProcessingError)
    def cleanup(self) ->None:
        """Cleanup resources."""
        try:
            self.code_understanding.cleanup()
            self.neo4j_tools.close()
        except Exception as e:
            log(f'Error during reference learning cleanup: {e}', level='error')

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def deep_learn_from_multiple_repositories(self, repo_ids: List[int]
        ) ->Dict[str, Any]:
        """[4.4.6] Deep learn from multiple reference repositories by analyzing cross-repository patterns.
        
        This method utilizes the enhanced graph synchronization capabilities to perform deep learning
        across multiple reference repositories, identifying common patterns that appear in high-quality
        repositories and can be considered industry best practices.
        """
        from utils.error_handling import AsyncErrorBoundary
        if len(repo_ids) < 2:
            raise ValueError(
                'At least two repositories are required for cross-repository learning'
                )
        learning_results = []
        for repo_id in repo_ids:
            async with AsyncErrorBoundary(f'learning_from_repository_{repo_id}'
                , error_types=(ProcessingError, DatabaseError, Neo4jError,
                ValueError)):
                result = await self.learn_from_repository(repo_id)
                learning_results.append(result)
                await graph_sync.ensure_projection(repo_id)
                await graph_sync.ensure_pattern_projection(repo_id)
        comparison_matrix = []
        for i, repo_id1 in enumerate(repo_ids):
            for repo_id2 in repo_ids[i + 1:]:
                async with AsyncErrorBoundary(
                    f'comparing_repositories_{repo_id1}_{repo_id2}',
                    error_types=(Neo4jError, TransactionError,
                    DatabaseError, ProcessingError)):
                    comparison = (await graph_sync.
                        compare_repository_structures(active_repo_id=
                        repo_id1, reference_repo_id=repo_id2))
                    comparison_matrix.append({'repo_id1': repo_id1,
                        'repo_id2': repo_id2, 'similarity_count':
                        comparison.get('similarity_count', 0),
                        'similarities': comparison.get('similarities', [])})
        common_patterns = await self._identify_common_patterns_across_repos(
            repo_ids)
        await self._store_cross_repository_patterns(repo_ids, common_patterns)
        return {'repositories_processed': len(learning_results),
            'repository_comparisons': len(comparison_matrix),
            'common_patterns_identified': len(common_patterns),
            'cross_repository_learning_complete': True}

    @handle_async_errors(error_types=DatabaseError)
    async def _identify_common_patterns_across_repos(self, repo_ids: List[int]
        ) ->List[Dict[str, Any]]:
        """Identify patterns that are common across multiple repositories."""
        common_patterns = []
        similar_code_patterns_query = """
        MATCH (p1:Pattern)-[:EXTRACTED_FROM]->(c1:Code {repo_id: $repo_id1})
        MATCH (p2:Pattern)-[:EXTRACTED_FROM]->(c2:Code {repo_id: $repo_id2})
        WHERE c1.language = c2.language AND p1.pattern_type = p2.pattern_type
        WITH p1, p2, c1.language AS language
        RETURN p1.pattern_id AS pattern_id1, 
               p2.pattern_id AS pattern_id2, 
               p1.pattern_type AS pattern_type,
               language
        LIMIT 100
        """
        for i, repo_id1 in enumerate(repo_ids):
            for repo_id2 in repo_ids[i + 1:]:
                similar_patterns = await run_query(similar_code_patterns_query,
                    {'repo_id1': repo_id1, 'repo_id2': repo_id2})
                pattern_groups = {}
                for pattern in similar_patterns:
                    key = f"{pattern['pattern_type']}:{pattern['language']}"
                    if key not in pattern_groups:
                        pattern_groups[key] = []
                    pattern_groups[key].append(pattern)
                for key, patterns in pattern_groups.items():
                    if len(patterns) >= 2:
                        pattern_type, language = key.split(':')
                        common_pattern = {'pattern_type': pattern_type,
                            'language': language, 'source_patterns':
                            patterns, 'repo_ids': [repo_id1, repo_id2],
                            'confidence': 0.8 + 0.05 * len(patterns)}
                        common_patterns.append(common_pattern)
        return common_patterns

    @handle_async_errors(error_types=DatabaseError)
    async def _store_cross_repository_patterns(self, repo_ids: List[int],
        common_patterns: List[Dict[str, Any]]) ->None:
        """Store patterns that are common across multiple repositories."""
        meta_repo_query = """
        MERGE (m:MetaRepository {id: $meta_id})
        SET m.repo_ids = $repo_ids,
            m.name = 'Cross-Repository Patterns',
            m.created_at = timestamp()
        """
        meta_id = hash(tuple(sorted(repo_ids))) & 2147483647
        await run_query(meta_repo_query, {'meta_id': meta_id, 'repo_ids':
            repo_ids})
        for i, pattern in enumerate(common_patterns):
            pattern_query = """
            CREATE (p:CrossRepositoryPattern {
                id: $pattern_id,
                meta_id: $meta_id,
                pattern_type: $pattern_type,
                language: $language,
                confidence: $confidence
            })
            RETURN id(p) as node_id
            """
            pattern_result = await run_query(pattern_query, {'pattern_id': 
                meta_id * 10000 + i, 'meta_id': meta_id, 'pattern_type':
                pattern['pattern_type'], 'language': pattern['language'],
                'confidence': pattern['confidence']})
            if pattern_result:
                node_id = pattern_result[0]['node_id']
                for source_pattern in pattern['source_patterns']:
                    link_query = """
                    MATCH (cp:CrossRepositoryPattern) WHERE id(cp) = $node_id
                    MATCH (p:Pattern {pattern_id: $pattern_id, repo_id: $repo_id})
                    MERGE (cp)-[:DERIVED_FROM]->(p)
                    """
                    await run_query(link_query, {'node_id': node_id,
                        'pattern_id': source_pattern['pattern_id1'],
                        'repo_id': pattern['repo_ids'][0]})
                    await run_query(link_query, {'node_id': node_id,
                        'pattern_id': source_pattern['pattern_id2'],
                        'repo_id': pattern['repo_ids'][1]})
                meta_link_query = """
                MATCH (cp:CrossRepositoryPattern) WHERE id(cp) = $node_id
                MATCH (m:MetaRepository {id: $meta_id})
                MERGE (m)-[:CONTAINS_PATTERN]->(cp)
                """
                await run_query(meta_link_query, {'node_id': node_id,
                    'meta_id': meta_id})
        log(f'Stored {len(common_patterns)} cross-repository patterns in meta-repository {meta_id}'
            , level='info')

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def get_cross_repository_patterns(self, repo_ids: List[int]) ->Dict[
        str, Any]:
        """[4.4.7] Retrieve patterns common across multiple repositories."""
        meta_id = hash(tuple(sorted(repo_ids))) & 2147483647
        check_query = """
        MATCH (m:MetaRepository {id: $meta_id})
        RETURN m.created_at as created_at
        """
        meta_result = await run_query(check_query, {'meta_id': meta_id})
        if not meta_result:
            await self.deep_learn_from_multiple_repositories(repo_ids)
        patterns_query = """
        MATCH (m:MetaRepository {id: $meta_id})-[:CONTAINS_PATTERN]->(cp:CrossRepositoryPattern)
        OPTIONAL MATCH (cp)-[:DERIVED_FROM]->(p:Pattern)-[:EXTRACTED_FROM]->(c:Code)
        RETURN cp.id as pattern_id,
               cp.pattern_type as pattern_type,
               cp.language as language,
               cp.confidence as confidence,
               collect(distinct p.pattern_id) as source_patterns,
               collect(distinct c.file_path) as example_files
        """
        patterns = await run_query(patterns_query, {'meta_id': meta_id})
        return {'meta_repository_id': meta_id, 'repository_ids': repo_ids,
            'pattern_count': len(patterns), 'patterns': patterns}

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def apply_cross_repository_patterns(self, target_repo_id: int,
        repo_ids: List[int]) ->Dict[str, Any]:
        """[4.4.8] Apply patterns common across reference repositories to a target repository.
        
        This method applies the deep learning patterns identified across multiple high-quality
        repositories to a target repository, providing high-confidence recommendations based
        on industry best practices.
        """
        cross_patterns = await self.get_cross_repository_patterns(repo_ids)
        if not cross_patterns or not cross_patterns.get('patterns'):
            return {'target_repo_id': target_repo_id,
                'recommendations_count': 0, 'status':
                'No cross-repository patterns found'}
        target_analysis = await self.code_understanding.analyze_codebase(
            target_repo_id)
        recommendations = []
        lang_query = """
        SELECT DISTINCT language FROM file_metadata
        WHERE repo_id = $repo_id AND language IS NOT NULL
        """
        languages = await query(lang_query, {'repo_id': target_repo_id})
        target_languages = [lang['language'] for lang in languages]
        for pattern in cross_patterns.get('patterns', []):
            if pattern['language'] in target_languages:
                files_query = """
                SELECT file_path FROM file_metadata
                WHERE repo_id = $repo_id AND language = $language
                LIMIT 5
                """
                target_files = await query(files_query, {'repo_id':
                    target_repo_id, 'language': pattern['language']})
                for file in target_files:
                    recommendation = {'pattern_id': pattern['pattern_id'],
                        'pattern_type': pattern['pattern_type'], 'language':
                        pattern['language'], 'target_file': file[
                        'file_path'], 'recommendation':
                        f'Apply cross-repository best practice pattern',
                        'confidence': pattern['confidence'],
                        'example_files': pattern['example_files'][:3] if
                        pattern.get('example_files') else [],
                        'is_cross_repository': True}
                    recommendations.append(recommendation)
        return {'target_repo_id': target_repo_id, 'reference_repos':
            repo_ids, 'recommendations_count': len(recommendations),
            'recommendations': recommendations, 'status': 'success'}

    @handle_async_errors(error_types=(ProcessingError, DatabaseError))
    async def update_patterns_for_file(self, repo_id: int, file_path: str
        ) ->Dict[str, Any]:
        """[4.4.9] Update patterns for a specific file in a repository.
        
        This method extracts patterns from a single file and updates them in the database,
        useful for incremental updates without reprocessing the entire repository.
        
        Args:
            repo_id: Repository ID
            file_path: Path to the file to update
            
        Returns:
            Dict with update results
        """
        from utils.error_handling import AsyncErrorBoundary, ErrorBoundary
        from parsers.pattern_processor import pattern_processor

        def create_embedding(pattern_text):
            with AsyncErrorBoundary(operation_name='pattern_embedding'):
                embedding = self.embedder.embed(pattern_text)
                return embedding.tolist() if hasattr(embedding, 'tolist'
                    ) else None
            return None
        async with AsyncErrorBoundary(operation_name='update_file_patterns',
            error_types=(Exception,)):
            file_query = """
                SELECT file_content, language 
                FROM file_metadata 
                WHERE repo_id = $repo_id AND file_path = $file_path
            """
            file_result = await query(file_query, {'repo_id': repo_id,
                'file_path': file_path})
            if not file_result:
                return {'status': 'error', 'message':
                    f'File not found: {file_path}'}
            file_content = file_result[0]['file_content']
            language = file_result[0]['language']
            delete_query = """
                DELETE FROM code_patterns
                WHERE repo_id = $repo_id AND file_path = $file_path
            """
            await query(delete_query, {'repo_id': repo_id, 'file_path':
                file_path})
            patterns = pattern_processor.extract_repository_patterns(file_path,
                file_content, language)
            new_patterns = []
            for pattern in patterns:
                pattern_text = pattern.get('content', '')
                if pattern_text:
                    embedding_list = create_embedding(pattern_text)
                    pattern_query = """
                        INSERT INTO code_patterns (
                            repo_id, file_path, pattern_type, content, 
                            language, confidence, example_usage, embedding
                        ) VALUES (
                            $repo_id, $file_path, $pattern_type, $content,
                            $language, $confidence, $example_usage, $embedding
                        )
                        RETURNING id
                    """
                    pattern_id = await query(pattern_query, {'repo_id':
                        repo_id, 'file_path': file_path, 'pattern_type':
                        pattern.get('pattern_type', 'code_structure'),
                        'content': pattern_text, 'language': language,
                        'confidence': pattern.get('confidence', 0.7),
                        'example_usage': pattern.get('content', ''),
                        'embedding': embedding_list})
                    if pattern_id:
                        await self.neo4j_tools.store_pattern_node({
                            'pattern_id': pattern_id[0]['id'], 'repo_id':
                            repo_id, 'file_path': file_path, 'pattern_type':
                            pattern.get('pattern_type', 'code_structure'),
                            'language': language, 'confidence': pattern.get
                            ('confidence', 0.7)})
                        new_patterns.append(pattern_id[0]['id'])
            if new_patterns:
                await graph_sync.invalidate_pattern_projection(repo_id)
                await graph_sync.ensure_pattern_projection(repo_id)
            return {'status': 'success', 'file_path': file_path,
                'patterns_updated': len(new_patterns), 'pattern_ids':
                new_patterns}
        return {'status': 'error', 'message':
            'Failed to update patterns for file'}


reference_learning = ReferenceRepositoryLearning()
