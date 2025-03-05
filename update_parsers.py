import os
import re

parser_dir = "parsers/custom_parsers"
for filename in os.listdir(parser_dir):
    if filename.startswith("custom_") and filename.endswith(".py"):
        filepath = os.path.join(parser_dir, filename)
        with open(filepath, "r") as f:
            content = f.read()
        
        # Remove pattern imports
        content = re.sub(r"from parsers\.query_patterns\.[a-z_]+ import [A-Z_]+PATTERNS\n", "", content)
        
        # Remove pattern compilation
        content = re.sub(r"\s+self\.patterns = self\._compile_patterns\([A-Z_]+PATTERNS\)\n", "", content)
        
        # Add pattern loading
        content = content.replace(
            "                    self._initialized = True",
            "                    await self._load_patterns()  # Load patterns through BaseParser mechanism\n                    self._initialized = True"
        )
        
        with open(filepath, "w") as f:
            f.write(content)

print("Updated all parser files") 