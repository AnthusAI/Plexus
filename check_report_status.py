#!/usr/bin/env python3
"""
Quick diagnostic script to check the status of a hanging report process.
Run this while your report is hanging to get more information.
"""

import psutil
import time
import sys
from datetime import datetime

def check_python_processes():
    """Check for Python processes running report commands."""
    print(f"\n🔍 Checking Python processes at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 80)
    
    found_report_process = False
    for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'cpu_percent', 'memory_info']):
        try:
            # Check if it's a Python process
            if 'python' in proc.info['name'].lower():
                cmdline = ' '.join(proc.info.get('cmdline', []))
                
                # Check if it's running a report command
                if 'report' in cmdline and ('plexus' in cmdline or 'transform' in cmdline):
                    found_report_process = True
                    print(f"\n📊 Found Report Process:")
                    print(f"  PID: {proc.info['pid']}")
                    print(f"  Command: {cmdline[:100]}...")
                    print(f"  CPU: {proc.cpu_percent(interval=1)}%")
                    print(f"  Memory: {proc.info['memory_info'].rss / 1024 / 1024:.1f} MB")
                    
                    # Check process status
                    status = proc.status()
                    print(f"  Status: {status}")
                    
                    # Check if process is hung (low CPU for extended time)
                    if proc.cpu_percent(interval=2) < 1:
                        print("  ⚠️  WARNING: Process appears idle (very low CPU usage)")
                    
                    # Check open connections
                    try:
                        connections = proc.connections(kind='inet')
                        active_connections = [c for c in connections if c.status == 'ESTABLISHED']
                        print(f"  Active connections: {len(active_connections)}")
                        for conn in active_connections[:5]:  # Show first 5
                            print(f"    - {conn.raddr}")
                    except:
                        pass
                        
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    if not found_report_process:
        print("❌ No report processes found running")
    
    return found_report_process

def check_network_activity():
    """Check for network activity that might indicate API calls."""
    print("\n🌐 Network Activity Check:")
    print("-" * 40)
    
    # Get initial network stats
    net_io_start = psutil.net_io_counters()
    time.sleep(2)
    net_io_end = psutil.net_io_counters()
    
    bytes_sent = net_io_end.bytes_sent - net_io_start.bytes_sent
    bytes_recv = net_io_end.bytes_recv - net_io_start.bytes_recv
    
    print(f"  Data sent: {bytes_sent / 1024:.1f} KB/s")
    print(f"  Data received: {bytes_recv / 1024:.1f} KB/s")
    
    if bytes_sent < 100 and bytes_recv < 100:
        print("  ⚠️  WARNING: Very low network activity - might be stuck")

def main():
    """Main diagnostic function."""
    print("🩺 Plexus Report Process Diagnostic Tool")
    print("This will help diagnose hanging report processes")
    
    # Run diagnostics
    found = check_python_processes()
    if found:
        check_network_activity()
        
        print("\n💡 Suggestions:")
        print("1. If the process is idle with no network activity, it might be:")
        print("   - Stuck in a retry loop with exponential backoff")
        print("   - Waiting for a rate limit to clear")
        print("   - Experiencing a timeout")
        print("\n2. Check your logs for:")
        print("   - '⚠️ LLM call for transcript X is taking longer than 30 seconds'")
        print("   - '💓 HEARTBEAT' messages")
        print("   - Error messages about retries or timeouts")
        print("\n3. You can kill the process with: kill -9 <PID>")
    else:
        print("\n💡 No report process found. The process may have:")
        print("   - Already completed")
        print("   - Crashed (check logs)")
        print("   - Been killed")

if __name__ == "__main__":
    main() 