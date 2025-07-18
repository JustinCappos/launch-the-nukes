#!/usr/bin/env python3
"""
Standalone worker script for processing jobs in production.
Run separately from the web application.

Usage:
    python worker.py --workers 2 --redis-url redis://localhost:6379/0
"""

import argparse
import logging
import os
import sys
import signal
import time
from job_processor import JobManager, check_services

# Configure logging for systemd
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description='Job processing worker')
    parser.add_argument('--workers', type=int, default=1, help='Number of worker processes')
    parser.add_argument('--redis-url', default='redis://localhost:6379/0', help='Redis URL')
    parser.add_argument('--shutdown-timeout', type=int, default=30, help='Graceful shutdown timeout in seconds')
    
    args = parser.parse_args()
    
    logger.info(f"Starting job worker with {args.workers} processes")
    logger.info(f"Redis URL: {args.redis_url}")
    logger.info(f"Shutdown timeout: {args.shutdown_timeout}s")
    
    # Check service health before starting
    logger.info("Checking service health...")
    try:
        check_services()
    except Exception as e:
        logger.error(f"Service health check failed: {e}")
        sys.exit(1)
    
    # Create job manager
    job_manager = JobManager(args.redis_url, args.workers)
    shutdown_requested = False
    
    # Handle shutdown signals
    def signal_handler(signum, frame):
        nonlocal shutdown_requested
        if shutdown_requested:
            logger.warning("Force shutdown requested")
            job_manager.stop_workers()
            sys.exit(1)
        
        shutdown_requested = True
        logger.info(f"Received shutdown signal ({signum}), initiating graceful shutdown...")
        
        # Start graceful shutdown in background
        import threading
        def graceful_shutdown():
            job_manager.stop_workers()
            logger.info("Graceful shutdown completed")
            sys.exit(0)
        
        shutdown_thread = threading.Thread(target=graceful_shutdown)
        shutdown_thread.daemon = True
        shutdown_thread.start()
        
        # Wait for graceful shutdown or timeout
        shutdown_thread.join(timeout=args.shutdown_timeout)
        if shutdown_thread.is_alive():
            logger.warning(f"Graceful shutdown timed out after {args.shutdown_timeout}s, forcing exit")
            job_manager.stop_workers()
            sys.exit(1)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    try:
        # Start workers
        job_manager.start_workers()
        logger.info("Workers started successfully")
        
        # Keep main process alive and show stats
        last_stats_time = 0
        while not shutdown_requested:
            try:
                # Monitor worker health
                dead_workers = []
                for i, worker in enumerate(job_manager.workers):
                    if not worker.is_alive():
                        dead_workers.append(i)
                
                if dead_workers:
                    logger.warning(f"Dead workers detected: {dead_workers}")
                    # Could implement restart logic here in the future
                
                # Show stats every 30 seconds
                current_time = time.time()
                if current_time - last_stats_time >= 30:
                    try:
                        stats = job_manager.get_queue_stats()
                        logger.info(f"Queue Stats - Pending: {stats['pending']}, Processing: {stats['processing']}, Total: {stats['total']}")
                        last_stats_time = current_time
                    except Exception as e:
                        logger.error(f"Error getting queue stats: {e}")
                
                time.sleep(1)  # Check every second
                
            except KeyboardInterrupt:
                logger.info("Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(5)
    
    except Exception as e:
        logger.error(f"Worker startup error: {e}")
        job_manager.stop_workers()
        sys.exit(1)
    
    finally:
        if not shutdown_requested:
            logger.info("Shutting down workers...")
            job_manager.stop_workers()

if __name__ == '__main__':
    main()
