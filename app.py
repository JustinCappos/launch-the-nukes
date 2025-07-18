from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, make_response
import os
import uuid
from datetime import datetime
from mcp_integration import MCPClient
from job_processor import get_job_queue, JobStatus
import time
import asyncio

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'launch-the-nukes-secret-key-2025-prod')

# Redis configuration
REDIS_URL = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')

# TODO: This would become unnecessary if we can read off of yaml files.
# Cache for MCP servers (5 minute cache)
_mcp_cache = {'servers': {}, 'last_update': 0}
MCP_CACHE_DURATION = 300  # 5 minutes

def get_cached_mcp_servers():
    """Get MCP servers with caching to avoid slow dashboard loads"""
    current_time = time.time()
    
    # Check if cache is still valid
    if current_time - _mcp_cache['last_update'] < MCP_CACHE_DURATION:
        return _mcp_cache['servers']
    
    # Cache expired, refresh it
    try:
        mcp_client = MCPClient()
        # Run the async method synchronously
        servers = asyncio.run(mcp_client.list_tools())
        _mcp_cache['servers'] = servers
        _mcp_cache['last_update'] = current_time
        return servers
    except Exception as e:
        print(f"Error loading MCP servers: {e}")
        # Return cached servers if available, otherwise empty dict
        return _mcp_cache['servers'] if _mcp_cache['servers'] else {}

def get_user_id():
    """Get or create anonymous user ID from cookie"""
    user_id = request.cookies.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())
    return user_id

def set_user_cookie(response, user_id):
    """Set user ID cookie with 30 day expiration (refresh on each visit)"""
    response.set_cookie('user_id', user_id, max_age=30*24*60*60, httponly=True, secure=False, samesite='Lax')

@app.route('/')
def index():
    return redirect(url_for('dashboard'))

@app.route('/dashboard')
def dashboard():
    user_id = get_user_id()
    
    # Get MCP servers with caching
    mcp_servers = get_cached_mcp_servers()
    
    response = make_response(render_template('dashboard.html', 
                                           username=f'User-{user_id[:8]}',
                                           mcp_servers=mcp_servers))
    set_user_cookie(response, user_id)
    return response

@app.route('/submit', methods=['POST'])
def submit():
    user_id = get_user_id()
    user_input = request.form.get('user_input', '').strip()
    
    if not user_input:
        flash('Please enter some text', 'error')
        return redirect(url_for('dashboard'))
    
    # Get job queue (connects to Redis directly)
    job_queue = get_job_queue()
    if not job_queue:
        flash('Job processing service unavailable', 'error')
        return redirect(url_for('dashboard'))
    
    job_id = job_queue.add_job(user_id, f'User-{user_id[:8]}', user_input)
    
    response = make_response(redirect(url_for('job_status', job_id=job_id)))
    set_user_cookie(response, user_id)
    return response

@app.route('/job/<job_id>')
def job_status(job_id):
    user_id = get_user_id()
    job_queue = get_job_queue()
    
    if not job_queue:
        flash('Job processing service unavailable', 'error')
        return redirect(url_for('dashboard'))
    
    job = job_queue.get_job(job_id)
    
    if not job:
        flash('Job not found', 'error')
        return redirect(url_for('dashboard'))
    
    response = make_response(render_template('job_status.html', 
                                           job=job, 
                                           job_id=job_id,
                                           username=f'User-{user_id[:8]}'))
    set_user_cookie(response, user_id)
    return response

@app.route('/api/job/<job_id>/status')
def api_job_status(job_id):
    job_queue = get_job_queue()
    
    if not job_queue:
        return jsonify({'error': 'Job processing service unavailable'}), 503
    
    job = job_queue.get_job(job_id)
    
    if not job:
        return jsonify({'error': 'Job not found'}), 404
    
    return jsonify({
        'id': job_id,
        'status': job.status.value,
        'progress': job.progress,
        'progress_message': job.progress_message,
        'result': job.result,
        'queue_position': job_queue.get_queue_position(job_id),
        'estimated_time': job_queue.get_estimated_time(job_id)
    })

@app.route('/api/mcp/servers')
def api_mcp_servers():
    """API endpoint to get MCP servers (uses cache)"""
    servers = get_cached_mcp_servers()
    return jsonify(servers)

@app.route('/api/queue/stats')
def api_queue_stats():
    job_queue = get_job_queue()
    
    if not job_queue:
        return jsonify({'error': 'Job processing service unavailable'}), 503
    
    stats = job_queue.get_queue_stats()
    return jsonify(stats)

@app.route('/results/<job_id>')
def results(job_id):
    user_id = get_user_id()
    job_queue = get_job_queue()
    job = job_queue.get_job(job_id)
    
    if not job or job.status != JobStatus.COMPLETED:
        flash('Job not found or not completed', 'error')
        return redirect(url_for('dashboard'))
    
    response = make_response(render_template('results.html', 
                                           **job.result, 
                                           username=f'User-{user_id[:8]}'))
    set_user_cookie(response, user_id)
    return response

@app.route('/my-jobs')
def my_jobs():
    user_id = get_user_id()
    job_queue = get_job_queue()
    user_jobs = job_queue.get_user_jobs(user_id)
    
    response = make_response(render_template('my_jobs.html', 
                                           jobs=user_jobs, 
                                           username=f'User-{user_id[:8]}'))
    set_user_cookie(response, user_id)
    return response

@app.route('/health')
def health_check():
    """Health check endpoint - doesn't require user tracking"""
    job_queue = get_job_queue()
    redis_status = "healthy" if job_queue else "unavailable"
    
    return jsonify({
        'status': 'healthy',
        'redis': redis_status,
        'timestamp': datetime.now().isoformat()
    })

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8080)
