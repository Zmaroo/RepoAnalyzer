# Expanded ignore configuration for common directories and file patterns in GitHub repos.

IGNORED_DIRECTORIES = [
    '__pycache__', '.git', 'node_modules', 'venv', '.venv',
    'dist', 'build', '.idea', '.vscode', 'coverage', 'docs',
    'env', '.env', 'bin', 'obj', 'target', 'out',
    'logs', 'temp', 'tmp', 'cache', '.cache'
]

IGNORED_FILES = [
    # Development artifacts
    '*.pyc', '*.pyo', '*.pyd', '*.so', '*.dll', '*.dylib',
    '*.exe', '*.obj', '*.o',
    # Logs and temporary files
    '*.log', '*.tmp', '*.temp', '*.swp', '*.swo', '*.bak',
    '*.cache', '*.DS_Store',
    # Package files
    '*.egg-info', '*.egg', '*.whl',
    # IDE files
    '*.iml', '*.ipr', '*.iws', '*.project', '*.classpath',
    # Build artifacts
    '*.min.js', '*.min.css', '*.map'
]

# Add new configuration for more granular control
IGNORED_PATTERNS = [
    r'.*\.git.*',  # Git-related files
    r'.*\.pytest_cache.*',  # Pytest cache
    r'.*__pycache__.*',  # Python cache
    r'.*\.coverage.*',  # Coverage reports
    r'.*\.tox.*',  # Tox test environments
] 