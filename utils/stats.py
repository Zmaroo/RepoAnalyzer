"""Base statistics class for core metrics tracking."""

from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class BaseStats:
    """Base class for core statistics tracking."""
    
    total_operations: int = 0
    successful_operations: int = 0
    failed_operations: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    errors: Dict[str, Exception] = field(default_factory=dict)
    operation_times: Dict[str, float] = field(default_factory=dict)
    memory_usage: float = 0.0  # in MB
    cache_hits: int = 0
    cache_misses: int = 0
    
    @property
    def duration(self) -> float:
        """Get operation duration in seconds."""
        if not self.start_time or not self.end_time:
            return 0.0
        return (self.end_time - self.start_time).total_seconds()
    
    @property
    def success_rate(self) -> float:
        """Get success rate as a percentage."""
        if self.total_operations == 0:
            return 0.0
        return (self.successful_operations / self.total_operations) * 100
    
    @property
    def error_rate(self) -> float:
        """Get error rate as a percentage."""
        if self.total_operations == 0:
            return 0.0
        return (self.failed_operations / self.total_operations) * 100
    
    @property
    def avg_operation_time(self) -> float:
        """Get average operation time in seconds."""
        if not self.operation_times:
            return 0.0
        return sum(self.operation_times.values()) / len(self.operation_times)
    
    @property
    def cache_hit_rate(self) -> float:
        """Get cache hit rate as a percentage."""
        total = self.cache_hits + self.cache_misses
        if total == 0:
            return 0.0
        return (self.cache_hits / total) * 100
    
    def record_operation_time(self, operation_type: str, duration: float) -> None:
        """Record operation duration."""
        if operation_type not in self.operation_times:
            self.operation_times[operation_type] = []
        self.operation_times[operation_type].append(duration)
    
    def record_error(self, operation_id: str, error: Exception) -> None:
        """Record an error."""
        self.errors[operation_id] = error
        self.failed_operations += 1
    
    def record_success(self) -> None:
        """Record a successful operation."""
        self.successful_operations += 1
    
    def record_memory_usage(self, memory_mb: float) -> None:
        """Record current memory usage in MB."""
        self.memory_usage = memory_mb
    
    def record_cache_hit(self) -> None:
        """Record a cache hit."""
        self.cache_hits += 1
    
    def record_cache_miss(self) -> None:
        """Record a cache miss."""
        self.cache_misses += 1
    
    def start_operation(self) -> None:
        """Start tracking operations."""
        if not self.start_time:
            self.start_time = datetime.now()
    
    def end_operation(self) -> None:
        """End tracking operations."""
        self.end_time = datetime.now()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert stats to dictionary for serialization."""
        return {
            "total_operations": self.total_operations,
            "successful_operations": self.successful_operations,
            "failed_operations": self.failed_operations,
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "errors": {k: str(v) for k, v in self.errors.items()},
            "duration": self.duration,
            "success_rate": self.success_rate,
            "error_rate": self.error_rate,
            "operation_times": self.operation_times,
            "avg_operation_time": self.avg_operation_time,
            "memory_usage": self.memory_usage,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "cache_hit_rate": self.cache_hit_rate
        } 