"""Statistical Pattern Analysis module.

This module provides tools for collecting and analyzing statistics about pattern usage
across different repositories, helping to identify the most valuable patterns and 
optimize performance.
"""
from typing import Dict, List, Any, Set, Optional, Tuple, Counter as CounterType
from collections import Counter, defaultdict
import time
import json
import statistics
import math
from dataclasses import dataclass, field, asdict
import asyncio
import os
from enum import Enum
import matplotlib.pyplot as plt
import numpy as np
from datetime import datetime, timedelta
from parsers.models import PatternType
from utils.logger import log
from utils.error_handling import ErrorBoundary, handle_errors, AsyncErrorBoundary
from utils.cache import pattern_cache


class PatternStatisticsType(Enum):
    """Types of pattern statistics that can be collected."""
    USAGE_FREQUENCY = 'usage_frequency'
    EXECUTION_TIME = 'execution_time'
    HIT_RATIO = 'hit_ratio'
    COMPILATION_TIME = 'compilation_time'
    MEMORY_USAGE = 'memory_usage'
    VALUE_SCORE = 'value_score'


@dataclass
class PatternMetrics:
    """Metrics for a specific pattern."""
    pattern_id: str
    pattern_type: PatternType
    language: str
    executions: int = 0
    matches: int = 0
    total_execution_time_ms: float = 0
    total_compilation_time_ms: float = 0
    estimated_memory_bytes: int = 0
    hit_ratio: float = 0
    avg_execution_time_ms: float = 0
    value_score: float = 0
    execution_times: List[float] = field(default_factory=list)
    match_counts: List[int] = field(default_factory=list)
    timestamps: List[float] = field(default_factory=list)

    def update(self, execution_time_ms: float=0, compilation_time_ms: float
        =0, matches_found: int=0, memory_bytes: int=0):
        """Update metrics with new execution data."""
        self.executions += 1
        self.matches += matches_found
        self.total_execution_time_ms += execution_time_ms
        self.total_compilation_time_ms += compilation_time_ms
        self.estimated_memory_bytes = max(self.estimated_memory_bytes,
            memory_bytes)
        self.execution_times.append(execution_time_ms)
        self.match_counts.append(matches_found)
        self.timestamps.append(time.time())
        if len(self.execution_times) > 100:
            self.execution_times = self.execution_times[-100:]
            self.match_counts = self.match_counts[-100:]
            self.timestamps = self.timestamps[-100:]
        self._calculate_derived_metrics()

    def _calculate_derived_metrics(self):
        """Calculate derived metrics from raw metrics."""
        self.hit_ratio = self.matches / max(1, self.executions)
        self.avg_execution_time_ms = self.total_execution_time_ms / max(1,
            self.executions)
        self.value_score = self.hit_ratio * 100 / (self.
            avg_execution_time_ms + 1)

    def to_dict(self) ->Dict[str, Any]:
        """Convert metrics to a dictionary."""
        return asdict(self)


class PatternStatisticsManager:
    """
    Manages the collection and analysis of pattern statistics.
    
    This class provides methods to:
    - Track pattern execution metrics
    - Analyze pattern value
    - Generate recommendations for optimization
    - Export statistics for visualization
    """

    def __init__(self):
        """Initialize the statistics manager."""
        self.metrics: Dict[str, PatternMetrics] = {}
        self.last_analysis_time = None
        self.analysis_results = {}

    async def load_from_cache(self):
        """
        Load pattern metrics from cache.
        
        This should be called after initialization to load cached metrics.
        """
        await self._load_metrics_from_cache()

    async def save_to_cache(self):
        """
        Save pattern metrics to cache explicitly.
        """
        await self._save_metrics_to_cache()

    def track_pattern_execution(self, pattern_id: str, pattern_type:
        PatternType, language: str, execution_time_ms: float,
        compilation_time_ms: float=0, matches_found: int=0, memory_bytes: int=0
        ):
        """
        Track the execution of a pattern.
        
        Args:
            pattern_id: Unique identifier for the pattern
            pattern_type: Type of the pattern
            language: Language the pattern is for
            execution_time_ms: Time taken to execute the pattern in milliseconds
            compilation_time_ms: Time taken to compile the pattern in milliseconds
            matches_found: Number of matches found by the pattern
            memory_bytes: Estimated memory usage of the pattern in bytes
        """
        key = f'{language}:{pattern_type.value}:{pattern_id}'
        if key not in self.metrics:
            self.metrics[key] = PatternMetrics(pattern_id=pattern_id,
                pattern_type=pattern_type, language=language)
        self.metrics[key].update(execution_time_ms=execution_time_ms,
            compilation_time_ms=compilation_time_ms, matches_found=
            matches_found, memory_bytes=memory_bytes)
        if len(self.metrics) % 10 == 0:
            log.debug(
                f'Metrics collection at {len(self.metrics)} entries - recommend calling save_to_cache()'
                )

    def analyze_patterns(self) ->Dict[str, Any]:
        """
        Analyze pattern statistics and generate insights.
        
        Returns:
            Dictionary with analysis results
        """
        if not self.metrics:
            return {'status': 'no_data', 'message':
                'No pattern statistics available for analysis'}
        self.last_analysis_time = time.time()
        results = {'timestamp': self.last_analysis_time, 'total_patterns':
            len(self.metrics), 'by_language': {}, 'by_pattern_type': {},
            'most_valuable_patterns': [], 'performance_bottlenecks': [],
            'recommendations': []}
        language_metrics = defaultdict(list)
        for key, metrics in self.metrics.items():
            language_metrics[metrics.language].append(metrics)
        for language, metrics_list in language_metrics.items():
            results['by_language'][language] = {'pattern_count': len(
                metrics_list), 'avg_hit_ratio': statistics.mean([m.
                hit_ratio for m in metrics_list]), 'avg_execution_time':
                statistics.mean([m.avg_execution_time_ms for m in
                metrics_list]), 'total_matches': sum([m.matches for m in
                metrics_list]), 'total_executions': sum([m.executions for m in
                metrics_list])}
        type_metrics = defaultdict(list)
        for key, metrics in self.metrics.items():
            type_metrics[metrics.pattern_type.value].append(metrics)
        for pattern_type, metrics_list in type_metrics.items():
            results['by_pattern_type'][pattern_type] = {'pattern_count':
                len(metrics_list), 'avg_hit_ratio': statistics.mean([m.
                hit_ratio for m in metrics_list]), 'avg_execution_time':
                statistics.mean([m.avg_execution_time_ms for m in
                metrics_list]), 'total_matches': sum([m.matches for m in
                metrics_list]), 'total_executions': sum([m.executions for m in
                metrics_list])}
        sorted_by_value = sorted(self.metrics.values(), key=lambda m: m.
            value_score, reverse=True)
        results['most_valuable_patterns'] = [{'pattern_id': m.pattern_id,
            'language': m.language, 'type': m.pattern_type.value,
            'value_score': m.value_score, 'hit_ratio': m.hit_ratio,
            'avg_execution_time': m.avg_execution_time_ms} for m in
            sorted_by_value[:10]]
        min_executions = 5
        if len(self.metrics) > 0 and not any(m for m in self.metrics.values
            () if m.executions > min_executions):
            min_executions = 0
        sorted_by_bottleneck = sorted([m for m in self.metrics.values() if 
            m.executions > min_executions], key=lambda m: (m.value_score, -
            m.avg_execution_time_ms))
        results['performance_bottlenecks'] = [{'pattern_id': m.pattern_id,
            'language': m.language, 'type': m.pattern_type.value,
            'value_score': m.value_score, 'avg_execution_time': m.
            avg_execution_time_ms, 'executions': m.executions, 'matches': m
            .matches} for m in sorted_by_bottleneck[:10]]
        recommendations = []
        for pattern in results['most_valuable_patterns'][:5]:
            recommendations.append({'type': 'prioritize_caching',
                'pattern_id': pattern['pattern_id'], 'language': pattern[
                'language'], 'reason':
                f"High value pattern (score: {pattern['value_score']:.2f}) with good hit ratio ({pattern['hit_ratio']:.2f})"
                })
        for pattern in results['performance_bottlenecks'][:5]:
            if pattern['matches'] == 0 and pattern['executions'] > 10:
                recommendations.append({'type': 'consider_removing',
                    'pattern_id': pattern['pattern_id'], 'language':
                    pattern['language'], 'reason':
                    f"Pattern never matches despite {pattern['executions']} executions"
                    })
            elif pattern['value_score'] < 0.1:
                recommendations.append({'type': 'optimize_or_deprioritize',
                    'pattern_id': pattern['pattern_id'], 'language':
                    pattern['language'], 'reason':
                    f"Low value score ({pattern['value_score']:.2f}) with high execution time ({pattern['avg_execution_time']:.2f}ms)"
                    })
        language_hit_ratios = [(lang, data['avg_hit_ratio']) for lang, data in
            results['by_language'].items()]
        language_hit_ratios.sort(key=lambda x: x[1], reverse=True)
        if language_hit_ratios:
            top_language = language_hit_ratios[0]
            recommendations.append({'type': 'focus_language', 'language':
                top_language[0], 'reason':
                f'Highest average hit ratio ({top_language[1]:.2f}) across patterns'
                })
        results['recommendations'] = recommendations
        self.analysis_results = results
        return results

    def get_pattern_value_ranking(self) ->List[Dict[str, Any]]:
        """
        Get a ranking of patterns by their value score.
        
        Returns:
            List of dictionaries with pattern details and value scores
        """
        if not self.metrics:
            return []
        sorted_patterns = sorted(self.metrics.values(), key=lambda m: m.
            value_score, reverse=True)
        return [{'pattern_id': m.pattern_id, 'language': m.language, 'type':
            m.pattern_type.value, 'value_score': m.value_score, 'hit_ratio':
            m.hit_ratio, 'avg_execution_time': m.avg_execution_time_ms,
            'executions': m.executions, 'matches': m.matches} for m in
            sorted_patterns]

    def get_pattern_metrics(self, pattern_id: str, language: str,
        pattern_type: PatternType) ->Optional[Dict[str, Any]]:
        """
        Get metrics for a specific pattern.
        
        Args:
            pattern_id: Pattern identifier
            language: Language of the pattern
            pattern_type: Type of the pattern
            
        Returns:
            Dictionary with pattern metrics or None if not found
        """
        key = f'{language}:{pattern_type.value}:{pattern_id}'
        if key in self.metrics:
            metrics_dict = self.metrics[key].to_dict()
            metrics_dict['pattern_type'] = metrics_dict['pattern_type'].value
            return metrics_dict
        return None

    def get_language_statistics(self) ->Dict[str, Dict[str, Any]]:
        """
        Get statistics organized by language.
        
        Returns:
            Dictionary with language statistics
        """
        if not self.metrics:
            return {}
        language_stats = defaultdict(lambda : {'pattern_count': 0,
            'total_executions': 0, 'total_matches': 0,
            'total_execution_time_ms': 0, 'patterns_by_type': defaultdict(
            int), 'avg_hit_ratio': 0, 'avg_execution_time_ms': 0})
        for key, metrics in self.metrics.items():
            lang = metrics.language
            language_stats[lang]['pattern_count'] += 1
            language_stats[lang]['total_executions'] += metrics.executions
            language_stats[lang]['total_matches'] += metrics.matches
            language_stats[lang]['total_execution_time_ms'
                ] += metrics.total_execution_time_ms
            language_stats[lang]['patterns_by_type'][metrics.pattern_type.value
                ] += 1
        for lang, stats in language_stats.items():
            if stats['total_executions'] > 0:
                stats['avg_hit_ratio'] = stats['total_matches'] / stats[
                    'total_executions']
                stats['avg_execution_time_ms'] = stats[
                    'total_execution_time_ms'] / stats['total_executions']
            stats['patterns_by_type'] = dict(stats['patterns_by_type'])
        return dict(language_stats)

    def generate_visualization(self, output_path: str='pattern_analysis.png'
        ) ->str:
        """
        Generate a visualization of pattern statistics.
        
        Args:
            output_path: Path to save the visualization
            
        Returns:
            Path to the generated visualization file
        """
        if not self.metrics:
            log('No pattern statistics available for visualization', level=
                'warning')
            return ''
        try:
            fig, axs = plt.subplots(2, 2, figsize=(15, 12))
            fig.suptitle('Pattern Statistics Analysis', fontsize=16)
            pattern_types = defaultdict(list)
            for metrics in self.metrics.values():
                pattern_types[metrics.pattern_type.value].append(metrics.
                    value_score)
            x = list(pattern_types.keys())
            y = [statistics.mean(scores) for scores in pattern_types.values()]
            axs[0, 0].bar(x, y)
            axs[0, 0].set_title('Average Value Score by Pattern Type')
            axs[0, 0].set_xlabel('Pattern Type')
            axs[0, 0].set_ylabel('Average Value Score')
            axs[0, 0].tick_params(axis='x', rotation=45)
            x = [m.avg_execution_time_ms for m in self.metrics.values()]
            y = [m.hit_ratio for m in self.metrics.values()]
            colors = [m.value_score for m in self.metrics.values()]
            scatter = axs[0, 1].scatter(x, y, c=colors, cmap='viridis',
                alpha=0.6)
            axs[0, 1].set_title('Hit Ratio vs Execution Time')
            axs[0, 1].set_xlabel('Avg Execution Time (ms)')
            axs[0, 1].set_ylabel('Hit Ratio')
            fig.colorbar(scatter, ax=axs[0, 1], label='Value Score')
            language_stats = self.get_language_statistics()
            x = list(language_stats.keys())
            y = [stats['avg_hit_ratio'] for stats in language_stats.values()]
            axs[1, 0].bar(x, y)
            axs[1, 0].set_title('Average Hit Ratio by Language')
            axs[1, 0].set_xlabel('Language')
            axs[1, 0].set_ylabel('Average Hit Ratio')
            axs[1, 0].tick_params(axis='x', rotation=45)
            languages = []
            pattern_type_counts = defaultdict(list)
            for lang, stats in language_stats.items():
                languages.append(lang)
                for pattern_type, count in stats['patterns_by_type'].items():
                    pattern_type_counts[pattern_type].append(count)
            bottom = np.zeros(len(languages))
            for pattern_type, counts in pattern_type_counts.items():
                axs[1, 1].bar(languages, counts, bottom=bottom, label=
                    pattern_type)
                bottom += np.array(counts)
            axs[1, 1].set_title('Pattern Count by Language and Type')
            axs[1, 1].set_xlabel('Language')
            axs[1, 1].set_ylabel('Pattern Count')
            axs[1, 1].legend()
            axs[1, 1].tick_params(axis='x', rotation=45)
            plt.tight_layout(rect=[0, 0, 1, 0.95])
            plt.savefig(output_path)
            return output_path
        except Exception as e:
            log(f'Error generating visualization: {str(e)}', level='error')
            return ''

    def export_statistics(self, output_path: str='pattern_statistics.json'
        ) ->str:
        """
        Export pattern statistics to a JSON file.
        
        Args:
            output_path: Path to save the exported statistics
            
        Returns:
            Path to the exported file
        """
        if not self.metrics:
            log('No pattern statistics available for export', level='warning')
            return ''
        try:
            export_data = {'timestamp': time.time(), 'pattern_count': len(
                self.metrics), 'metrics': {k: m.to_dict() for k, m in self.
                metrics.items()}, 'language_stats': self.
                get_language_statistics(), 'analysis': self.
                analysis_results if self.analysis_results else self.
                analyze_patterns()}
            with open(output_path, 'w') as f:
                json.dump(export_data, f, indent=2)
            return output_path
        except Exception as e:
            log(f'Error exporting statistics: {str(e)}', level='error')
            return ''

    def get_recommendations(self) ->List[Dict[str, Any]]:
        """
        Get pattern optimization recommendations.
        
        Returns:
            List of recommendation dictionaries
        """
        if not self.analysis_results or self.last_analysis_time and time.time(
            ) - self.last_analysis_time > 3600:
            self.analyze_patterns()
        return self.analysis_results.get('recommendations', [])

    def generate_cache_warming_recommendations(self) ->List[Dict[str, Any]]:
        """
        Generate recommendations for cache warming based on pattern statistics.
        
        Returns:
            List of patterns recommended for cache warming
        """
        recommendations = []
        if not self.metrics:
            return recommendations
        sorted_patterns = sorted(self.metrics.values(), key=lambda m: (m.
            value_score, m.hit_ratio), reverse=True)
        for metrics in sorted_patterns[:20]:
            if metrics.value_score > 0.5 and metrics.hit_ratio > 0.1:
                recommendations.append({'pattern_id': metrics.pattern_id,
                    'language': metrics.language, 'type': metrics.
                    pattern_type.value, 'priority': 'high' if metrics.
                    value_score > 5 else 'medium', 'reason':
                    f'High value pattern (score: {metrics.value_score:.2f}) with good hit ratio ({metrics.hit_ratio:.2f})'
                    })
        return recommendations

    async def _load_metrics_from_cache(self):
        """Load metrics from cache."""
        with AsyncErrorBoundary(operation_name=
            'Failed to load pattern statistics from cache'):
            cached_metrics = await pattern_cache.get_async(
                'pattern_statistics:metrics')
            if cached_metrics:
                self.metrics = cached_metrics
                log.info(
                    f'Loaded {len(self.metrics)} pattern metrics from cache')

    async def _save_metrics_to_cache(self):
        """Save metrics to cache."""
        with AsyncErrorBoundary(operation_name=
            'Failed to save pattern statistics to cache'):
            await pattern_cache.set_async('pattern_statistics:metrics',
                self.metrics)
            log.info(f'Saved {len(self.metrics)} pattern metrics to cache')


pattern_statistics = PatternStatisticsManager()
