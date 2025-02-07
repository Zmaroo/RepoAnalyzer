import unittest
from parsers.language_parser import parse_code, get_ast_sexp

class TreeSitterParserTest(unittest.TestCase):
    def test_basic_python_parsing(self):
        code = "def foo():\n    return 'bar'"
        tree = parse_code(code, "python")
        self.assertIsNotNone(tree, "Parser should return a valid tree")
        sexp = get_ast_sexp(tree)
        self.assertIn("module", sexp, "AST should contain module node")
        self.assertIn("function_definition", sexp, "AST should contain function definition")

    def test_invalid_code(self):
        code = "def foo() invalid syntax"
        tree = parse_code(code, "python")
        self.assertIsNotNone(tree, "Parser should return a tree even for invalid syntax")
        sexp = get_ast_sexp(tree)
        self.assertIn("ERROR", sexp, "AST should contain error node for invalid syntax")

    def test_empty_code(self):
        code = ""
        tree = parse_code(code, "python")
        self.assertIsNotNone(tree, "Parser should handle empty code")
        sexp = get_ast_sexp(tree)
        self.assertIn("module", sexp, "AST should contain module node even for empty code")

if __name__ == "__main__":
    unittest.main() 