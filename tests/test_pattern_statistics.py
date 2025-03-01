#!/usr/bin/env python3
"""
Unit tests for the pattern statistics system.
"""

import sys
import os
import unittest
from unittest.mock import patch, MagicMock
import time
import json
from pathlib import Path
import asyncio

# Add the parent directory to the Python path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analytics.pattern_statistics import PatternStatisticsManager, PatternMetrics
from parsers.models import PatternType

def async_mock():
    """Create a mock for an async function that returns a coroutine."""
    mock = MagicMock()
    mock.__await__ = lambda self: (yield from asyncio.sleep(0).__await__())
    return mock

class TestPatternStatistics(unittest.TestCase):
    """Test the Pattern Statistics system."""

    def setUp(self):
        """Set up test fixtures."""
        # Create a test instance of PatternStatisticsManager
        self.manager = PatternStatisticsManager()
        
        # Mock the cache methods to avoid actual cache operations during tests
        self.manager._load_metrics_from_cache = async_mock()
        self.manager._save_metrics_to_cache = async_mock()
        self.manager.load_from_cache = async_mock()
        self.manager.save_to_cache = async_mock()
        
        # Add some test data
        self.manager.track_pattern_execution(
            pattern_id="test_pattern_1",
            pattern_type=PatternType.CODE_STRUCTURE,
            language="python",
            execution_time_ms=10.0,
            compilation_time_ms=5.0,
            matches_found=5,
            memory_bytes=1000
        )
        
        self.manager.track_pattern_execution(
            pattern_id="test_pattern_2",
            pattern_type=PatternType.CODE_NAMING,
            language="python",
            execution_time_ms=20.0,
            compilation_time_ms=8.0,
            matches_found=0,
            memory_bytes=2000
        )
        
        self.manager.track_pattern_execution(
            pattern_id="test_pattern_3",
            pattern_type=PatternType.ERROR_HANDLING,
            language="javascript",
            execution_time_ms=15.0,
            compilation_time_ms=6.0,
            matches_found=3,
            memory_bytes=1500
        )
        
        # Add multiple executions for one pattern to test aggregation
        for i in range(5):
            self.manager.track_pattern_execution(
                pattern_id="test_pattern_4",
                pattern_type=PatternType.CODE_STRUCTURE,
                language="python",
                execution_time_ms=5.0 * (i + 1),  # Increasing execution times
                compilation_time_ms=2.0,
                matches_found=i,  # Varying match counts
                memory_bytes=800
            )

    def test_track_pattern_execution(self):
        """Test tracking pattern execution metrics."""
        # Test that patterns were added correctly
        self.assertEqual(len(self.manager.metrics), 4)
        
        # Test that a specific pattern was tracked correctly
        key = "python:code_structure:test_pattern_1"
        self.assertIn(key, self.manager.metrics)
        metrics = self.manager.metrics[key]
        
        self.assertEqual(metrics.pattern_id, "test_pattern_1")
        self.assertEqual(metrics.pattern_type, PatternType.CODE_STRUCTURE)
        self.assertEqual(metrics.language, "python")
        self.assertEqual(metrics.executions, 1)
        self.assertEqual(metrics.matches, 5)
        self.assertEqual(metrics.total_execution_time_ms, 10.0)
        self.assertEqual(metrics.total_compilation_time_ms, 5.0)
        self.assertEqual(metrics.estimated_memory_bytes, 1000)
        
        # Test derived metrics
        self.assertEqual(metrics.hit_ratio, 5.0)  # 5 matches / 1 execution
        self.assertEqual(metrics.avg_execution_time_ms, 10.0)
        self.assertGreater(metrics.value_score, 0)
        
    def test_multiple_executions(self):
        """Test tracking and aggregating multiple executions of the same pattern."""
        key = "python:code_structure:test_pattern_4"
        self.assertIn(key, self.manager.metrics)
        metrics = self.manager.metrics[key]
        
        # Should have 5 executions
        self.assertEqual(metrics.executions, 5)
        
        # Sum of 0,1,2,3,4 = 10 matches
        self.assertEqual(metrics.matches, 10)
        
        # Sum of 5.0, 10.0, 15.0, 20.0, 25.0 = 75.0
        self.assertEqual(metrics.total_execution_time_ms, 75.0)
        
        # 5 executions * 2.0 = 10.0
        self.assertEqual(metrics.total_compilation_time_ms, 10.0)
        
        # Average execution time: 75.0 / 5 = 15.0
        self.assertEqual(metrics.avg_execution_time_ms, 15.0)
        
        # Hit ratio: 10 / 5 = 2.0
        self.assertEqual(metrics.hit_ratio, 2.0)
        
        # Should have execution history
        self.assertEqual(len(metrics.execution_times), 5)
        self.assertEqual(len(metrics.match_counts), 5)
        self.assertEqual(len(metrics.timestamps), 5)

    def test_analyze_patterns(self):
        """Test pattern analysis functionality."""
        analysis = self.manager.analyze_patterns()
        
        # Check basic structure of analysis
        self.assertIn("total_patterns", analysis)
        self.assertEqual(analysis["total_patterns"], 4)
        
        self.assertIn("by_language", analysis)
        self.assertIn("python", analysis["by_language"])
        self.assertIn("javascript", analysis["by_language"])
        
        self.assertIn("by_pattern_type", analysis)
        self.assertIn("code_structure", analysis["by_pattern_type"])
        self.assertIn("code_naming", analysis["by_pattern_type"])
        self.assertIn("error_handling", analysis["by_pattern_type"])
        
        self.assertIn("most_valuable_patterns", analysis)
        self.assertGreater(len(analysis["most_valuable_patterns"]), 0)
        
        self.assertIn("performance_bottlenecks", analysis)
        self.assertGreater(len(analysis["performance_bottlenecks"]), 0)
        
        self.assertIn("recommendations", analysis)
        self.assertGreater(len(analysis["recommendations"]), 0)

    def test_get_pattern_value_ranking(self):
        """Test retrieving pattern value rankings."""
        rankings = self.manager.get_pattern_value_ranking()
        
        # Should have 4 patterns
        self.assertEqual(len(rankings), 4)
        
        # Should be sorted by value score (descending)
        for i in range(1, len(rankings)):
            self.assertGreaterEqual(
                rankings[i-1]["value_score"],
                rankings[i]["value_score"]
            )

    def test_get_pattern_metrics(self):
        """Test retrieving metrics for a specific pattern."""
        # Get metrics for a pattern that exists
        metrics = self.manager.get_pattern_metrics(
            pattern_id="test_pattern_1",
            language="python",
            pattern_type=PatternType.CODE_STRUCTURE
        )
        
        self.assertIsNotNone(metrics)
        self.assertEqual(metrics["pattern_id"], "test_pattern_1")
        self.assertEqual(metrics["pattern_type"], "code_structure")
        self.assertEqual(metrics["language"], "python")
        
        # Get metrics for a pattern that doesn't exist
        metrics = self.manager.get_pattern_metrics(
            pattern_id="nonexistent_pattern",
            language="python",
            pattern_type=PatternType.CODE_STRUCTURE
        )
        
        self.assertIsNone(metrics)

    def test_get_language_statistics(self):
        """Test retrieving statistics grouped by language."""
        language_stats = self.manager.get_language_statistics()
        
        # Should have stats for python and javascript
        self.assertIn("python", language_stats)
        self.assertIn("javascript", language_stats)
        
        # Check python stats
        python_stats = language_stats["python"]
        self.assertEqual(python_stats["pattern_count"], 3)  # 3 python patterns
        self.assertEqual(python_stats["total_executions"], 7)  # 1 + 1 + 5 executions
        self.assertEqual(python_stats["total_matches"], 15)  # 5 + 0 + 10 matches
        
        # Check javascript stats
        js_stats = language_stats["javascript"]
        self.assertEqual(js_stats["pattern_count"], 1)  # 1 javascript pattern
        self.assertEqual(js_stats["total_executions"], 1)  # 1 execution
        self.assertEqual(js_stats["total_matches"], 3)  # 3 matches

    def test_get_recommendations(self):
        """Test generating optimization recommendations."""
        recommendations = self.manager.get_recommendations()
        
        # Should have some recommendations
        self.assertGreater(len(recommendations), 0)
        
        # Each recommendation should have a type and reason
        for rec in recommendations:
            self.assertIn("type", rec)
            self.assertIn("reason", rec)

    def test_generate_cache_warming_recommendations(self):
        """Test generating cache warming recommendations."""
        recommendations = self.manager.generate_cache_warming_recommendations()
        
        # Should have some recommendations (for patterns with good value scores)
        self.assertGreater(len(recommendations), 0)
        
        # Each recommendation should have pattern_id, language, type, priority, and reason
        for rec in recommendations:
            self.assertIn("pattern_id", rec)
            self.assertIn("language", rec)
            self.assertIn("type", rec)
            self.assertIn("priority", rec)
            self.assertIn("reason", rec)

    @patch('matplotlib.pyplot.savefig')
    def test_generate_visualization(self, mock_savefig):
        """Test generating visualizations."""
        # Mock plt.savefig to avoid actually creating a file
        mock_savefig.return_value = None
        
        output_path = self.manager.generate_visualization("test_visualization.png")
        
        # Should return the output path if successful
        self.assertEqual(output_path, "test_visualization.png")
        
        # Should have called savefig
        mock_savefig.assert_called_once()

    @patch('builtins.open', new_callable=unittest.mock.mock_open)
    @patch('json.dump')
    def test_export_statistics(self, mock_json_dump, mock_open):
        """Test exporting statistics to a file."""
        output_path = self.manager.export_statistics("test_export.json")
        
        # Should return the output path if successful
        self.assertEqual(output_path, "test_export.json")
        
        # Should have opened the file
        mock_open.assert_called_once_with("test_export.json", 'w')
        
        # Should have called json.dump
        mock_json_dump.assert_called_once()
        
        # Check that what we're exporting contains the right keys
        export_data = mock_json_dump.call_args[0][0]
        self.assertIn("timestamp", export_data)
        self.assertIn("pattern_count", export_data)
        self.assertIn("metrics", export_data)
        self.assertIn("language_stats", export_data)
        self.assertIn("analysis", export_data)

if __name__ == "__main__":
    unittest.main() 