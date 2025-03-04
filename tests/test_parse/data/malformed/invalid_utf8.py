# This file contains invalid UTF-8 sequences

def invalid_utf8():
    # Invalid UTF-8 sequences
    str1 = b'\xff\xfe\xfd'.decode('utf8', 'ignore')
    str2 = b'\x80\x81\x82'.decode('utf8', 'ignore')
    
    # More invalid sequences
    text = b'''
    \xff\xff Invalid bytes
    \x80\x81 More invalid bytes
    \xfe\xff Yet more invalid bytes
    '''.decode('utf8', 'ignore')
    
    # Mix valid and invalid
    result = "Valid UTF-8: 你好" + str1 + str2 + text
    
    return result

# Invalid string literal
s = "Invalid sequence: \xff\xfe"

# Invalid comment with binary data
# Here's some invalid UTF-8: \xff\xfe\xfd

print(invalid_utf8()) 