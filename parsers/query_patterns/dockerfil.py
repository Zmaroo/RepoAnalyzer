"""
Query patterns for Dockerfile parsing.
This module is named 'dockerfil' to avoid conflicts with 'dockerfile'.
"""

# Dockerfile specific patterns
DOCKERFILE_PATTERNS = {
    "instruction": {
        "pattern": r"^\s*(FROM|MAINTAINER|RUN|CMD|ENTRYPOINT|LABEL|ENV|ADD|COPY|VOLUME|USER|WORKDIR|ARG|ONBUILD|STOPSIGNAL|HEALTHCHECK|SHELL)\s+(.+)$",
        "flags": ["MULTILINE"],
        "extract": lambda m: {
            "instruction": m.group(1),
            "value": m.group(2)
        }
    },
    "comment": {
        "pattern": r"^\s*#\s*(.+)$",
        "flags": ["MULTILINE"],
        "extract": lambda m: {
            "comment": m.group(1)
        }
    },
    "variable": {
        "pattern": r"\$(?:\{([A-Za-z0-9_]+)(?::-([^}]+))?\}|([A-Za-z0-9_]+))",
        "extract": lambda m: {
            "variable": m.group(1) or m.group(3),
            "default": m.group(2)
        }
    },
    "base_image": {
        "pattern": r"^\s*FROM\s+(?:--platform=[^\s]+\s+)?([^\s:]+)(?::([^\s]+))?(?:\s+(?:as|AS)\s+([^\s]+))?",
        "flags": ["MULTILINE"],
        "extract": lambda m: {
            "image": m.group(1),
            "tag": m.group(2) or "latest",
            "alias": m.group(3)
        }
    },
    "expose": {
        "pattern": r"^\s*EXPOSE\s+(\d+(?:-\d+)?(?:\/(?:tcp|udp))?(?:\s+\d+(?:-\d+)?(?:\/(?:tcp|udp))?)*)",
        "flags": ["MULTILINE"],
        "extract": lambda m: {
            "ports": m.group(1).split()
        }
    },
}

# Define patterns for feature extraction
FROM_PATTERN = {
    "pattern": r"^\s*FROM\s+(?:--platform=[^\s]+\s+)?([^\s:]+)(?::([^\s]+))?(?:\s+(?:as|AS)\s+([^\s]+))?",
    "flags": ["MULTILINE"],
}

RUN_PATTERN = {
    "pattern": r"^\s*RUN\s+(.+)$",
    "flags": ["MULTILINE"],
}

# Avoid circular imports by providing static functions
def extract_dockerfile_patterns_for_learning(content):
    """Extract patterns from Dockerfile content for repository learning."""
    from parsers.pattern_processor import pattern_processor
    
    # Extract patterns without circular import
    patterns = []
    
    # Simple regex patterns instead of depending on pattern_processor
    import re
    
    # Extract FROM instructions
    from_matches = re.finditer(r"^\s*FROM\s+(?:--platform=[^\s]+\s+)?([^\s:]+)(?::([^\s]+))?(?:\s+(?:as|AS)\s+([^\s]+))?", 
                               content, re.MULTILINE)
    for match in from_matches:
        patterns.append({
            'name': 'dockerfile_base_image',
            'content': match.group(0),
            'language': 'dockerfile',
            'confidence': 0.9,
            'metadata': {
                'image': match.group(1),
                'tag': match.group(2) or "latest",
                'alias': match.group(3)
            }
        })
    
    # Extract RUN instructions
    run_matches = re.finditer(r"^\s*RUN\s+(.+)$", content, re.MULTILINE)
    for match in run_matches:
        patterns.append({
            'name': 'dockerfile_run_command',
            'content': match.group(0),
            'language': 'dockerfile',
            'confidence': 0.85,
            'metadata': {
                'command': match.group(1)
            }
        })
    
    return patterns

# Module identification
LANGUAGE = "dockerfile" 