from diagrams import Diagram, Edge
from diagrams.programming.language import Python
from diagrams.programming.framework import FastAPI
from diagrams.generic.device import Mobile

def generate_parser_flow():
    with Diagram("Parser Flow", show=True, direction="TB"):
        # Main components
        unified = Python("UnifiedParser\nparse_file()")
        lang_detect = Python("Language Detection\nget_language_by_ext()")
        parser_select = Python("Parser Selection\nget_parser()")
        
        # Parser paths
        tree_sitter = Python("Tree-sitter Parser")
        custom_parser = Python("Custom Parser")
        
        # Feature extraction
        tree_features = Python("Tree-sitter\nFeature Extraction")
        custom_features = Python("Custom\nFeature Extraction")
        
        # Pattern processing and result
        pattern_proc = Python("Pattern Processing")
        parser_result = Python("Parser Result")

        # Draw the flow
        unified >> lang_detect >> parser_select
        parser_select >> tree_sitter >> tree_features
        parser_select >> custom_parser >> custom_features
        tree_features >> pattern_proc
        custom_features >> pattern_proc
        pattern_proc >> parser_result

if __name__ == "__main__":
    generate_parser_flow() 