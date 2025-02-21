# AI Tools Implementation

This directory contains the core implementation of AI-powered code analysis tools.

## Components

- Graph analysis capabilities (see `graph_capabilities.py`)
- **Unified AI Interface** (see `ai_interface.py`)
- Code structure analysis
- Semantic search implementation
- Pattern matching utilities

## Usage Example

For a simplified interface to perform comprehensive analysis, use the `AIAssistantInterface`:

'''python

from ai_tools.ai_interface import AIAssistantInterface
ai_assistant = AIAssistantInterface()
analysis = ai_assistant.analyze_repository(repo_id=1)
print(analysis)
ai_assistant.close()

## Configuration

- Set up database connections
- Configure language parsers
- Set analysis parameters
