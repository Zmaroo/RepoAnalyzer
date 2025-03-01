#!/usr/bin/env python3
"""
RepoAnalyzer Health Monitoring Tool

This script provides a command-line interface to the health monitoring system,
allowing users to start monitoring, view health status, and generate reports.
"""

import os
import sys
import time
import argparse
import json
from datetime import datetime

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.health_monitor import (
    global_health_monitor,
    ComponentStatus,
    get_health_status
)
from utils.logger import log

def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="RepoAnalyzer Health Monitoring Tool")
    
    # Create subparsers for different commands
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Start monitoring command
    start_parser = subparsers.add_parser("start", help="Start health monitoring")
    start_parser.add_argument(
        "--interval", 
        type=int, 
        default=60,
        help="Check interval in seconds (default: 60)"
    )
    
    # Stop monitoring command
    subparsers.add_parser("stop", help="Stop health monitoring")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Show current health status")
    status_parser.add_argument(
        "--component", 
        type=str, 
        help="Show details for specific component"
    )
    status_parser.add_argument(
        "--watch", 
        action="store_true",
        help="Watch status updates continuously"
    )
    status_parser.add_argument(
        "--interval", 
        type=int, 
        default=5,
        help="Update interval for watch mode in seconds (default: 5)"
    )
    
    # Report command
    report_parser = subparsers.add_parser("report", help="Generate health report")
    report_parser.add_argument(
        "--output", 
        type=str, 
        help="Output file path (default: auto-generated filename)"
    )
    
    # Configure command
    config_parser = subparsers.add_parser("configure", help="Configure health monitoring")
    config_parser.add_argument(
        "--cpu-threshold", 
        type=float, 
        help="CPU usage alert threshold (percent)"
    )
    config_parser.add_argument(
        "--memory-threshold", 
        type=float, 
        help="Memory usage alert threshold (percent)"
    )
    config_parser.add_argument(
        "--disk-threshold", 
        type=float, 
        help="Disk usage alert threshold (percent)"
    )
    config_parser.add_argument(
        "--error-rate-threshold", 
        type=float, 
        help="Error rate alert threshold (0.0-1.0)"
    )
    config_parser.add_argument(
        "--response-time-threshold", 
        type=float, 
        help="Response time alert threshold (milliseconds)"
    )
    
    # List reports command
    subparsers.add_parser("list-reports", help="List saved health reports")
    
    # View report command
    view_parser = subparsers.add_parser("view-report", help="View a saved health report")
    view_parser.add_argument(
        "report_file", 
        type=str,
        help="Health report file to view"
    )
    
    return parser.parse_args()

def start_monitoring(args):
    """Start health monitoring."""
    print(f"Starting health monitoring with {args.interval}s interval...")
    global_health_monitor.start_monitoring(check_interval=args.interval)
    print("Health monitoring started. Use 'stop' command to stop monitoring.")

def stop_monitoring(args):
    """Stop health monitoring."""
    print("Stopping health monitoring...")
    global_health_monitor.stop_monitoring()
    print("Health monitoring stopped.")

def print_status_header():
    """Print status display header."""
    print("\n" + "=" * 80)
    print(f"REPOANALYZER HEALTH STATUS - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)

def format_status(status, component=None):
    """Format status for display.
    
    Args:
        status: Status dictionary
        component: Specific component to show details for
        
    Returns:
        str: Formatted status string
    """
    status_colors = {
        "healthy": "\033[92m",  # Green
        "degraded": "\033[93m",  # Yellow
        "unhealthy": "\033[91m",  # Red
        "unknown": "\033[90m",   # Gray
    }
    reset_color = "\033[0m"
    
    lines = []
    
    # Overall status
    status_color = status_colors.get(status["status"], "")
    lines.append(f"System Status: {status_color}{status['status'].upper()}{reset_color}")
    lines.append(f"Timestamp: {status['timestamp']}")
    
    # Resources
    lines.append("\nSystem Resources:")
    lines.append(f"  CPU Usage: {status['resources']['cpu_percent']:.1f}%")
    lines.append(f"  Memory Usage: {status['resources']['memory_percent']:.1f}%")
    lines.append(f"  Disk Usage: {status['resources']['disk_usage']:.1f}%")
    
    # Components
    if component and component in status["components"]:
        # Detailed view for a specific component
        comp_data = status["components"][component]
        comp_color = status_colors.get(comp_data["status"], "")
        
        lines.append(f"\nComponent Details: {component}")
        lines.append(f"  Status: {comp_color}{comp_data['status'].upper()}{reset_color}")
        lines.append(f"  Error Rate: {comp_data['error_rate']:.2%}")
        lines.append(f"  Response Time: {comp_data['response_time']:.2f}ms")
        
        # Get full component data from monitor
        report = global_health_monitor.check_health()
        if component in report.components:
            full_comp = report.components[component]
            lines.append(f"  Error Count: {full_comp.error_count}")
            lines.append(f"  Last Check: {full_comp.last_check.isoformat() if full_comp.last_check else 'Never'}")
            
            # Add details if available
            if full_comp.details:
                lines.append("\n  Details:")
                for key, value in full_comp.details.items():
                    lines.append(f"    {key}: {value}")
    else:
        # Summary view of all components
        lines.append("\nComponents:")
        for name, comp in status["components"].items():
            comp_color = status_colors.get(comp["status"], "")
            lines.append(f"  {name}: {comp_color}{comp['status'].upper()}{reset_color}")
            if comp["error_rate"] > 0:
                lines.append(f"    Error Rate: {comp['error_rate']:.2%}")
            if comp["response_time"] > 0:
                lines.append(f"    Response Time: {comp['response_time']:.2f}ms")
    
    return "\n".join(lines)

def show_status(args):
    """Show current health status."""
    if args.watch:
        try:
            while True:
                status = get_health_status()
                os.system('clear' if os.name == 'posix' else 'cls')
                print_status_header()
                print(format_status(status, args.component))
                print("\nPress Ctrl+C to exit...")
                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStatus watch stopped.")
    else:
        status = get_health_status()
        print_status_header()
        print(format_status(status, args.component))

def generate_report(args):
    """Generate a health report."""
    print("Generating health report...")
    report_path = global_health_monitor.save_health_report()
    
    if args.output:
        # Copy report to user-specified location
        import shutil
        shutil.copy(report_path, args.output)
        print(f"Report saved to: {args.output}")
    else:
        print(f"Report saved to: {report_path}")

def configure_monitoring(args):
    """Configure monitoring thresholds."""
    print("Configuring health monitoring...")
    
    if args.cpu_threshold is not None:
        global_health_monitor.set_alert_threshold("cpu_percent", args.cpu_threshold)
        print(f"CPU usage alert threshold set to {args.cpu_threshold}%")
        
    if args.memory_threshold is not None:
        global_health_monitor.set_alert_threshold("memory_percent", args.memory_threshold)
        print(f"Memory usage alert threshold set to {args.memory_threshold}%")
        
    if args.disk_threshold is not None:
        global_health_monitor.set_alert_threshold("disk_usage", args.disk_threshold)
        print(f"Disk usage alert threshold set to {args.disk_threshold}%")
        
    if args.error_rate_threshold is not None:
        global_health_monitor.set_alert_threshold("error_rate", args.error_rate_threshold)
        print(f"Error rate alert threshold set to {args.error_rate_threshold:.2%}")
        
    if args.response_time_threshold is not None:
        global_health_monitor.set_alert_threshold("response_time", args.response_time_threshold)
        print(f"Response time alert threshold set to {args.response_time_threshold}ms")
        
    print("Configuration updated.")

def list_reports(args):
    """List saved health reports."""
    report_dir = global_health_monitor._report_dir
    
    if not os.path.exists(report_dir):
        print("No reports directory found.")
        return
        
    reports = [f for f in os.listdir(report_dir) if f.startswith("health_report_") and f.endswith(".json")]
    
    if not reports:
        print("No health reports found.")
        return
        
    reports.sort(reverse=True)  # Most recent first
    
    print("\nAvailable Health Reports:")
    print("=" * 80)
    
    for i, report_file in enumerate(reports[:20], 1):  # Show up to 20 reports
        # Extract timestamp from filename
        try:
            timestamp_str = report_file.replace("health_report_", "").replace(".json", "")
            timestamp = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
            formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
            
            # Get report status if possible
            status = "Unknown"
            try:
                with open(os.path.join(report_dir, report_file), 'r') as f:
                    data = json.load(f)
                    status = data.get("system_status", "unknown").upper()
            except:
                pass
                
            print(f"{i:2}. {formatted_time} - {status} - {report_file}")
        except:
            print(f"{i:2}. {report_file}")
    
    if len(reports) > 20:
        print(f"\n... and {len(reports) - 20} more reports")
    
    print("\nUse 'view-report <filename>' to view a specific report.")

def view_report(args):
    """View a saved health report."""
    report_path = args.report_file
    
    # If just the filename is provided, look in the reports directory
    if not os.path.exists(report_path):
        report_dir = global_health_monitor._report_dir
        full_path = os.path.join(report_dir, report_path)
        if os.path.exists(full_path):
            report_path = full_path
        else:
            print(f"Report file not found: {report_path}")
            return
    
    try:
        with open(report_path, 'r') as f:
            report = json.load(f)
            
        # Extract the timestamp
        timestamp = datetime.fromisoformat(report["timestamp"])
        formatted_time = timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        print("\n" + "=" * 80)
        print(f"HEALTH REPORT - {formatted_time}")
        print("=" * 80)
        
        # System status
        status_colors = {
            "healthy": "\033[92m",  # Green
            "degraded": "\033[93m",  # Yellow
            "unhealthy": "\033[91m",  # Red
            "unknown": "\033[90m",   # Gray
        }
        reset_color = "\033[0m"
        
        status_color = status_colors.get(report["system_status"], "")
        print(f"System Status: {status_color}{report['system_status'].upper()}{reset_color}")
        
        # System resources
        resources = report["system_resources"]
        print("\nSystem Resources:")
        print(f"  CPU Usage: {resources['cpu_percent']:.1f}%")
        print(f"  Memory Usage: {resources['memory_percent']:.1f}%")
        print(f"  Disk Usage: {resources['disk_usage']:.1f}%")
        print(f"  Memory Used: {resources['memory_used'] / (1024 * 1024):.1f} MB")
        print(f"  Memory Available: {resources['memory_available'] / (1024 * 1024):.1f} MB")
        print(f"  Disk Free: {resources['disk_free'] / (1024 * 1024 * 1024):.1f} GB")
        print(f"  Open Files: {resources['open_files']}")
        print(f"  Open Connections: {resources['open_connections']}")
        print(f"  Thread Count: {resources['thread_count']}")
        
        # Components
        print("\nComponents:")
        for name, comp in report["components"].items():
            comp_color = status_colors.get(comp["status"], "")
            print(f"  {name}: {comp_color}{comp['status'].upper()}{reset_color}")
            print(f"    Error Rate: {comp['error_rate']:.2%}")
            print(f"    Error Count: {comp['error_count']}")
            print(f"    Response Time: {comp['response_time']:.2f}ms")
            if comp.get("last_check"):
                print(f"    Last Check: {comp['last_check']}")
                
            # Show details if available
            if comp.get("details") and comp["details"]:
                print(f"    Details:")
                for key, value in comp["details"].items():
                    print(f"      {key}: {value}")
        
        # Database health
        if report.get("database"):
            print("\nDatabases:")
            for name, db in report["database"].items():
                print(f"  {name}:")
                print(f"    Connection Pool Size: {db['connection_pool_size']}")
                print(f"    Active Connections: {db['active_connections']}")
                print(f"    Query Response Time: {db['query_response_time']:.2f}ms")
                print(f"    Slow Queries: {db['slow_queries']}")
                print(f"    Failed Queries: {db['failed_queries']}")
                print(f"    Retried Operations: {db['retried_operations']}")
                if db.get("last_successful_connection"):
                    print(f"    Last Successful Connection: {db['last_successful_connection']}")
        
        # Recent errors
        if report.get("recent_errors") and report["recent_errors"]:
            print("\nRecent Errors:")
            for i, error in enumerate(report["recent_errors"], 1):
                print(f"  {i}. Component: {error['component']}")
                print(f"     Time: {error['timestamp']}")
                print(f"     Error: {error['error']}")
                print(f"     Type: {error['error_type']}")
                if error.get("context"):
                    print(f"     Context: {error['context']}")
                print()
    
    except Exception as e:
        print(f"Error reading report: {str(e)}")

def main():
    """Main function."""
    args = parse_args()
    
    if not args.command:
        # No command specified, show help
        print("Error: Command is required")
        print("Use --help for usage information")
        return 1
    
    commands = {
        "start": start_monitoring,
        "stop": stop_monitoring,
        "status": show_status,
        "report": generate_report,
        "configure": configure_monitoring,
        "list-reports": list_reports,
        "view-report": view_report
    }
    
    if args.command in commands:
        commands[args.command](args)
        return 0
    else:
        print(f"Unknown command: {args.command}")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 