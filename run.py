#!/usr/bin/env python3
"""
Main script to run the Barber Agent system.
This starts:
1. The ngrok tunnel for public access
2. The Flask application for SMS and Telegram webhooks
"""

import os
import sys
import subprocess
import threading
import time
import logging
import signal
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

# Global processes
processes = []

def run_ngrok():
    """Start the ngrok tunnel"""
    logger.info("Starting ngrok tunnel...")
    try:
        ngrok_process = subprocess.Popen([sys.executable, "ngrok_tunnel.py"], 
                                         stdout=subprocess.PIPE,
                                         stderr=subprocess.PIPE)
        processes.append(ngrok_process)
        logger.info("Ngrok tunnel started")
        
        # Give ngrok time to establish tunnel before starting Flask
        time.sleep(3)
        return True
    except Exception as e:
        logger.error(f"Error starting ngrok: {e}")
        return False

def run_flask_app():
    """Start the Flask application"""
    logger.info("Starting Flask application...")
    try:
        flask_process = subprocess.Popen([sys.executable, "app.py"], 
                                          stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE)
        processes.append(flask_process)
        logger.info("Flask application started")
        return True
    except Exception as e:
        logger.error(f"Error starting Flask application: {e}")
        return False

def monitor_process(process, name):
    """Monitor a subprocess and log its output"""
    while True:
        try:
            output = process.stdout.readline()
            if output:
                logger.info(f"[{name}] {output.decode().strip()}")
            if process.poll() is not None:
                logger.warning(f"Process {name} exited with code {process.returncode}")
                break
        except Exception as e:
            logger.error(f"Error monitoring {name}: {e}")
            break

def setup_process_monitoring():
    """Set up threads to monitor process output"""
    if len(processes) >= 1:
        ngrok_thread = threading.Thread(target=monitor_process, args=(processes[0], "ngrok"), daemon=True)
        ngrok_thread.start()
    
    if len(processes) >= 2:
        flask_thread = threading.Thread(target=monitor_process, args=(processes[1], "flask"), daemon=True)
        flask_thread.start()

def cleanup(sig=None, frame=None):
    """Clean up all processes on exit"""
    logger.info("Shutting down...")
    for process in processes:
        try:
            process.terminate()
            logger.info(f"Terminated process {process.pid}")
        except Exception as e:
            logger.error(f"Error terminating process: {e}")
    
    logger.info("All processes terminated")
    sys.exit(0)

def show_help():
    """Show help information"""
    print("""
Barber Agent - Appointment Scheduling System
--------------------------------------------

This script starts the complete Barber Agent system including:
- ngrok tunnel for public access
- Flask application for SMS and Telegram webhooks

Requirements:
- Python 3.8+
- ngrok account (get a free one at https://ngrok.com)
- Environment variables set in .env file

Options:
  --help, -h    Show this help message

Instructions:
1. Copy .env.example to .env and fill in your credentials
2. Run this script to start the system
3. Use the public URLs displayed to configure your SMS or Telegram webhooks
4. Send a message to your Twilio number or Telegram bot to test
    """)

def main():
    """Main function to run the system"""
    # Check for help flag
    if len(sys.argv) > 1 and sys.argv[1] in ['--help', '-h']:
        show_help()
        return
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, cleanup)
    signal.signal(signal.SIGTERM, cleanup)
    
    logger.info("Starting Barber Agent system...")
    
    # Start ngrok first to get the public URL
    if not run_ngrok():
        logger.error("Failed to start ngrok. Exiting.")
        cleanup()
        return
    
    # Then start Flask app
    if not run_flask_app():
        logger.error("Failed to start Flask application. Exiting.")
        cleanup()
        return
    
    # Set up monitoring for process output
    setup_process_monitoring()
    
    logger.info("All systems started. Press Ctrl+C to stop.")
    
    # Keep the main thread alive
    try:
        while True:
            time.sleep(1)
            
            # Check if any process has terminated unexpectedly
            for i, process in enumerate(processes):
                if process.poll() is not None:
                    name = "ngrok" if i == 0 else "flask"
                    logger.error(f"{name} process terminated unexpectedly with code {process.returncode}")
                    cleanup()
                    return
                    
    except KeyboardInterrupt:
        pass
    finally:
        cleanup()

if __name__ == "__main__":
    main() 