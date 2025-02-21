# Useful commands for project structure

```zsh

tree -I 'tests|query_patterns|node-types'

index.py 
  -> unified_indexer.py (async)
    -> async_get_files() 
      -> FileProcessor.process_file() (async)
        -> get_file_classification()
        -> LanguageSupport.normalize_language_name()
        -> Custom Parser OR Tree-sitter Parser
          -> extract_ast_features_dual()
            -> db storage
