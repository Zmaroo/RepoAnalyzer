#!/usr/bin/env python3
"""
Comprehensive Error Boundary Fix Script

This script fixes multiple issues related to error boundaries across the codebase:
1. Adds missing imports for AsyncErrorBoundary
2. Converts ErrorBoundary to AsyncErrorBoundary in async functions/methods
3. Updates parameter formats to use named parameters consistently
4. Fixes database pool references in cleanup methods

Usage:
    python comprehensive_error_boundary_fix.py [directory]
"""

import os
import re
import ast
import sys
import astor
from typing import List, Dict, Tuple, Set, Optional


class ErrorBoundaryVisitor(ast.NodeVisitor):
    """AST visitor to find error boundary issues."""
    
    def __init__(self):
        self.async_functions = set()
        self.error_boundary_uses = []
        self.async_error_boundary_uses = []
        self.import_issues = {}
        self.pool_references = []
        
@handle_errors(error_types=(Exception,))
    def visit_AsyncFunctionDef(self, node):
        """Track async functions."""
        self.async_functions.add(node.name)
        self.generic_visit(node)
@handle_errors(error_types=(Exception,))
        
    def visit_With(self, node):
        """Find with statements using ErrorBoundary or AsyncErrorBoundary."""
        for item in node.items:
            if isinstance(item.context_expr, ast.Call):
                if isinstance(item.context_expr.func, ast.Name):
                    if item.context_expr.func.id == 'ErrorBoundary':
                        self.error_boundary_uses.append((node, item.context_expr))
                    elif item.context_expr.func.id == 'AsyncErrorBoundary':
                        self.async_error_boundary_uses.append((node, item.context_expr))
@handle_errors(error_types=(Exception,))
        self.generic_visit(node)
        
    def visit_Import(self, node):
        """Track imports."""
        for name in node.names:
            if 'error_handling' in name.name:
                # Found error_handling import
                if not name.asname:  # Not aliased
@handle_errors(error_types=(Exception,))
                    self.import_issues[node] = {'node': node, 'type': 'direct_import', 'has_async': False}
        self.generic_visit(node)
        
    def visit_ImportFrom(self, node):
        """Track from imports."""
        if node.module and 'error_handling' in node.module:
            # Check if AsyncErrorBoundary is imported
@handle_errors(error_types=(Exception,))
            has_async = any(name.name == 'AsyncErrorBoundary' for name in node.names)
            self.import_issues[node] = {'node': node, 'type': 'from_import', 'has_async': has_async}
        self.generic_visit(node)
        
    def visit_Assign(self, node):
        """Find assignments involving _pool."""
        # Look for uses of _pool that might need to be changed to db.psql._pool
        if isinstance(node.value, ast.Attribute) and isinstance(node.value.value, ast.Name):
            if node.value.attr == '_pool':
                self.pool_references.append(node)
        self.generic_visit(node)


@handle_errors(error_types=(Exception,))
def find_python_files(directory: str) -> List[str]:
    """Find all Python files in the given directory and its subdirectories."""
    python_files = []
    for root, _, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                python_files.append(os.path.join(root, file))
    return python_files

@handle_errors(error_types=(Exception,))

def analyze_file(file_path: str) -> Tuple[ast.Module, ErrorBoundaryVisitor]:
    """
    Analyze a Python file for error boundary issues.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        Tuple of (ast_tree, visitor)
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    try:
        tree = ast.parse(content)
        visitor = ErrorBoundaryVisitor()
        visitor.visit(tree)
        return tree, visitor
    except SyntaxError:
        print(f"Syntax error in {file_path}, skipping")
        return None, None
@handle_errors(error_types=(Exception,))


def fix_error_boundary_issues(file_path: str, tree: ast.Module, visitor: ErrorBoundaryVisitor) -> bool:
    """
    Fix error boundary issues in a Python file.
    
    Args:
        file_path: Path to the Python file
        tree: AST tree of the file
        visitor: Visitor with detected issues
        
    Returns:
        True if the file was modified, False otherwise
    """
    modified = False
    
    # 1. Fix imports
    if visitor.error_boundary_uses or visitor.async_error_boundary_uses:
        # Need to ensure necessary imports
        if not any(info['has_async'] for info in visitor.import_issues.values()):
            # Need to add AsyncErrorBoundary import
            for node, info in visitor.import_issues.items():
                if info['type'] == 'from_import':
                    # Add AsyncErrorBoundary to existing import
                    for name in node.names:
                        if name.name == 'ErrorBoundary':
                            # Add AsyncErrorBoundary after ErrorBoundary
                            import_names = [n.name for n in node.names]
                            if 'AsyncErrorBoundary' not in import_names:
                                node.names.append(ast.alias(name='AsyncErrorBoundary', asname=None))
                                modified = True
                                break
            
            # If no suitable import to modify or no error_handling import at all
            if not modified and visitor.import_issues:
                # Get first import to determine indentation
                import_nodes = list(visitor.import_issues.keys())
                if import_nodes:
                    # Add AsyncErrorBoundary to existing import
                    first_node = import_nodes[0]
                    if visitor.import_issues[first_node]['type'] == 'from_import':
                        first_node.names.append(ast.alias(name='AsyncErrorBoundary', asname=None))
                        modified = True
            
            # If no error_handling import at all, add one at the top
            if not visitor.import_issues and (visitor.error_boundary_uses or visitor.async_error_boundary_uses):
                # Need to add a new import
                new_import = ast.ImportFrom(
                    module='utils.error_handling',
                    names=[
                        ast.alias(name='ErrorBoundary', asname=None),
                        ast.alias(name='AsyncErrorBoundary', asname=None)
                    ],
                    level=0
                )
                # Add at the top, after any existing imports
                for i, node in enumerate(tree.body):
                    if not isinstance(node, (ast.Import, ast.ImportFrom)):
                        tree.body.insert(i, new_import)
                        modified = True
                        break
                else:
                    # No non-import statements, append to the end
                    tree.body.append(new_import)
                    modified = True
    
    # 2. Convert ErrorBoundary to AsyncErrorBoundary in async functions
    # Get all with statements that are inside async functions
    for node, call_node in visitor.error_boundary_uses:
        # Check if this with statement is inside an async function
        for async_func in ast.walk(tree):
            if isinstance(async_func, ast.AsyncFunctionDef):
                # Check if the with statement is inside this async function
                if any(node is n or node in ast.walk(n) for n in async_func.body):
                    # Change ErrorBoundary to AsyncErrorBoundary
                    call_node.func.id = 'AsyncErrorBoundary'
                    modified = True
                    break
    
    # 3. Fix parameter format for ErrorBoundary and AsyncErrorBoundary
    for node, call_node in visitor.error_boundary_uses + visitor.async_error_boundary_uses:
        # Check for positional string argument
        if call_node.args and isinstance(call_node.args[0], ast.Str):
            # Convert to named parameter
            operation_name = call_node.args[0]
            call_node.args = call_node.args[1:]  # Remove first arg
            call_node.keywords.append(ast.keyword(arg='operation_name', value=operation_name))
            modified = True
    
    # 4. Fix database pool references in cleanup methods
    # This is harder with AST, so we'll use regex for this part
    if modified:
        # If we've already modified the AST, write it back first
        try:
            new_content = astor.to_source(tree)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)
        except Exception as e:
            print(f"Error writing AST back to {file_path}: {e}")
            return modified
    
    # Now fix pool references with regex
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Pattern for _pool without qualification in database cleanup
    # This is a simplified approach - a more robust approach would use AST
    # to analyze the function context
    pattern = r'await\s+_pool\.release\('
    replace = r'await db.psql._pool.release('
    
    if re.search(pattern, content):
        new_content = re.sub(pattern, replace, content)
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        modified = True
    
    # Also check for proper db import for db.psql._pool
    if 'db.psql._pool' in content and 'import db.psql' not in content:
        # Need to add import for db.psql
        lines = content.split('\n')
        import_line = 'import db.psql'
        
        # Find a good place to add the import
        import_added = False
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                if i < len(lines) - 1 and (not lines[i+1].startswith('import ') and not lines[i+1].startswith('from ')):
                    # Insert after the last import
                    lines.insert(i+1, import_line)
                    import_added = True
                    break
        
        if not import_added and lines:
            # Add after the first docstring if exists
            in_docstring = False
            for i, line in enumerate(lines):
                if line.strip().startswith('"""') or line.strip().startswith("'''"):
                    in_docstring = not in_docstring
                    if not in_docstring:
                        # End of docstring
                        lines.insert(i+1, '')
                        lines.insert(i+2, import_line)
                        import_added = True
                        break
            
            if not import_added:
                # Add at the top
                lines.insert(0, import_line)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))
        modified = True
    
@handle_errors(error_types=(Exception,))
    return modified


def apply_transaction_cleanup_fix(file_path: str) -> bool:
    """
    Apply a specific fix for the transaction _cleanup method issue.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        True if the file was modified, False otherwise
    """
    if not file_path.endswith('transaction.py'):
        return False
    
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Look for the _cleanup method in TransactionCoordinator
    if 'async def _cleanup' in content and 'class TransactionCoordinator' in content:
        # Check if db.psql import is missing
        if 'import db.psql' not in content:
            lines = content.split('\n')
            
            # Find TransactionCoordinator class
            in_class = False
            in_cleanup = False
            cleanup_start = -1
            cleanup_end = -1
            
            for i, line in enumerate(lines):
                if 'class TransactionCoordinator' in line:
                    in_class = True
                elif in_class and 'async def _cleanup' in line:
                    in_cleanup = True
                    cleanup_start = i
                elif in_cleanup and line.strip().startswith('async def '):
                    # Next method, end of cleanup
                    cleanup_end = i
                    break
                elif in_cleanup and line.strip() == '':
                    # Empty line could indicate end of method
                    for j in range(i+1, len(lines)):
                        if lines[j].strip() and not lines[j].startswith(' '):
                            # Not indented, end of method
                            cleanup_end = j
                            break
                        elif lines[j].strip().startswith('async def '):
                            # Next method
                            cleanup_end = j
                            break
                        elif lines[j].strip():
                            # Still in method
                            break
            
            if cleanup_start >= 0:
                # Found the cleanup method
                if cleanup_end < 0:
                    cleanup_end = len(lines)
                
                # Check if we need to add the import and fix the pool reference
                needs_import = True
                pool_fixed = False
                
                for i in range(cleanup_start, cleanup_end):
                    line = lines[i]
                    if 'import db.psql' in line:
                        needs_import = False
                    if 'await db.psql._pool.release' in line:
                        pool_fixed = True
                
                if needs_import or not pool_fixed:
                    # Apply the fix
                    new_lines = lines.copy()
                    
                    # Add import at the start of the _cleanup method
                    if needs_import:
                        indent = len(lines[cleanup_start]) - len(lines[cleanup_start].lstrip())
                        indent_str = ' ' * indent
                        new_lines.insert(cleanup_start + 1, f"{indent_str}import db.psql")
                    
                    # Fix _pool reference
                    if not pool_fixed:
                        for i in range(cleanup_start, cleanup_end):
                            if 'await _pool.release' in new_lines[i]:
                                new_lines[i] = new_lines[i].replace('await _pool.release', 'await db.psql._pool.release')
                    
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write('\n'.join(new_lines))
                    
                    return True
@handle_errors(error_types=(Exception,))
    
    return False


def fix_with_regex(file_path: str) -> bool:
    """
    Apply regex-based fixes that might be harder with AST.
    
    Args:
        file_path: Path to the Python file
        
    Returns:
        True if the file was modified, False otherwise
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    modified = False
    
    # 1. Fix converting "with ErrorBoundary" to "async with AsyncErrorBoundary" in async functions
    # This is difficult with AST due to context, so using regex
    pattern1 = r'(async\s+def\s+\w+.*?:.*?)with\s+ErrorBoundary'
    replace1 = r'\1async with AsyncErrorBoundary'
    
    if re.search(pattern1, content, re.DOTALL):
        content = re.sub(pattern1, replace1, content)
        modified = True
    
    # 2. Fix parameters for AsyncErrorBoundary
    pattern2 = r'AsyncErrorBoundary\((["\'].*?["\']),?'
    replace2 = r'AsyncErrorBoundary(operation_name=\1'
    
    if re.search(pattern2, content):
        content = re.sub(pattern2, replace2, content)
        modified = True
    
    # 3. Fix parameters for ErrorBoundary
    pattern3 = r'ErrorBoundary\((["\'].*?["\']),?'
    replace3 = r'ErrorBoundary(operation_name=\1'
    
    if re.search(pattern3, content):
        content = re.sub(pattern3, replace3, content)
        modified = True
    
    if modified:
        with open(file_path, 'w', encoding='utf-8') as f:
@handle_errors(error_types=(Exception,))
            f.write(content)
    
    return modified


def main():
    """Main function."""
    directory = sys.argv[1] if len(sys.argv) > 1 else '.'
    print(f"Analyzing Python files in {directory}")
    
    python_files = find_python_files(directory)
    print(f"Found {len(python_files)} Python files")
    
    modified_files = 0
    
    for file_path in python_files:
        print(f"Checking {file_path}")
        
        # Try the AST-based approach first
        try:
            tree, visitor = analyze_file(file_path)
            if tree and visitor:
                if fix_error_boundary_issues(file_path, tree, visitor):
                    modified_files += 1
                    print(f"Fixed AST-based issues in {file_path}")
        except Exception as e:
            print(f"Error analyzing {file_path} with AST: {e}")
        
        # Now try the transaction cleanup specific fix
        try:
            if apply_transaction_cleanup_fix(file_path):
                modified_files += 1
                print(f"Fixed transaction cleanup in {file_path}")
        except Exception as e:
            print(f"Error fixing transaction cleanup in {file_path}: {e}")
        
        # Finally, try regex-based fixes
        try:
            if fix_with_regex(file_path):
                modified_files += 1
                print(f"Fixed regex-based issues in {file_path}")
        except Exception as e:
            print(f"Error applying regex fixes to {file_path}: {e}")
    
    print(f"\nSummary: Modified {modified_files} files")


if __name__ == "__main__":
    main() 