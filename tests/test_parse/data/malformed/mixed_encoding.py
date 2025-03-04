# -*- coding: utf-8 -*-
# This file contains mixed encodings

def mixed_encoding():
    # UTF-8 string
    str1 = "Hello, 世界"
    
    # Latin-1 string (will cause issues when mixed with UTF-8)
    str2 = b"Hello, \xf1".decode('latin1')
    
    # Invalid UTF-8 sequence
    str3 = b'\xff\xfe\xfd'.decode('utf8', 'ignore')
    
    # Mix of encodings
    result = str1 + str2 + str3
    
    return result

# More encoding issues
text = """
Some UTF-8: 你好
Some Latin-1: ñ
Some invalid bytes: �
"""

print(text) 