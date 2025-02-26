"""
Query patterns for Protocol Buffers files.
"""

from parsers.types import FileType
from .common import COMMON_PATTERNS

PROTO_PATTERNS_FOR_LEARNING = {
    "message_definitions": {
        "pattern": """
        [
            (message
                name: (message_name) @msg.name
                body: (message_body
                    (field
                        type: (type) @msg.field.type
                        name: (identifier) @msg.field.name)*)) @msg.def,
                        
            (message
                body: (message_body
                    (oneof
                        name: (identifier) @msg.oneof.name
                        fields: (oneof_field)* @msg.oneof.fields))) @msg.with.oneof,
                        
            (message
                body: (message_body
                    (map_field
                        key_type: (key_type) @msg.map.key_type
                        type: (type) @msg.map.value_type
                        name: (identifier) @msg.map.name))) @msg.with.map,
                        
            (message
                body: (message_body
                    (message
                        name: (message_name) @msg.nested.name))) @msg.with.nested
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "message_definitions",
            "is_message": "msg.def" in node["captures"],
            "has_oneof": "msg.with.oneof" in node["captures"],
            "has_map": "msg.with.map" in node["captures"],
            "has_nested_message": "msg.with.nested" in node["captures"],
            "message_name": node["captures"].get("msg.name", {}).get("text", ""),
            "field_type": node["captures"].get("msg.field.type", {}).get("text", ""),
            "field_name": node["captures"].get("msg.field.name", {}).get("text", ""),
            "oneof_name": node["captures"].get("msg.oneof.name", {}).get("text", ""),
            "map_name": node["captures"].get("msg.map.name", {}).get("text", ""),
            "nested_message_name": node["captures"].get("msg.nested.name", {}).get("text", ""),
            "message_complexity": (
                "complex" if any([
                    "msg.with.oneof" in node["captures"],
                    "msg.with.map" in node["captures"],
                    "msg.with.nested" in node["captures"]
                ]) else "simple"
            )
        }
    },
    
    "service_definitions": {
        "pattern": """
        [
            (service
                name: (service_name) @svc.name
                body: (service_body
                    (rpc
                        name: (rpc_name) @svc.rpc.name
                        input_type: (message_or_enum_type) @svc.rpc.req
                        output_type: (message_or_enum_type) @svc.rpc.resp))) @svc.def,
                        
            (rpc
                name: (rpc_name) @rpc.name
                input_type: (message_or_enum_type
                    stream: (stream)? @rpc.req.stream
                    message_name: (_) @rpc.req.type)
                output_type: (message_or_enum_type
                    stream: (stream)? @rpc.resp.stream
                    message_name: (_) @rpc.resp.type)) @rpc.def,
                    
            (rpc
                options: (option
                    name: [(full_ident) (identifier)] @rpc.option.name
                    value: (constant) @rpc.option.value)) @rpc.with.options
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "service_definitions",
            "is_service": "svc.def" in node["captures"],
            "is_rpc": "rpc.def" in node["captures"],
            "has_options": "rpc.with.options" in node["captures"],
            "service_name": node["captures"].get("svc.name", {}).get("text", ""),
            "rpc_name": node["captures"].get("svc.rpc.name", {}).get("text", "") or node["captures"].get("rpc.name", {}).get("text", ""),
            "request_type": node["captures"].get("svc.rpc.req", {}).get("text", "") or node["captures"].get("rpc.req.type", {}).get("text", ""),
            "response_type": node["captures"].get("svc.rpc.resp", {}).get("text", "") or node["captures"].get("rpc.resp.type", {}).get("text", ""),
            "request_is_stream": "rpc.req.stream" in node["captures"],
            "response_is_stream": "rpc.resp.stream" in node["captures"],
            "option_name": node["captures"].get("rpc.option.name", {}).get("text", ""),
            "option_value": node["captures"].get("rpc.option.value", {}).get("text", ""),
            "rpc_pattern": (
                "unary" if not ("rpc.req.stream" in node["captures"] or "rpc.resp.stream" in node["captures"]) else
                "client_streaming" if "rpc.req.stream" in node["captures"] and not "rpc.resp.stream" in node["captures"] else
                "server_streaming" if not "rpc.req.stream" in node["captures"] and "rpc.resp.stream" in node["captures"] else
                "bidirectional" if "rpc.req.stream" in node["captures"] and "rpc.resp.stream" in node["captures"] else
                "unknown"
            )
        }
    },
    
    "field_options": {
        "pattern": """
        [
            (field
                options: (field_options) @field.options) @field.with.options,
                
            (field_options
                (option
                    name: [(full_ident) (identifier)] @field.option.name
                    value: (constant) @field.option.value)) @field.option,
                    
            (option
                name: [(full_ident) (identifier)] @option.name
                value: (constant) @option.value) @option.def,
                
            (extend
                name: (message_or_enum_type) @extend.name
                body: (extend_body
                    (field) @extend.field)) @extend.def
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "field_options",
            "has_field_options": "field.with.options" in node["captures"],
            "is_option_definition": "option.def" in node["captures"],
            "is_extend_definition": "extend.def" in node["captures"],
            "field_option_name": node["captures"].get("field.option.name", {}).get("text", ""),
            "field_option_value": node["captures"].get("field.option.value", {}).get("text", ""),
            "option_name": node["captures"].get("option.name", {}).get("text", ""),
            "option_value": node["captures"].get("option.value", {}).get("text", ""),
            "extend_name": node["captures"].get("extend.name", {}).get("text", ""),
            "option_type": (
                "field_option" if "field.option" in node["captures"] else
                "file_option" if "option.def" in node["captures"] else
                "extension" if "extend.def" in node["captures"] else
                "unknown"
            ),
            "uses_common_options": any([
                "deprecated" in (node["captures"].get("field.option.name", {}).get("text", "") or node["captures"].get("option.name", {}).get("text", "")),
                "packed" in (node["captures"].get("field.option.name", {}).get("text", "") or node["captures"].get("option.name", {}).get("text", "")),
                "json_name" in (node["captures"].get("field.option.name", {}).get("text", "") or node["captures"].get("option.name", {}).get("text", ""))
            ])
        }
    },
    
    "best_practices": {
        "pattern": """
        [
            (package
                name: (full_ident) @pkg.name) @pkg.def,
                
            (import
                path: (string) @import.path) @import.def,
                
            (syntax
                value: (string) @syntax.version) @syntax.def,
                
            (enum
                name: (enum_name) @enum.name
                body: (enum_body
                    (enum_value
                        name: (identifier) @enum.field.name
                        value: (integer) @enum.field.value))) @enum.def,
                        
            (map_field
                key_type: (key_type) @field.map.key_type
                type: (type) @field.map.value_type) @field.map
        ]
        """,
        "extract": lambda node: {
            "pattern_type": "best_practices",
            "has_package": "pkg.def" in node["captures"],
            "has_import": "import.def" in node["captures"],
            "has_syntax": "syntax.def" in node["captures"],
            "is_enum": "enum.def" in node["captures"],
            "uses_map": "field.map" in node["captures"],
            "package_name": node["captures"].get("pkg.name", {}).get("text", ""),
            "import_path": node["captures"].get("import.path", {}).get("text", ""),
            "syntax_version": node["captures"].get("syntax.version", {}).get("text", ""),
            "enum_name": node["captures"].get("enum.name", {}).get("text", ""),
            "enum_field_name": node["captures"].get("enum.field.name", {}).get("text", ""),
            "enum_field_value": node["captures"].get("enum.field.value", {}).get("text", ""),
            "map_key_type": node["captures"].get("field.map.key_type", {}).get("text", ""),
            "map_value_type": node["captures"].get("field.map.value_type", {}).get("text", ""),
            "follows_convention": (
                node["captures"].get("pkg.name", {}).get("text", "").count(".") > 0 if "pkg.def" in node["captures"] else
                node["captures"].get("enum.field.name", {}).get("text", "").isupper() if "enum.def" in node["captures"] else
                "proto2" in node["captures"].get("syntax.version", {}).get("text", "") or "proto3" in node["captures"].get("syntax.version", {}).get("text", "") if "syntax.def" in node["captures"] else
                True
            )
        }
    }
}

PROTO_PATTERNS = {
    **COMMON_PATTERNS,
    "syntax": {
        "class": {
            "pattern": """
            [
                (message
                    name: (message_name) @syntax.class.name
                    body: (message_body) @syntax.class.body) @syntax.class.def,
                (enum
                    name: (enum_name) @syntax.enum.name
                    body: (enum_body) @syntax.enum.body) @syntax.enum.def,
                (service
                    name: (service_name) @syntax.service.name
                    body: (_) @syntax.service.body) @syntax.service.def
            ]
            """
        },
        "function": {
            "pattern": """
            [
                (rpc
                    name: (rpc_name) @syntax.function.name
                    input_type: (message_or_enum_type) @syntax.function.input
                    output_type: (message_or_enum_type) @syntax.function.output
                    options: (option)* @syntax.function.options) @syntax.function.def
            ]
            """
        },
        "field": {
            "pattern": """
            [
                (field
                    type: (type) @syntax.field.type
                    name: (identifier) @syntax.field.name
                    number: (field_number) @syntax.field.number
                    options: (field_options)? @syntax.field.options) @syntax.field.def,
                (map_field
                    key_type: (key_type) @syntax.field.map.key_type
                    type: (type) @syntax.field.map.value_type
                    name: (identifier) @syntax.field.map.name
                    number: (field_number) @syntax.field.map.number) @syntax.field.map.def,
                (oneof
                    name: (identifier) @syntax.field.oneof.name
                    fields: (oneof_field)* @syntax.field.oneof.fields) @syntax.field.oneof.def
            ]
            """
        }
    },
    "structure": {
        "namespace": {
            "pattern": """
            [
                (package
                    name: (full_ident) @structure.namespace.name) @structure.namespace.def,
                (source_file
                    syntax: (syntax) @structure.file.syntax
                    edition: (edition)? @structure.file.edition) @structure.file
            ]
            """
        },
        "import": {
            "pattern": """
            (import
                path: (string) @structure.import.path) @structure.import.def
            """
        },
        "option": {
            "pattern": """
            (option
                name: [(full_ident) (identifier)] @structure.option.name
                value: (constant) @structure.option.value) @structure.option.def
            """
        }
    },
    "semantics": {
        "variable": [
            """
            (field
                name: (identifier) @name
                type: (_) @type
                number: (_) @number) @variable
            """
        ],
        "type": [
            """
            (message_type
                name: (identifier) @name) @type
            """
        ]
    },
    "documentation": {
        "comment": {
            "pattern": """
            (comment) @documentation.comment
            """
        }
    },
    
    "REPOSITORY_LEARNING": PROTO_PATTERNS_FOR_LEARNING
} 