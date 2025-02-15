"""
Query patterns for plain text files.

Since our AST for plaintext files contains a series of lines, we can simply map each line.
"""

PLAINTEXT_PATTERNS = [
    "(plaintext (line) @line)"
] 