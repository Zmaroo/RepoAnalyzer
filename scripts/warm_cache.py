#!/usr/bin/env python3
"""
RepoAnalyzer Cache Warming CLI Tool

This script provides a command-line interface to manage cache warming operations,
including running specific warming strategies, starting proactive warming, and
checking the status of warming operations.
"""

import os
import sys
import time
import json
import argparse
import asyncio
from typing import Dict, List, Any, Optional

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.logger import log
from utils.cache_warmer import cache_warmer
from utils.cache import cache_coordinator

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="RepoAnalyzer Cache Warming Tool")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # List warming strategies command
    subparsers.add_parser("list", help="List all available warming strategies")
    
    # Warm command
    warm_parser = subparsers.add_parser("warm", help="Execute a warming strategy")
    warm_parser.add_argument(
        "--cache", 
        type=str, 
        required=True,
        help="Cache to warm (e.g., 'patterns', 'repositories')"
    )
    warm_parser.add_argument(
        "--strategy", 
        type=str, 
        required=True,
        help="Warming strategy to use"
    )
    warm_parser.add_argument(
        "--limit", 
        type=int,
        help="Maximum number of items to warm"
    )
    warm_parser.add_argument(
        "--language", 
        type=str,
        help="Programming language for language-specific warming"
    )
    warm_parser.add_argument(
        "--complexity", 
        type=float,
        help="Minimum complexity threshold for complexity-based warming"
    )
    
    # Start proactive warming command
    start_parser = subparsers.add_parser("start", help="Start proactive background warming")
    start_parser.add_argument(
        "--interval", 
        type=int, 
        default=3600,
        help="Time between warming cycles in seconds (default: 3600)"
    )
    
    # Stop proactive warming command
    subparsers.add_parser("stop", help="Stop proactive background warming")
    
    # Status command
    subparsers.add_parser("status", help="Check the status of warming operations")
    
    return parser.parse_args()

async def list_strategies():
    """List all available warming strategies."""
    print("\nAvailable Cache Warming Strategies:")
    print("=" * 80)
    
    registry = cache_warmer._warmup_registry
    
    if not registry:
        print("No warming strategies registered.")
        return
    
    for cache_name in sorted(registry.keys()):
        print(f"\n{cache_name}:")
        
        strategies = registry[cache_name]
        for strategy_name, warmup_func in strategies.items():
            # Extract docstring for description
            description = warmup_func.__doc__.split('\n')[0].strip() if warmup_func.__doc__ else "No description"
            
            print(f"  - {strategy_name}: {description}")
            
            # Show parameters from docstring if available
            if warmup_func.__doc__ and "Args:" in warmup_func.__doc__:
                docstring = warmup_func.__doc__
                args_section = docstring.split("Args:")[1].split("Returns:")[0].strip()
                args_lines = [line.strip() for line in args_section.split('\n') if line.strip()]
                
                for arg_line in args_lines:
                    if ':' in arg_line:
                        arg_name, arg_desc = arg_line.split(':', 1)
                        print(f"      {arg_name.strip()}: {arg_desc.strip()}")
    
    print("\nUse 'warm --cache <cache> --strategy <strategy>' to execute a strategy")

async def warm_cache(args):
    """Execute a specific warming strategy.
    
    Args:
        args: Command-line arguments
    """
    # Prepare kwargs for the warming strategy
    kwargs = {}
    
    if args.limit is not None:
        kwargs["limit"] = args.limit
    
    if args.language is not None:
        kwargs["language"] = args.language
    
    if args.complexity is not None:
        kwargs["min_complexity"] = args.complexity
    
    print(f"\nExecuting warming strategy '{args.strategy}' for cache '{args.cache}'...")
    print(f"Parameters: {kwargs}")
    
    # Execute the warming strategy
    result = await cache_warmer.warm_cache(args.cache, args.strategy, **kwargs)
    
    if result:
        print(f"\nWarming strategy executed successfully.")
    else:
        print(f"\nFailed to execute warming strategy.")
        
        # Check if there's an error in the status
        status = cache_warmer._warm_status.get(args.cache, {}).get(args.strategy, {})
        if "error" in status:
            print(f"Error: {status['error']}")

async def start_proactive_warming(args):
    """Start proactive background warming.
    
    Args:
        args: Command-line arguments
    """
    print(f"\nStarting proactive cache warming (interval: {args.interval} seconds)...")
    
    await cache_warmer.start_proactive_warming(interval=args.interval)
    
    print("Proactive cache warming started.")
    print("This will run in the background. Use 'stop' to stop warming.")

async def stop_proactive_warming(args):
    """Stop proactive background warming.
    
    Args:
        args: Command-line arguments
    """
    print("\nStopping proactive cache warming...")
    
    await cache_warmer.stop_proactive_warming()
    
    print("Proactive cache warming stopped.")

async def check_status(args):
    """Check the status of warming operations.
    
    Args:
        args: Command-line arguments
    """
    print("\nCache Warming Status:")
    print("=" * 80)
    
    # Get warming status
    status = cache_warmer._warm_status
    
    if not status:
        print("No warming operations have been executed yet.")
        return
    
    # Check if proactive warming is running
    is_running = cache_warmer._is_running
    print(f"Proactive Warming: {'Running' if is_running else 'Stopped'}")
    
    # Show warming status for each cache
    for cache_name in sorted(status.keys()):
        print(f"\n{cache_name}:")
        
        cache_status = status[cache_name]
        for strategy_name, strategy_status in cache_status.items():
            # Format timestamp
            last_run = strategy_status.get("last_run", "Never")
            if "T" in last_run:  # ISO format
                last_run = last_run.replace("T", " ").split(".")[0]
            
            status_str = strategy_status.get("status", "Unknown")
            
            # Color-code status
            if status_str == "success":
                status_str = "\033[92mSuccess\033[0m"  # Green
            elif status_str == "failed":
                status_str = "\033[91mFailed\033[0m"  # Red
            elif status_str == "running":
                status_str = "\033[93mRunning\033[0m"  # Yellow
            
            print(f"  - {strategy_name}:")
            print(f"      Last Run: {last_run}")
            print(f"      Status: {status_str}")
            
            # Show error if any
            if "error" in strategy_status:
                print(f"      Error: {strategy_status['error']}")

async def main():
    """Main function."""
    args = parse_args()
    
    if not args.command:
        # No command specified, show help
        print("Error: Command is required")
        print("Use --help for usage information")
        return 1
    
    commands = {
        "list": list_strategies,
        "warm": lambda: warm_cache(args),
        "start": lambda: start_proactive_warming(args),
        "stop": lambda: stop_proactive_warming(args),
        "status": lambda: check_status(args)
    }
    
    if args.command in commands:
        await commands[args.command]()
        return 0
    else:
        print(f"Unknown command: {args.command}")
        return 1

if __name__ == "__main__":
    asyncio.run(main()) 