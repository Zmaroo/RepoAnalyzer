"""Query patterns for Assembly files."""

from .common import COMMON_PATTERNS

ASM_PATTERNS = {
    **COMMON_PATTERNS,  # Keep as fallback for basic patterns
    
    "syntax": {
        "instruction": {
            "pattern": """
            [
                (instruction
                    kind: (word) @syntax.instruction.name
                    [
                        (ident) @syntax.instruction.operand.ident
                        (int) @syntax.instruction.operand.immediate
                        (ptr) @syntax.instruction.operand.pointer
                        (reg) @syntax.instruction.operand.register
                        (string) @syntax.instruction.operand.string
                        (tc_infix) @syntax.instruction.operand.expression
                    ]*) @syntax.instruction.def,
                
                (label
                    name: (word) @syntax.label.name) @syntax.label.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("syntax.instruction.name", {}).get("text", ""),
                "operands": [op.get("text", "") for op in 
                           node["captures"].get("syntax.instruction.operand.ident", []) +
                           node["captures"].get("syntax.instruction.operand.immediate", []) +
                           node["captures"].get("syntax.instruction.operand.register", [])]
            }
        }
    },
    
    "semantics": {
        "constant": {
            "pattern": """
            [
                (const
                    name: (word) @semantics.constant.name
                    value: [
                        (ident) @semantics.constant.value.ident
                        (int) @semantics.constant.value.int
                        (string) @semantics.constant.value.string
                        (tc_infix) @semantics.constant.value.expr
                    ]) @semantics.constant.def,
                
                (meta
                    kind: (meta_ident) @semantics.meta.kind
                    [(ident) @semantics.meta.value.ident
                     (int) @semantics.meta.value.int
                     (string) @semantics.meta.value.string
                     (float) @semantics.meta.value.float]*) @semantics.meta.def
            ]
            """,
            "extract": lambda node: {
                "name": node["captures"].get("semantics.constant.name", {}).get("text", ""),
                "value": (node["captures"].get("semantics.constant.value.int", {}).get("text", "") or
                         node["captures"].get("semantics.constant.value.string", {}).get("text", ""))
            }
        },
        
        "memory": {
            "pattern": """
            [
                (ptr
                    [(ident) @semantics.memory.base
                     (int) @semantics.memory.offset
                     (reg) @semantics.memory.register]*) @semantics.memory.pointer,
                
                (reg
                    [(address) @semantics.register.address
                     (word) @semantics.register.name]*) @semantics.register
            ]
            """,
            "extract": lambda node: {
                "base": node["captures"].get("semantics.memory.base", {}).get("text", ""),
                "offset": node["captures"].get("semantics.memory.offset", {}).get("text", ""),
                "register": node["captures"].get("semantics.memory.register", {}).get("text", "")
            }
        }
    },
    
    "structure": {
        "program": {
            "pattern": """
            [
                (program
                    [(const) @structure.program.constant
                     (instruction) @structure.program.instruction
                     (label) @structure.program.label
                     (meta) @structure.program.meta]*) @structure.program.def
            ]
            """,
            "extract": lambda node: {
                "constants": [c.get("text", "") for c in node["captures"].get("structure.program.constant", [])],
                "labels": [l.get("text", "") for l in node["captures"].get("structure.program.label", [])]
            }
        }
    },
    
    "documentation": {
        "comments": {
            "pattern": """
            [
                (line_comment) @documentation.comment.line,
                (block_comment) @documentation.comment.block
            ]
            """,
            "extract": lambda node: {
                "text": node["captures"].get("documentation.comment.line", {}).get("text", "") or
                       node["captures"].get("documentation.comment.block", {}).get("text", ""),
                "type": "line" if "documentation.comment.line" in node["captures"] else "block"
            }
        }
    }
} 

# Repository learning patterns for Assembly
ASM_PATTERNS_FOR_LEARNING = {
    "naming_conventions": {
        "pattern": """
        [
            (label
                name: (word) @naming.label.name) @naming.label,
                
            (const
                name: (word) @naming.const.name) @naming.const
        ]
        """,
        "extract": lambda node: {
            "type": "naming_convention_pattern",
            "name": node["node"].text.decode('utf8'),
            "convention": "label" if "naming.label" in node["captures"] else "constant",
            "is_uppercase": all(c.isupper() or not c.isalpha() for c in node["node"].text.decode('utf8'))
        }
    },
    
    "code_structure": {
        "pattern": """
        [
            (program
                [(const) @structure.const
                 (instruction) @structure.instruction
                 (label) @structure.label
                 (meta) @structure.meta]) @structure.program
        ]
        """,
        "extract": lambda node: {
            "type": "code_structure_pattern",
            "has_constants": "structure.const" in node["captures"],
            "has_labels": "structure.label" in node["captures"],
            "has_metadata": "structure.meta" in node["captures"]
        }
    },
    
    "instructions": {
        "pattern": """
        [
            (instruction
                kind: (word) @instruction.kind) @instruction.def
        ]
        """,
        "extract": lambda node: {
            "type": "instruction_pattern",
            "instruction": node["captures"].get("instruction.kind", {}).get("text", "").lower(),
            "is_jump": node["captures"].get("instruction.kind", {}).get("text", "").lower() in ["jmp", "je", "jne", "jz", "jnz", "call"],
            "is_arithmetic": node["captures"].get("instruction.kind", {}).get("text", "").lower() in ["add", "sub", "mul", "div", "inc", "dec"]
        }
    }
}

# Add the repository learning patterns to the main patterns
ASM_PATTERNS['REPOSITORY_LEARNING'] = ASM_PATTERNS_FOR_LEARNING 