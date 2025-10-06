# startup.py - WebExtract Pro Complete System Startup (Fixed for webapp.py)
import subprocess
import time
import os
import sys
import threading
from pathlib import Path

def print_banner():
    """Print startup banner"""
    print("=" * 60)
    print("[START] WEBEXTRACT PRO - PROFESSIONAL WEB SCRAPING PLATFORM")
    print("=" * 60)
    print("[DASHBOARD] Main Dashboard: http://127.0.0.1:8000")
    print("[KILIMALL] Kilimall Worker (Selenium): http://127.0.0.1:5001")
    print("[JUMIA] Jumia Worker (HTTP): http://127.0.0.1:5000")
    print("[ADMIN] Admin Login: admin@webextract-pro.com / admin123")
    print("=" * 60)
    print()

def check_dependencies():
    """Check if required files exist"""
    required_files = [
        'shared_db.py',
        'webapp.py',
        'workers/kilimall/kilimall_worker.py',
        'workers/jumia/jumia_worker.py'
    ]
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        print("[ERROR] Missing required files:")
        for file in missing_files:
            print(f"   - {file}")
        print("\nPlease ensure all files are in the correct directories.")
        return False
    
    return True

def start_service(service_name, script_path, port, cwd=None):
    """Start a service in a separate process"""
    try:
        print(f"[START] Starting {service_name}...")

        # Use sys.executable to get the current Python interpreter
        # Don't capture stdout/stderr to prevent blocking - let output go to console
        process = subprocess.Popen(
            [sys.executable, script_path],
            cwd=cwd,
            stdout=None,  # Don't capture - prevents blocking
            stderr=None,  # Don't capture - prevents blocking
            universal_newlines=True
        )

        # Give service time to start
        time.sleep(2)

        # Check if process is still running
        if process.poll() is None:
            print(f"[SUCCESS] {service_name} started successfully on port {port}")
            return process
        else:
            print(f"[ERROR] {service_name} failed to start (exited immediately)")
            return None

    except Exception as e:
        print(f"[ERROR] Error starting {service_name}: {str(e)}")
        return None

def monitor_services(processes):
    """Monitor running services"""
    print("\n[MONITOR] Monitoring services... (Press Ctrl+C to stop all)")
    
    try:
        while True:
            time.sleep(10)
            
            # Check if any process has died
            for name, process in processes.items():
                if process and process.poll() is not None:
                    print(f"[WARNING] {name} has stopped unexpectedly")
                    
    except KeyboardInterrupt:
        print("\n[STOP] Stopping all services...")

        for name, process in processes.items():
            if process and process.poll() is None:
                print(f"[STOP] Stopping {name}...")
                process.terminate()

                # Wait for graceful shutdown
                try:
                    process.wait(timeout=5)
                    print(f"[SUCCESS] {name} stopped successfully")
                except subprocess.TimeoutExpired:
                    print(f"[WARNING] Force killing {name}...")
                    process.kill()

        print("[SUCCESS] All services stopped")

def main():
    """Main startup function"""
    print_banner()
    
    # Check if we're in the right directory
    if not Path('shared_db.py').exists():
        print("[ERROR] Please run this script from the WebExtract Pro root directory")
        print("   (where shared_db.py is located)")
        return
    
    # Check dependencies
    if not check_dependencies():
        return
    
    print("[CONFIG] Starting WebExtract Pro services...\n")
    
    # Store process references
    processes = {}
    
    # Start main webapp
    processes['WebApp (Dashboard)'] = start_service(
        "WebApp (Dashboard)",
        "webapp.py",
        8000
    )

    # Start Kilimall worker (Selenium-based)
    processes['Kilimall Worker'] = start_service(
        "Kilimall Worker",
        "kilimall_worker.py",
        5001,
        cwd="workers/kilimall"
    )

    # Start Jumia worker (HTTP-based)
    processes['Jumia Worker'] = start_service(
        "Jumia Worker",
        "jumia_worker.py",
        5000,
        cwd="workers/jumia"
    )
    
    # Check if all services started
    failed_services = [name for name, process in processes.items() if process is None]
    
    if failed_services:
        print(f"\n[ERROR] Failed to start: {', '.join(failed_services)}")
        print("Please check the error messages above and fix any issues.")
        
        # Stop any services that did start
        for name, process in processes.items():
            if process and process.poll() is None:
                process.terminate()
        return
    
    print("\n[SUCCESS] All services started successfully!")
    print("\n[ACCESS] Access WebExtract Pro:")
    print("   1. Open http://127.0.0.1:8000 in your browser")
    print("   2. Sign up or use admin@webextract-pro.com / admin123")
    print("   3. Click 'Open Scraper' to use the Jumia worker")
    print("   4. Start scraping and monitor progress in real-time!")
    
    # Monitor services
    monitor_services(processes)

if __name__ == '__main__':
    main()