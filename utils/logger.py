"""Enhanced logging system with error handling."""

import logging
import sys
import os
from datetime import datetime
from typing import Optional, Dict, Any
from functools import wraps
import json
from utils.error_handling import (
    handle_errors,
    ProcessingError,
    ErrorBoundary
)

class EnhancedLogger:
    """Enhanced logging with structured output and error handling."""
    
    def __init__(self):
        self._initialize_logger()
        self.log_levels = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "warning": logging.WARNING,
            "error": logging.ERROR,
            "critical": logging.CRITICAL
        }
    
    @handle_errors(error_types=ProcessingError)
    def _initialize_logger(self):
        """Initialize logging configuration."""
        with ErrorBoundary("logger initialization"):
            # Create logs directory if it doesn't exist
            log_dir = "logs"
            if not os.path.exists(log_dir):
                os.makedirs(log_dir)
            
            # Set up file handler
            log_file = os.path.join(
                log_dir,
                f"app_{datetime.now().strftime('%Y%m%d')}.log"
            )
            
            # Configure logging
            logging.basicConfig(
                level=logging.INFO,
                format='%(asctime)s - %(levelname)s - %(message)s',
                handlers=[
                    logging.FileHandler(log_file),
                    logging.StreamHandler(sys.stdout)
                ]
            )
    
    @handle_errors(error_types=ProcessingError)
    def log(
        self,
        message: str,
        level: str = "info",
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Log a message with optional context.
        
        Args:
            message: The message to log
            level: The log level (debug, info, warning, error, critical)
            context: Optional dictionary of contextual information
        """
        with ErrorBoundary("logging operation"):
            log_level = self.log_levels.get(level.lower(), logging.INFO)
            
            # Create structured log entry
            log_entry = {
                "message": message,
                "timestamp": datetime.now().isoformat(),
                "level": level
            }
            
            if context:
                log_entry["context"] = context
            
            # Format as JSON for structured logging
            structured_message = json.dumps(log_entry)
            
            # Log using standard logging
            logging.log(log_level, structured_message)
    
    @handle_errors(error_types=ProcessingError)
    def debug(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log debug message."""
        self.log(message, "debug", context)
    
    @handle_errors(error_types=ProcessingError)
    def info(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log info message."""
        self.log(message, "info", context)
    
    @handle_errors(error_types=ProcessingError)
    def warning(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log warning message."""
        self.log(message, "warning", context)
    
    @handle_errors(error_types=ProcessingError)
    def error(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log error message."""
        self.log(message, "error", context)
    
    @handle_errors(error_types=ProcessingError)
    def critical(self, message: str, context: Optional[Dict[str, Any]] = None) -> None:
        """Log critical message."""
        self.log(message, "critical", context)

# Global logger instance
logger = EnhancedLogger()

# Convenience function
def log(message: str, level: str = "info", context: Optional[Dict[str, Any]] = None):
    """Global logging function."""
    logger.log(message, level, context)