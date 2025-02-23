from typing import Dict, Type
from parsers.base_parser import BaseParser

from .custom_env_parser import EnvParser
from .custom_plaintext_parser import PlaintextParser
from .custom_yaml_parser import YamlParser
from .custom_markdown_parser import MarkdownParser
from .custom_editorconfig_parser import EditorconfigParser
from .custom_graphql_parser import GraphqlParser
from .custom_nim_parser import NimParser
from .custom_ocaml_parser import OcamlParser
from .custom_cobalt_parser import CobaltParser
from .custom_xml_parser import XmlParser
from .custom_html_parser import HtmlParser
from .custom_ini_parser import IniParser
from .custom_json_parser import JsonParser
from .custom_rst_parser import RstParser
from .custom_toml_parser import TomlParser
from .custom_asciidoc_parser import AsciidocParser

# Register custom parser classes
CUSTOM_PARSER_CLASSES: Dict[str, Type[BaseParser]] = {
    "env": EnvParser,
    "plaintext": PlaintextParser,
    "yaml": YamlParser,
    "markdown": MarkdownParser,
    "editorconfig": EditorconfigParser,
    "graphql": GraphqlParser,
    "nim": NimParser,
    "ocaml": OcamlParser,
    "ocaml_interface": OcamlParser,
    "cobalt": CobaltParser,
    "xml": XmlParser,
    "html": HtmlParser,
    "ini": IniParser,
    "json": JsonParser,
    "restructuredtext": RstParser,
    "toml": TomlParser,
    "asciidoc": AsciidocParser
}

# Export the parser classes
__all__ = [
    'CUSTOM_PARSER_CLASSES',
    'EnvParser',
    'PlaintextParser',
    'YamlParser',
    'MarkdownParser',
    'EditorconfigParser',
    'GraphqlParser',
    'NimParser',
    'OcamlParser',
    'CobaltParser',
    'XmlParser',
    'HtmlParser',
    'IniParser',
    'JsonParser',
    'RstParser',
    'TomlParser',
    'AsciidocParser'
] 