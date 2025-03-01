#!/usr/bin/env python3
"""
Exception Handling Pattern Analyzer for RepoAnalyzer

This script analyzes the codebase to identify exception handling patterns
that don't follow the best practices outlined in the Exception Handling Guide.
It generates a report of files and functions that need attention.
"""

import os
import sys
import re
import ast
import json
import argparse
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any, Optional
from dataclasses import dataclass, field

# Add the parent directory to sys.path to import from utils
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from utils.error_handling import handle_errors, ErrorBoundary, ProcessingError


@dataclass
class ExceptionIssue:
    """Represents an issue with exception handling in code."""
    file_path: str
    line_number: int
    issue_type: str
    description: str
    severity: str  # 'high', 'medium', 'low'
    suggested_fix: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "file_path": self.file_path,
            "line_number": self.line_number,
            "issue_type": self.issue_type,
            "description": self.description,
            "severity": self.severity,
            "suggested_fix": self.suggested_fix
        }


@dataclass
class AnalysisResult:
    """Contains the result of analyzing exception handling patterns."""
    issues: List[ExceptionIssue] = field(default_factory=list)
    files_analyzed: int = 0
    issue_count_by_type: Dict[str, int] = field(default_factory=dict)
    issue_count_by_severity: Dict[str, int] = field(default_factory=dict)
    
    def add_issue(self, issue: ExceptionIssue) -> None:
        """Add an issue to the results and update counts."""
        self.issues.append(issue)
        
        # Update type count
        self.issue_count_by_type[issue.issue_type] = self.issue_count_by_type.get(issue.issue_type, 0) + 1
        
        # Update severity count
        self.issue_count_by_severity[issue.severity] = self.issue_count_by_severity.get(issue.severity, 0) + 1
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "issues": [issue.to_dict() for issue in self.issues],
            "files_analyzed": self.files_analyzed,
            "issue_count_by_type": self.issue_count_by_type,
            "issue_count_by_severity": self.issue_count_by_severity,
            "total_issues": len(self.issues)
        }


class ExceptionPatternVisitor(ast.NodeVisitor):
    """AST visitor to find exception handling patterns."""
    
    def __init__(self, file_path: str, result: AnalysisResult):
        self.file_path = file_path
        self.result = result
        self.function_stack = []
        self.error_boundaries = set()
        self.decorated_functions = set()
        
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definitions."""
        self.function_stack.append(node.name)
        
        # Check if function has error handling decorator
        has_error_handling = False
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name in ('handle_errors', 'handle_async_errors', 'with_retry'):
                has_error_handling = True
                self.decorated_functions.add(node.name)
                break
        
        # Check if function contains try/except but no decorator
        if not has_error_handling:
            try_except_count = sum(1 for n in ast.walk(node) if isinstance(n, ast.Try))
            if try_except_count > 0:
                self.result.add_issue(ExceptionIssue(
                    file_path=self.file_path,
                    line_number=node.lineno,
                    issue_type="missing_decorator",
                    description=f"Function '{node.name}' contains try/except but no error handling decorator",
                    severity="medium",
                    suggested_fix=f"Consider adding @handle_errors or @handle_async_errors decorator to function '{node.name}'"
                ))
        
        self.generic_visit(node)
        self.function_stack.pop()
    
    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definitions."""
        self.function_stack.append(node.name)
        
        # Check if async function has error handling decorator
        has_error_handling = False
        for decorator in node.decorator_list:
            decorator_name = self._get_decorator_name(decorator)
            if decorator_name in ('handle_async_errors', 'with_retry'):
                has_error_handling = True
                self.decorated_functions.add(node.name)
                break
        
        # Check if async function should have handle_async_errors
        if not has_error_handling and self._contains_await_in_try(node):
            self.result.add_issue(ExceptionIssue(
                file_path=self.file_path,
                line_number=node.lineno,
                issue_type="missing_async_decorator",
                description=f"Async function '{node.name}' has try/except with await but no handle_async_errors decorator",
                severity="high",
                suggested_fix=f"Add @handle_async_errors decorator to async function '{node.name}'"
            ))
        
        self.generic_visit(node)
        self.function_stack.pop()
    
    def visit_Try(self, node: ast.Try) -> None:
        """Visit try/except blocks."""
        # Check for bare except
        for handler in node.handlers:
            if handler.type is None:
                self.result.add_issue(ExceptionIssue(
                    file_path=self.file_path,
                    line_number=handler.lineno,
                    issue_type="bare_except",
                    description="Bare except clause used without specifying exception types",
                    severity="high",
                    suggested_fix="Specify exception types to catch, avoid catching all exceptions"
                ))
            # Check for too broad exception handling (Exception)
            elif isinstance(handler.type, ast.Name) and handler.type.id == 'Exception':
                # Check if this is inside an ErrorBoundary
                if not self._is_in_error_boundary(node):
                    self.result.add_issue(ExceptionIssue(
                        file_path=self.file_path,
                        line_number=handler.lineno,
                        issue_type="broad_except",
                        description="Catching Exception is too broad",
                        severity="medium",
                        suggested_fix="Use more specific exception types or ErrorBoundary context manager"
                    ))
        
        # Check if the try block contains no exception handling (just finally)
        if not node.handlers and not node.orelse and node.finalbody:
            # This is fine, it's a try/finally block
            pass
        
        # Check for pass in except block
        for handler in node.handlers:
            if len(handler.body) == 1 and isinstance(handler.body[0], ast.Pass):
                self.result.add_issue(ExceptionIssue(
                    file_path=self.file_path,
                    line_number=handler.lineno,
                    issue_type="silent_except",
                    description="Exception silently ignored with pass",
                    severity="high",
                    suggested_fix="Add proper error handling or logging instead of pass"
                ))
                
        self.generic_visit(node)
    
    def visit_With(self, node: ast.With) -> None:
        """Visit with statements to track ErrorBoundary usage."""
        for item in node.items:
            if isinstance(item.context_expr, ast.Call) and hasattr(item.context_expr, 'func'):
                if isinstance(item.context_expr.func, ast.Name):
                    if item.context_expr.func.id in ('ErrorBoundary', 'AsyncErrorBoundary'):
                        self.error_boundaries.add(node)
        
        self.generic_visit(node)
    
    def visit_Raise(self, node: ast.Raise) -> None:
        """Visit raise statements."""
        # Check if raising generic exceptions
        if node.exc and isinstance(node.exc, ast.Call) and isinstance(node.exc.func, ast.Name):
            exception_name = node.exc.func.id
            if exception_name == 'Exception':
                self.result.add_issue(ExceptionIssue(
                    file_path=self.file_path,
                    line_number=node.lineno,
                    issue_type="generic_raise",
                    description="Raising generic Exception",
                    severity="medium",
                    suggested_fix="Use a more specific exception type from error_handling module"
                ))
        
        self.generic_visit(node)
    
    def _get_decorator_name(self, node: ast.expr) -> str:
        """Extract the decorator name from a decorator node."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node, ast.Attribute):
            return node.attr
        return ""
    
    def _contains_await_in_try(self, node: ast.AsyncFunctionDef) -> bool:
        """Check if an async function contains await inside try blocks."""
        for n in ast.walk(node):
            if isinstance(n, ast.Try):
                for sub_node in ast.walk(n):
                    if isinstance(sub_node, ast.Await):
                        return True
        return False
    
    def _is_in_error_boundary(self, node: ast.Try) -> bool:
        """Check if a try block is inside an ErrorBoundary context manager."""
        for boundary in self.error_boundaries:
            # Check if the try node is within the body of any error boundary
            for body_node in boundary.body:
                if node in ast.walk(body_node):
                    return True
        return False


@handle_errors(error_types=(ProcessingError,))
def find_python_files(directory: str, exclude_dirs: List[str] = None) -> List[str]:
    """Find all Python files in the given directory."""
    if exclude_dirs is None:
        exclude_dirs = ['.git', '.venv', 'venv', 'env', '__pycache__', 'tests']
    
    python_files = []
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    
    return python_files


@handle_errors(error_types=(ProcessingError,))
def analyze_file(file_path: str, result: AnalysisResult) -> None:
    """Analyze a single Python file for exception handling patterns."""
    with ErrorBoundary(f"analyzing file {file_path}", error_types=(SyntaxError, ProcessingError)):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            # Parse the AST
            tree = ast.parse(content, filename=file_path)
            
            # Run the visitor
            visitor = ExceptionPatternVisitor(file_path, result)
            visitor.visit(tree)
            
            # Check for imports of error handling utilities
            has_error_imports = False
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for name in node.names:
                        if 'error_handling' in name.name:
                            has_error_imports = True
                            break
                elif isinstance(node, ast.ImportFrom):
                    if 'error_handling' in node.module:
                        has_error_imports = True
                        break
                
                if has_error_imports:
                    break
            
            # If there are try/except blocks but no error_handling imports
            try_except_count = sum(1 for n in ast.walk(tree) if isinstance(n, ast.Try))
            if try_except_count > 0 and not has_error_imports:
                result.add_issue(ExceptionIssue(
                    file_path=file_path,
                    line_number=1,
                    issue_type="missing_error_handling_import",
                    description="File contains exception handling but doesn't import error_handling utilities",
                    severity="medium",
                    suggested_fix="Import error handling utilities: from utils.error_handling import handle_errors, ErrorBoundary"
                ))
            
            # Special check for database operations
            if 'db/' in file_path and not '/test' in file_path:
                # Check if retry_utils is imported for database operations
                has_retry_imports = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for name in node.names:
                            if 'retry_utils' in name.name:
                                has_retry_imports = True
                                break
                    elif isinstance(node, ast.ImportFrom):
                        if 'retry_utils' in (node.module or ''):
                            has_retry_imports = True
                            break
                    
                    if has_retry_imports:
                        break
                
                if not has_retry_imports and try_except_count > 0:
                    result.add_issue(ExceptionIssue(
                        file_path=file_path,
                        line_number=1,
                        issue_type="missing_retry_mechanism",
                        description="Database operations file doesn't use retry mechanism",
                        severity="medium",
                        suggested_fix="Import and use retry utilities: from db.retry_utils import with_retry"
                    ))
        
        except SyntaxError as e:
            result.add_issue(ExceptionIssue(
                file_path=file_path,
                line_number=e.lineno or 1,
                issue_type="syntax_error",
                description=f"Syntax error: {str(e)}",
                severity="high",
                suggested_fix="Fix the syntax error to enable proper analysis"
            ))
        except Exception as e:
            # Use more specific exceptions when possible, but keep this general handler as a fallback
            result.add_issue(ExceptionIssue(
                file_path=file_path,
                line_number=1,
                issue_type="analysis_error",
                description=f"Error analyzing file: {str(e)}",
                severity="low",
                suggested_fix=None
            ))


@handle_errors(error_types=(ProcessingError,))
def analyze_codebase(directory: str, exclude_dirs: List[str] = None) -> AnalysisResult:
    """Analyze the entire codebase for exception handling patterns."""
    result = AnalysisResult()
    
    python_files = find_python_files(directory, exclude_dirs)
    result.files_analyzed = len(python_files)
    
    for file_path in python_files:
        analyze_file(file_path, result)
    
    return result


@handle_errors(error_types=(ProcessingError,))
def print_report(result: AnalysisResult, verbose: bool = False, severity_filter: Optional[str] = None, 
                issue_type_filter: Optional[str] = None, file_filter: Optional[str] = None,
                group_by_file: bool = False, fix_mode: bool = False, interactive: bool = True) -> None:
    """Print a human-readable report of the analysis results."""
    # Apply filters
    filtered_issues = result.issues
    
    # Apply severity filter if provided
    if severity_filter:
        filtered_issues = [i for i in filtered_issues if i.severity == severity_filter.lower()]
        
    # Apply issue type filter if provided
    if issue_type_filter:
        filtered_issues = [i for i in filtered_issues if i.issue_type == issue_type_filter]
        
    # Apply file filter if provided
    if file_filter:
        filtered_issues = [i for i in filtered_issues if file_filter in i.file_path]
    
    # Print header
    print("\n" + "=" * 80)
    print(f"EXCEPTION HANDLING ANALYSIS REPORT")
    print("=" * 80)
    
    # Print statistics
    print(f"\nFiles analyzed: {result.files_analyzed}")
    print(f"Total issues found: {len(result.issues)}")
    
    if severity_filter or issue_type_filter or file_filter:
        print(f"Filtered issues: {len(filtered_issues)}")
        if severity_filter:
            print(f"  - Severity filter: {severity_filter.upper()}")
        if issue_type_filter:
            print(f"  - Issue type filter: {issue_type_filter}")
        if file_filter:
            print(f"  - File filter: {file_filter}")
    
    # Print severity statistics
    print("\nIssues by severity:")
    for severity, count in sorted(result.issue_count_by_severity.items(), 
                                 key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x[0], 3)):
        print(f"  {severity.upper()}: {count}")
    
    # Print issue type statistics
    print("\nIssues by type:")
    for issue_type, count in sorted(result.issue_count_by_type.items(), key=lambda x: x[1], reverse=True):
        print(f"  {issue_type}: {count}")
    
    # If fix mode is enabled, show issues with fix suggestions
    if fix_mode and filtered_issues:
        print("\n" + "=" * 80)
        print("FIX MODE - Issues with suggested fixes:")
        print("=" * 80)
        
        # Sort issues by file and then by line number
        sorted_issues = sorted(filtered_issues, key=lambda x: (x.file_path, x.line_number))
        
        if interactive:
            # Interactive mode - show one issue at a time
            for i, issue in enumerate(sorted_issues):
                print(f"\n[{i+1}/{len(filtered_issues)}] {issue.file_path}:{issue.line_number}")
                print(f"Type: {issue.issue_type}")
                print(f"Severity: {issue.severity.upper()}")
                print(f"Description: {issue.description}")
                
                if issue.suggested_fix:
                    print("\nSuggested Fix:")
                    print("-" * 40)
                    
                    # For missing decorators, provide the exact code to add
                    if issue.issue_type == "missing_async_decorator":
                        print("Add this line before the function definition:")
                        print(f"@handle_async_errors")
                    elif issue.issue_type == "missing_decorator":
                        print("Add this line before the function definition:")
                        print(f"@handle_errors")
                    elif issue.issue_type == "missing_error_handling_import":
                        print("Add these imports at the top of the file:")
                        print("from utils.error_handling import handle_errors, handle_async_errors, ErrorBoundary")
                    elif issue.issue_type == "missing_retry_mechanism":
                        print("Add retry mechanism to database operations:")
                        print("from db.retry_utils import with_retry")
                        print("\nAnd decorate functions that perform database operations:")
                        print("@with_retry()")
                    else:
                        print(issue.suggested_fix)
                    print("-" * 40)
                
                print("\nPress Enter to continue to the next issue, or type 'q' to quit fix mode")
                if i < len(filtered_issues) - 1:  # Don't wait for input on the last issue
                    response = input()
                    if response.lower() == 'q':
                        break
        else:
            # Non-interactive mode - show all issues at once
            current_file = None
            for i, issue in enumerate(sorted_issues):
                # Group by file for better readability in non-interactive mode
                if current_file != issue.file_path:
                    current_file = issue.file_path
                    print(f"\n\nFile: {current_file}")
                    print("-" * (len(f"File: {current_file}")))
                
                print(f"\n[{i+1}/{len(filtered_issues)}] Line {issue.line_number}")
                print(f"Type: {issue.issue_type}")
                print(f"Severity: {issue.severity.upper()}")
                print(f"Description: {issue.description}")
                
                if issue.suggested_fix:
                    print("\nSuggested Fix:")
                    print("-" * 40)
                    
                    # For missing decorators, provide the exact code to add
                    if issue.issue_type == "missing_async_decorator":
                        print("Add this line before the function definition:")
                        print(f"@handle_async_errors")
                    elif issue.issue_type == "missing_decorator":
                        print("Add this line before the function definition:")
                        print(f"@handle_errors")
                    elif issue.issue_type == "missing_error_handling_import":
                        print("Add these imports at the top of the file:")
                        print("from utils.error_handling import handle_errors, handle_async_errors, ErrorBoundary")
                    elif issue.issue_type == "missing_retry_mechanism":
                        print("Add retry mechanism to database operations:")
                        print("from db.retry_utils import with_retry")
                        print("\nAnd decorate functions that perform database operations:")
                        print("@with_retry()")
                    else:
                        print(issue.suggested_fix)
                    print("-" * 40)
        
        return  # Exit after fix mode
    
    # Group by file if requested
    if group_by_file and filtered_issues:
        print("\nIssues grouped by file:")
        # Group issues by file
        issues_by_file = {}
        for issue in filtered_issues:
            if issue.file_path not in issues_by_file:
                issues_by_file[issue.file_path] = []
            issues_by_file[issue.file_path].append(issue)
        
        # Print issues grouped by file
        for file_path, issues in sorted(issues_by_file.items()):
            print(f"\nFile: {file_path}")
            print("-" * len(f"File: {file_path}"))
            print(f"Total issues: {len(issues)}")
            
            # Count issues by severity in this file
            severity_counts = {}
            for issue in issues:
                severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
            
            for severity in ["high", "medium", "low"]:
                if severity in severity_counts:
                    print(f"  {severity.upper()}: {severity_counts[severity]}")
            
            # Print issues in this file
            for issue in sorted(issues, key=lambda x: x.line_number):
                severity_marker = {
                    'high': '!!!',
                    'medium': ' !!',
                    'low': '  !'
                }.get(issue.severity, '   ')
                
                print(f"  {severity_marker} Line {issue.line_number}: {issue.description}")
                if verbose and issue.suggested_fix:
                    print(f"      Suggestion: {issue.suggested_fix}")
        
        return  # Exit after grouped output
    
    # Regular detailed or summary output
    if verbose:
        print("\nDetailed Issues:")
        for issue in sorted(filtered_issues, key=lambda x: (x.severity, x.file_path, x.line_number)):
            severity_marker = {
                'high': '!!!',
                'medium': ' !!',
                'low': '  !'
            }.get(issue.severity, '   ')
            
            print(f"\n{severity_marker} {issue.file_path}:{issue.line_number}")
            print(f"    Type: {issue.issue_type}")
            print(f"    Description: {issue.description}")
            if issue.suggested_fix:
                print(f"    Suggestion: {issue.suggested_fix}")
    else:
        # Print summary of filtered or high severity issues
        high_severity = [i for i in filtered_issues if i.severity == 'high'] if not severity_filter else filtered_issues
        if high_severity:
            print("\nHigh Severity Issues:") if not severity_filter else print(f"\n{severity_filter.capitalize()} Severity Issues:")
            for issue in sorted(high_severity, key=lambda x: (x.file_path, x.line_number))[:10]:  # Show top 10
                print(f"  {issue.file_path}:{issue.line_number} - {issue.description}")
            
            if len(high_severity) > 10:
                print(f"  ... and {len(high_severity) - 10} more {severity_filter if severity_filter else 'high'} severity issues")
    
    # Provide recommendations
    print("\nRecommendations:")
    if result.issue_count_by_type.get('bare_except', 0) > 0:
        print("  - Replace bare except clauses with specific exception types")
    if result.issue_count_by_type.get('silent_except', 0) > 0:
        print("  - Add proper error handling instead of silently ignoring exceptions")
    if result.issue_count_by_type.get('missing_decorator', 0) > 0:
        print("  - Add handle_errors or handle_async_errors decorators to functions with try/except")
    if result.issue_count_by_type.get('missing_error_handling_import', 0) > 0:
        print("  - Import error handling utilities in files with exception handling")
    if result.issue_count_by_type.get('missing_retry_mechanism', 0) > 0:
        print("  - Apply retry mechanism to database operations")
    
    print("\nFor detailed guidelines, see docs/exception_handling_guide.md")
    print("=" * 80)


@handle_errors(error_types=(ProcessingError, IOError))
def main():
    parser = argparse.ArgumentParser(description="Analyze exception handling patterns in Python code")
    parser.add_argument("directory", nargs="?", default=".", help="Directory to analyze (defaults to current directory)")
    parser.add_argument("--exclude", nargs="+", default=None, help="Directories to exclude")
    parser.add_argument("--output", "-o", help="Output file for JSON report")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show detailed issue information")
    parser.add_argument("--severity", choices=["high", "medium", "low"], 
                       help="Filter issues by severity (high, medium, or low)")
    parser.add_argument("--issue-type", dest="issue_type", 
                       help="Filter issues by type (e.g., missing_async_decorator, broad_except)")
    parser.add_argument("--file", help="Filter issues to only those in files matching this pattern")
    parser.add_argument("--group-by-file", action="store_true", help="Group issues by file")
    parser.add_argument("--fix-mode", action="store_true", 
                       help="Mode showing issues with fix suggestions")
    parser.add_argument("--non-interactive", action="store_true",
                       help="Show all fixes at once without waiting for user input (use with --fix-mode)")
    args = parser.parse_args()
    
    # Construct the exclude list
    exclude_dirs = ['.git', '.venv', 'venv', 'env', '__pycache__']
    if args.exclude:
        exclude_dirs.extend(args.exclude)
    
    # Analyze the codebase
    print(f"Analyzing Python files in {args.directory}...")
    result = analyze_codebase(args.directory, exclude_dirs)
    
    # Determine if interactive mode should be used
    interactive = not args.non_interactive
    
    # Print human-readable report
    print_report(result, args.verbose, args.severity, args.issue_type, args.file, 
                args.group_by_file, args.fix_mode, interactive)
    
    # Save JSON report if requested
    if args.output:
        # Apply filters to JSON output if provided
        filtered_issues = result.issues
        
        if args.severity:
            filtered_issues = [i for i in filtered_issues if i.severity == args.severity.lower()]
            
        if args.issue_type:
            filtered_issues = [i for i in filtered_issues if i.issue_type == args.issue_type]
            
        if args.file:
            filtered_issues = [i for i in filtered_issues if args.file in i.file_path]
        
        # Create filtered result
        if args.severity or args.issue_type or args.file:
            filtered_result = AnalysisResult()
            filtered_result.files_analyzed = result.files_analyzed
            filtered_result.issue_count_by_type = result.issue_count_by_type
            filtered_result.issue_count_by_severity = result.issue_count_by_severity
            filtered_result.issues = filtered_issues
            json_result = filtered_result.to_dict()
        else:
            json_result = result.to_dict()
            
        with open(args.output, 'w', encoding='utf-8') as f:
            json.dump(json_result, f, indent=2)
        print(f"\nDetailed report saved to {args.output}")


if __name__ == "__main__":
    main() 