#!/usr/bin/env python3
"""
HTTP-enabled worker service for Cloud Run.
Runs worker processes while serving HTTP health checks.
"""

import asyncio
import logging
import os
import sys
import threading
import time
from flask import Flask, jsonify
from job_processor import JobManager, check_services
from config import config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Flask app for health checks
app = Flask(__name__)
job_manager = None
worker_stats = {"status": "starting", "workers": 0}

@app.route('/')
def health_check():
    """Health check endpoint for Cloud Run"""
    return jsonify({
        "status": "healthy",
        "service": "launch-the-nukes-worker",
        "worker_stats": worker_stats
    })

@app.route('/stats')
def get_stats():
    """Get worker and queue statistics"""
    try:
        if job_manager:
            queue_stats = job_manager.get_queue_stats()
            return jsonify({
                "worker_stats": worker_stats,
                "queue_stats": queue_stats
            })
        else:
            return jsonify({"error": "Job manager not initialized"}), 503
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/test-mcp')
def test_mcp():
    """Test MCP access for debugging"""
    try:
        from mcp_integration import MCPClient
        import os
        
        result = {
            "status": "testing",
            "working_directory": os.getcwd(),
            "mcp_servers_dir": os.path.join(os.getcwd(), "mcp_servers"),
            "mcp_servers_exists": os.path.exists(os.path.join(os.getcwd(), "mcp_servers")),
            "mcp_servers_files": [],
            "available_servers": {},
            "error": None
        }
        
        # Check if mcp_servers directory exists and list files
        mcp_dir = os.path.join(os.getcwd(), "mcp_servers")
        if os.path.exists(mcp_dir):
            result["mcp_servers_files"] = os.listdir(mcp_dir)
        
        # Test MCP client
        try:
            mcp_client = MCPClient()
            servers = mcp_client.get_available_servers()
            result["available_servers"] = dict(servers)
            result["status"] = "success" if servers else "no_servers"
        except Exception as e:
            result["error"] = str(e)
            result["status"] = "error"
            
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "status": "error", 
            "error": str(e)
        }), 500

def run_workers():
    """Run worker processes in background thread"""
    global job_manager, worker_stats
    
    try:
        # Check service health
        logger.info("🔍 Checking service health...")
        check_services()
        
        # Get configuration
        redis_url = os.getenv('REDIS_URL', config.REDIS_URL)
        num_workers = int(os.getenv('NUM_WORKERS', '2'))
        
        logger.info(f"🚀 Starting job worker with {num_workers} processes")
        logger.info(f"📡 Redis URL: {redis_url}")
        logger.info(f"🧠 Ollama URL: {config.effective_ollama_url}")
        logger.info(f"🏢 Production mode: {config.is_production}")
        
        # Create and start job manager
        job_manager = JobManager(redis_url, num_workers)
        job_manager.start_workers()
        
        worker_stats["status"] = "running"
        worker_stats["workers"] = num_workers
        
        last_stats_time = time.time()
        error_count = 0
        max_errors = 10
        
        # Main worker loop
        while True:
            try:
                # Check worker health and restart if needed
                dead_workers = job_manager.check_worker_health()
                if dead_workers:
                    logger.warning(f"💀 Dead workers detected: {dead_workers}")
                    restarted = job_manager.restart_dead_workers()
                    if restarted > 0:
                        logger.info(f"🔄 Restarted {restarted} dead workers")
                        worker_stats["restarts"] = worker_stats.get("restarts", 0) + restarted
                
                # Update worker stats
                alive_workers = len([w for w in job_manager.workers if w.is_alive()])
                worker_stats["workers"] = alive_workers
                worker_stats["status"] = "running" if alive_workers > 0 else "degraded"
                
                # Log stats periodically
                current_time = time.time()
                if current_time - last_stats_time >= 30:
                    try:
                        stats = job_manager.get_queue_stats()
                        logger.info(f"📊 Queue Stats - Pending: {stats['pending']}, Processing: {stats['processing']}, Total: {stats['total']}")
                        logger.info(f"⚙️ Worker Stats - Alive: {alive_workers}/{num_workers}, Status: {worker_stats['status']}")
                        
                        # Additional health information
                        if worker_stats.get("restarts", 0) > 0:
                            logger.info(f"🔄 Total restarts this session: {worker_stats['restarts']}")
                        
                        last_stats_time = current_time
                        error_count = 0  # Reset error count on successful stats logging
                    except Exception as e:
                        logger.error(f"❌ Error getting queue stats: {e}")
                        error_count += 1
                
                time.sleep(5)  # Check every 5 seconds
                
            except Exception as e:
                logger.error(f"❌ Error in worker loop: {e}")
                error_count += 1
                
                if error_count >= max_errors:
                    logger.error(f"💥 Too many consecutive errors ({error_count}), restarting worker manager...")
                    if job_manager:
                        job_manager.stop_workers()
                    # Try to restart everything
                    job_manager = JobManager(redis_url, num_workers)
                    job_manager.start_workers()
                    error_count = 0
                    worker_stats["major_restarts"] = worker_stats.get("major_restarts", 0) + 1
                
                sleep_time = min(error_count * 2, 60)  # Exponential backoff, max 60 seconds
                logger.info(f"⏳ Sleeping for {sleep_time}s before retry...")
                time.sleep(sleep_time)
                
    except Exception as e:
        logger.error(f"💥 Worker startup error: {e}")
        worker_stats["status"] = "error"
        worker_stats["error"] = str(e)
        if job_manager:
            job_manager.stop_workers()

def main():
    """Main function to start HTTP server and workers"""
    # Start workers in background thread
    worker_thread = threading.Thread(target=run_workers, daemon=True)
    worker_thread.start()
    
    # Start HTTP server
    port = int(os.getenv('PORT', '8080'))
    logger.info(f"Starting HTTP server on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)

if __name__ == '__main__':
    main()