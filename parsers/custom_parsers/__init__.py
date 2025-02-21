from typing import Dict, Set, Optional, Tuple, Any

from .custom_env_parser import EnvParser
from .custom_plaintext_parser import PlaintextParser
from .custom_yaml_parser import YamlParser
from .custom_markdown_parser import MarkdownParser
from .custom_editorconfig_parser import EditorconfigParser
from .custom_graphql_parser import GraphqlParser
from .custom_nim_parser import NimParser
from .custom_ocaml_parser import OCamlmlParser, OCamlmliParser
from .custom_cobalt_parser import CobaltParser
from .custom_xml_parser import XmlParser
from .custom_html_parser import HtmlParser
from .custom_ini_parser import IniParser
from .custom_json_parser import JsonParser
from .custom_rst_parser import RstParser
from .custom_toml_parser import TomlParser
from .custom_asciidoc_parser import AsciidocParser

# Register custom parser functions
CUSTOM_PARSER_FUNCTIONS: Dict[str, callable] = {
    "env": lambda source_code: EnvParser().parse(source_code),
    "plaintext": lambda source_code: PlaintextParser().parse(source_code),
    "yaml": lambda source_code: YamlParser().parse(source_code),
    "markdown": lambda source_code: MarkdownParser().parse(source_code),
    "editorconfig": lambda source_code: EditorconfigParser().parse(source_code),
    "graphql": lambda source_code: GraphqlParser().parse(source_code),
    "nim": lambda source_code: NimParser().parse(source_code),
    "ocaml": lambda source_code: OCamlmlParser().parse(source_code),
    "ocaml_interface": lambda source_code: OCamlmliParser().parse(source_code),
    "cobalt": lambda source_code: CobaltParser().parse(source_code),
    "xml": lambda source_code: XmlParser().parse(source_code),
    "html": lambda source_code: HtmlParser().parse(source_code),
    "ini": lambda source_code: IniParser().parse(source_code),
    "json": lambda source_code: JsonParser().parse(source_code),
    "restructuredtext": lambda source_code: RstParser().parse(source_code),
    "toml": lambda source_code: TomlParser().parse(source_code),
    "asciidoc": lambda source_code: AsciidocParser().parse(source_code),
    # Add additional custom parser registrations as needed.
}

# Export the parser functions
__all__ = [
    'CUSTOM_PARSER_FUNCTIONS',
    'EnvParser',
    'PlaintextParser',
    'YamlParser',
    'MarkdownParser',
    'EditorconfigParser',
    'GraphqlParser',
    'NimParser',
    'OCamlmlParser',
    'OCamlmliParser',
    'CobaltParser',
    'XmlParser',
    'HtmlParser',
    'IniParser',
    'JsonParser',
    'RstParser',
    'TomlParser',
    'AsciidocParser'
] 