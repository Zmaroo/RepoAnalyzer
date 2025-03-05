"""Health monitoring system for RepoAnalyzer.

This module provides comprehensive health monitoring for the RepoAnalyzer system,
including tracking system resources, component status, error rates, and 
performance metrics. It can alert on critical issues and provide diagnostic
information for troubleshooting.
"""

import os
import time
import threading
import json
import logging
import platform
import psutil
import asyncio
from typing import Dict, List, Any, Optional, Set, Callable, Union, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
import traceback
import gc
import socket
from enum import Enum

# Internal imports
from utils.logger import log

# Component status enum
class ComponentStatus(Enum):
    """Status enum for system components."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

@dataclass
class ComponentHealth:
    """Health information for a system component."""
    name: str
    status: ComponentStatus = ComponentStatus.UNKNOWN
    last_check: Optional[datetime] = None
    error_count: int = 0
    error_rate: float = 0.0
    response_time: float = 0.0  # in milliseconds
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['status'] = self.status.value
        result['last_check'] = self.last_check.isoformat() if self.last_check else None
        return result

@dataclass
class SystemResources:
    """System resource usage metrics."""
    cpu_percent: float = 0.0
    memory_percent: float = 0.0
    memory_used: int = 0  # in bytes
    memory_available: int = 0  # in bytes
    disk_usage: float = 0.0  # percent
    disk_free: int = 0  # in bytes
    open_files: int = 0
    open_connections: int = 0
    thread_count: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)

@dataclass
class DatabaseHealth:
    """Health metrics for database connections."""
    connection_pool_size: int = 0
    active_connections: int = 0
    query_response_time: float = 0.0  # in milliseconds
    slow_queries: int = 0
    failed_queries: int = 0
    retried_operations: int = 0
    last_successful_connection: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        result = asdict(self)
        result['last_successful_connection'] = (
            self.last_successful_connection.isoformat() 
            if self.last_successful_connection else None
        )
        return result

@dataclass
class HealthReport:
    """Comprehensive health report."""
    timestamp: datetime = field(default_factory=datetime.now)
    system_status: ComponentStatus = ComponentStatus.UNKNOWN
    components: Dict[str, ComponentHealth] = field(default_factory=dict)
    system_resources: SystemResources = field(default_factory=SystemResources)
    database: Dict[str, DatabaseHealth] = field(default_factory=dict)
    recent_errors: List[Dict[str, Any]] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "system_status": self.system_status.value,
            "components": {name: comp.to_dict() for name, comp in self.components.items()},
            "system_resources": self.system_resources.to_dict(),
            "database": {name: db.to_dict() for name, db in self.database.items()},
            "recent_errors": self.recent_errors
        }

class HealthMonitor:
    """Central health monitoring system."""
    
    def __init__(self):
        """Initialize the health monitor."""
        self._components: Dict[str, ComponentHealth] = {}
        self._resources = SystemResources()
        self._database_health: Dict[str, DatabaseHealth] = {}
        self._error_history: List[Dict[str, Any]] = []
        self._max_error_history = 100
        self._check_interval = 60  # Default check interval in seconds
        self._alert_thresholds = {
            "cpu_percent": 90.0,
            "memory_percent": 90.0,
            "disk_usage": 90.0,
            "error_rate": 0.1,  # 10% error rate
            "response_time": 1000.0,  # 1 second in ms
        }
        self._lock = threading.RLock()
        self._reporter_thread = None
        self._stop_event = threading.Event()
        self._report_dir = os.path.join("reports", "health")
        self._health_checks: Dict[str, Callable[[], ComponentStatus]] = {}
        self._recent_response_times: Dict[str, List[float]] = {}
        self._recent_errors: Dict[str, int] = {}
        self._recent_successes: Dict[str, int] = {}
        
        # Create report directory
        os.makedirs(self._report_dir, exist_ok=True)
        
    def register_component(self, name: str, health_check: Optional[Callable[[], ComponentStatus]] = None) -> None:
        """Register a component for health monitoring.
        
        Args:
            name: Component name
            health_check: Optional function that returns component status
        """
        with self._lock:
            self._components[name] = ComponentHealth(name=name)
            if health_check:
                self._health_checks[name] = health_check
            self._recent_response_times[name] = []
            self._recent_errors[name] = 0
            self._recent_successes[name] = 0
            
    def register_database(self, name: str) -> None:
        """Register a database for health monitoring.
        
        Args:
            name: Database name
        """
        with self._lock:
            self._database_health[name] = DatabaseHealth()
            
    def update_component_status(
        self, 
        name: str, 
        status: ComponentStatus,
        response_time: float = 0.0,
        error: bool = False,
        details: Optional[Dict[str, Any]] = None
    ) -> None:
        """Update status for a component.
        
        Args:
            name: Component name
            status: Component status
            response_time: Response time in milliseconds
            error: Whether this was an error
            details: Additional details about component status
        """
        with self._lock:
            if name not in self._components:
                self.register_component(name)
                
            component = self._components[name]
            component.status = status
            component.last_check = datetime.now()
            
            # Update response times (keep last 100)
            if response_time > 0:
                self._recent_response_times[name].append(response_time)
                if len(self._recent_response_times[name]) > 100:
                    self._recent_response_times[name].pop(0)
                
                # Calculate average response time
                component.response_time = sum(self._recent_response_times[name]) / len(self._recent_response_times[name])
                
            # Update error counts
            if error:
                self._recent_errors[name] += 1
                component.error_count += 1
            else:
                self._recent_successes[name] += 1
                
            # Calculate error rate
            total_ops = self._recent_errors[name] + self._recent_successes[name]
            if total_ops > 0:
                component.error_rate = self._recent_errors[name] / total_ops
                
            # Update details
            if details:
                component.details.update(details)
                
            # Check for alerts
            self._check_component_alerts(name, component)
            
    def update_database_health(
        self,
        name: str,
        connection_pool_size: Optional[int] = None,
        active_connections: Optional[int] = None,
        query_response_time: Optional[float] = None,
        slow_query: bool = False,
        failed_query: bool = False,
        retried_operation: bool = False
    ) -> None:
        """Update health metrics for a database.
        
        Args:
            name: Database name
            connection_pool_size: Size of connection pool
            active_connections: Number of active connections
            query_response_time: Response time in milliseconds
            slow_query: Whether this was a slow query
            failed_query: Whether this was a failed query
            retried_operation: Whether this was a retried operation
        """
        with self._lock:
            if name not in self._database_health:
                self.register_database(name)
                
            db_health = self._database_health[name]
            
            if connection_pool_size is not None:
                db_health.connection_pool_size = connection_pool_size
                
            if active_connections is not None:
                db_health.active_connections = active_connections
                
            if query_response_time is not None:
                # Simple moving average
                db_health.query_response_time = (
                    0.9 * db_health.query_response_time + 0.1 * query_response_time
                    if db_health.query_response_time > 0
                    else query_response_time
                )
                
            if slow_query:
                db_health.slow_queries += 1
                
            if failed_query:
                db_health.failed_queries += 1
                
            if retried_operation:
                db_health.retried_operations += 1
                
            # Update last successful connection timestamp
            if not failed_query and query_response_time is not None:
                db_health.last_successful_connection = datetime.now()
                
    def _update_system_resources(self) -> None:
        """Update system resource metrics."""
        try:
            # Get process info
            process = psutil.Process(os.getpid())
            
            # Update CPU usage
            self._resources.cpu_percent = psutil.cpu_percent(interval=0.1)
            
            # Update memory usage
            mem = psutil.virtual_memory()
            self._resources.memory_percent = mem.percent
            self._resources.memory_used = mem.used
            self._resources.memory_available = mem.available
            
            # Update disk usage
            disk = psutil.disk_usage('/')
            self._resources.disk_usage = disk.percent
            self._resources.disk_free = disk.free
            
            # Count open files
            try:
                self._resources.open_files = len(process.open_files())
            except (psutil.AccessDenied, psutil.Error):
                pass
                
            # Count open connections
            try:
                self._resources.open_connections = len(process.connections())
            except (psutil.AccessDenied, psutil.Error):
                pass
                
            # Count threads
            self._resources.thread_count = threading.active_count()
            
        except Exception as e:
            log(f"Error updating system resources: {str(e)}", level="error")
            
    def record_error(self, error: Exception, component: str, context: Dict[str, Any] = None) -> None:
        """Record an error for health monitoring.
        
        Args:
            error: The exception that occurred
            component: Component where the error occurred
            context: Additional context about the error
        """
        with self._lock:
            # Update component status
            self.update_component_status(
                component,
                ComponentStatus.DEGRADED,
                error=True,
                details={"last_error": str(error)}
            )
            
            # Add to error history
            timestamp = datetime.now()
            error_info = {
                "timestamp": timestamp.isoformat(),
                "component": component,
                "error": str(error),
                "error_type": error.__class__.__name__,
                "traceback": traceback.format_exc(),
                "context": context or {}
            }
            
            self._error_history.append(error_info)
            
            # Trim history if needed
            if len(self._error_history) > self._max_error_history:
                self._error_history = self._error_history[-self._max_error_history:]
                
    def _check_component_alerts(self, name: str, component: ComponentHealth) -> None:
        """Check if component metrics exceed alert thresholds.
        
        Args:
            name: Component name
            component: Component health data
        """
        alerts = []
        
        # Check error rate
        if component.error_rate > self._alert_thresholds["error_rate"]:
            alerts.append(f"High error rate: {component.error_rate:.2%}")
            
        # Check response time
        if component.response_time > self._alert_thresholds["response_time"]:
            alerts.append(f"Slow response time: {component.response_time:.2f}ms")
            
        # Log alerts
        if alerts:
            log(f"Health alert for {name}: {', '.join(alerts)}", level="warning")
            
    def _check_system_alerts(self) -> None:
        """Check if system metrics exceed alert thresholds."""
        alerts = []
        
        # Check CPU usage
        if self._resources.cpu_percent > self._alert_thresholds["cpu_percent"]:
            alerts.append(f"High CPU usage: {self._resources.cpu_percent:.1f}%")
            
        # Check memory usage
        if self._resources.memory_percent > self._alert_thresholds["memory_percent"]:
            alerts.append(f"High memory usage: {self._resources.memory_percent:.1f}%")
            
        # Check disk usage
        if self._resources.disk_usage > self._alert_thresholds["disk_usage"]:
            alerts.append(f"High disk usage: {self._resources.disk_usage:.1f}%")
            
        # Log alerts
        if alerts:
            log(f"System health alert: {', '.join(alerts)}", level="warning")
            
    def check_health(self) -> HealthReport:
        """Check health of all components and system resources.
        
        Returns:
            HealthReport: Current health report
        """
        with self._lock:
            # Update system resources
            self._update_system_resources()
            
            # Check system alerts
            self._check_system_alerts()
            
            # Run component health checks
            for name, check_func in self._health_checks.items():
                try:
                    start_time = time.time()
                    status = check_func()
                    elapsed = (time.time() - start_time) * 1000  # ms
                    
                    self.update_component_status(
                        name,
                        status,
                        response_time=elapsed
                    )
                except Exception as e:
                    self.record_error(e, name)
                    
            # Determine overall system status
            system_status = ComponentStatus.HEALTHY
            
            # If any component is unhealthy, the system is unhealthy
            for component in self._components.values():
                if component.status == ComponentStatus.UNHEALTHY:
                    system_status = ComponentStatus.UNHEALTHY
                    break
                elif component.status == ComponentStatus.DEGRADED and system_status != ComponentStatus.UNHEALTHY:
                    system_status = ComponentStatus.DEGRADED
                    
            # Create health report
            report = HealthReport(
                timestamp=datetime.now(),
                system_status=system_status,
                components=self._components.copy(),
                system_resources=self._resources,
                database=self._database_health.copy(),
                recent_errors=self._error_history[-10:] if self._error_history else []
            )
            
            return report
            
    def save_health_report(self, report: Optional[HealthReport] = None) -> str:
        """Save health report to disk.
        
        Args:
            report: Health report to save (if None, generates a new report)
            
        Returns:
            str: Path to saved report
        """
        if report is None:
            report = self.check_health()
            
        # Generate filename
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"health_report_{timestamp}.json"
        filepath = os.path.join(self._report_dir, filename)
        
        # Save report
        with open(filepath, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)
            
        log(f"Health report saved to {filepath}", level="info")
        return filepath
        
    def _reporter_loop(self) -> None:
        """Background thread to periodically check and report health."""
        log("Health monitor reporter thread started", level="info")
        
        while not self._stop_event.is_set():
            try:
                report = self.check_health()
                self.save_health_report(report)
            except Exception as e:
                log(f"Error in health reporter loop: {str(e)}", level="error")
                
            # Sleep until next check
            self._stop_event.wait(self._check_interval)
            
        log("Health monitor reporter thread stopped", level="info")
        
    def start_monitoring(self, check_interval: int = 60) -> None:
        """Start background health monitoring.
        
        Args:
            check_interval: Interval between health checks in seconds
        """
        with self._lock:
            if self._reporter_thread and self._reporter_thread.is_alive():
                log("Health monitoring already running", level="warning")
                return
                
            self._check_interval = check_interval
            self._stop_event.clear()
            self._reporter_thread = threading.Thread(
                target=self._reporter_loop,
                daemon=True,
                name="HealthMonitorReporter"
            )
            self._reporter_thread.start()
            
            log(f"Health monitoring started with {check_interval}s interval", level="info")
            
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        with self._lock:
            if not self._reporter_thread or not self._reporter_thread.is_alive():
                log("Health monitoring not running", level="warning")
                return
                
            self._stop_event.set()
            self._reporter_thread.join(timeout=5.0)
            
            if self._reporter_thread.is_alive():
                log("Health monitor reporter thread did not stop gracefully", level="warning")
            else:
                log("Health monitoring stopped", level="info")
                
    def set_alert_threshold(self, metric: str, threshold: float) -> None:
        """Set alert threshold for a metric.
        
        Args:
            metric: Metric name
            threshold: Alert threshold value
        """
        with self._lock:
            if metric in self._alert_thresholds:
                self._alert_thresholds[metric] = threshold
            else:
                log(f"Unknown alert metric: {metric}", level="warning")

    def cleanup(self):
        """Clean up health monitor resources."""
        try:
            self.stop_monitoring()
            # Save final health report
            self.save_health_report()
        except Exception as e:
            log(f"Error cleaning up health monitor: {e}", level="error")

# Context manager for monitoring operation health
@contextmanager
def monitor_operation(name: str, component: str, health_monitor: Optional['HealthMonitor'] = None):
    """Context manager to monitor an operation.
    
    This automatically records timing and errors to the health monitor.
    
    Args:
        name: Operation name
        component: Component name
        health_monitor: Health monitor instance (if None, uses global instance)
        
    Example:
        ```python
        with monitor_operation("parse_file", "parser"):
            # Do parsing operation
            result = parse_file(file_path)
        ```
    """
    # Use global instance if none provided
    monitor = health_monitor or global_health_monitor
    
    start_time = time.time()
    try:
        yield
        # Operation succeeded
        elapsed_ms = (time.time() - start_time) * 1000
        details = {"operation": name, "duration_ms": elapsed_ms}
        monitor.update_component_status(
            component,
            ComponentStatus.HEALTHY,
            response_time=elapsed_ms,
            error=False,
            details=details
        )
    except Exception as e:
        # Operation failed
        elapsed_ms = (time.time() - start_time) * 1000
        context = {
            "operation": name,
            "duration_ms": elapsed_ms
        }
        monitor.record_error(e, component, context=context)
        raise

# Function to monitor database operations
@contextmanager
def monitor_database(db_name: str, operation: str, health_monitor: Optional['HealthMonitor'] = None):
    """Context manager to monitor database operations.
    
    This automatically records timing and errors to the health monitor.
    
    Args:
        db_name: Database name
        operation: Operation name
        health_monitor: Health monitor instance (if None, uses global instance)
        
    Example:
        ```python
        with monitor_database("neo4j", "create_node"):
            # Execute database operation
            result = db.create_node(...)
        ```
    """
    # Use global instance if none provided
    monitor = health_monitor or global_health_monitor
    
    start_time = time.time()
    slow_threshold = 500  # ms
    
    try:
        yield
        # Operation succeeded
        elapsed_ms = (time.time() - start_time) * 1000
        slow_query = elapsed_ms > slow_threshold
        
        monitor.update_database_health(
            db_name,
            query_response_time=elapsed_ms,
            slow_query=slow_query
        )
        
        # Also update component status
        details = {"operation": operation, "duration_ms": elapsed_ms}
        monitor.update_component_status(
            f"db_{db_name}",
            ComponentStatus.HEALTHY,
            response_time=elapsed_ms,
            error=False,
            details=details
        )
        
    except Exception as e:
        # Operation failed
        elapsed_ms = (time.time() - start_time) * 1000
        
        monitor.update_database_health(
            db_name,
            query_response_time=elapsed_ms,
            failed_query=True
        )
        
        # Also record error
        context = {
            "database": db_name,
            "operation": operation,
            "duration_ms": elapsed_ms
        }
        monitor.record_error(e, f"db_{db_name}", context=context)
        raise

# Global health monitor instance
global_health_monitor = HealthMonitor()

# Initialize with common components
global_health_monitor.register_component("system")
global_health_monitor.register_component("parser")
global_health_monitor.register_component("indexer")
global_health_monitor.register_component("db_neo4j")
global_health_monitor.register_component("db_postgres")

# Register databases
global_health_monitor.register_database("neo4j")
global_health_monitor.register_database("postgres")

def get_health_status():
    """Get current health status as a dictionary.
    
    This is a simple API-friendly status report.
    
    Returns:
        dict: Health status summary
    """
    report = global_health_monitor.check_health()
    
    # Create a simplified status report
    status = {
        "status": report.system_status.value,
        "timestamp": report.timestamp.isoformat(),
        "components": {}
    }
    
    # Add component statuses
    for name, component in report.components.items():
        status["components"][name] = {
            "status": component.status.value,
            "error_rate": component.error_rate,
            "response_time": component.response_time
        }
    
    # Add system resources
    status["resources"] = {
        "cpu_percent": report.system_resources.cpu_percent,
        "memory_percent": report.system_resources.memory_percent,
        "disk_usage": report.system_resources.disk_usage
    }
    
    return status 