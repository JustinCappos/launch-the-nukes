import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, asdict
import multiprocessing
import signal
import sys

import redis

from llm_providers import OllamaProvider
from mcp_integration import MCPClient

class JobStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

@dataclass
class Job:
    job_id: str
    user_id: str
    username: str
    prompt: str
    status: JobStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    progress: int = 0
    progress_message: str = "Queued"
    queue_position: int = 0

    def to_dict(self):
        return {
            'job_id': self.job_id,
            'user_id': self.user_id,
            'username': self.username,
            'prompt': self.prompt,
            'status': self.status.value,
            'created_at': self.created_at.isoformat(),
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'result': self.result,
            'error': self.error,
            'progress': self.progress,
            'progress_message': self.progress_message,
            'queue_position': self.queue_position
        }

    @classmethod
    def from_dict(cls, data: dict):
        return cls(
            job_id=data['job_id'],
            user_id=data['user_id'],
            username=data['username'],
            prompt=data['prompt'],
            status=JobStatus(data['status']),
            created_at=datetime.fromisoformat(data['created_at']),
            started_at=datetime.fromisoformat(data['started_at']) if data['started_at'] else None,
            completed_at=datetime.fromisoformat(data['completed_at']) if data['completed_at'] else None,
            result=data.get('result'),
            error=data.get('error'),
            progress=data.get('progress', 0),
            progress_message=data.get('progress_message', 'Queued'),
            queue_position=data.get('queue_position', 0)
        )

class RedisJobQueue:
    """Redis-based job queue for multi-worker environments"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0"):
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.jobs_key = "jobs"
        self.queue_key = "job_queue"
        self.processing_key = "processing_jobs"
        
    def add_job(self, user_id: str, username: str, prompt: str) -> str:
        job_id = str(uuid.uuid4())
        job = Job(
            job_id=job_id,
            user_id=user_id,
            username=username,
            prompt=prompt,
            status=JobStatus.PENDING,
            created_at=datetime.now()
        )
        
        # Store job data
        self.redis_client.hset(self.jobs_key, job_id, json.dumps(job.to_dict()))
        
        # Add to queue
        self.redis_client.lpush(self.queue_key, job_id)
        
        # Update queue positions
        self._update_queue_positions()
        
        return job_id
    
    def get_job(self, job_id: str) -> Optional[Job]:
        job_data = self.redis_client.hget(self.jobs_key, job_id)
        if job_data:
            return Job.from_dict(json.loads(job_data))
        return None
    
    def update_job(self, job_id: str, **kwargs):
        job_data = self.redis_client.hget(self.jobs_key, job_id)
        if job_data:
            job_dict = json.loads(job_data)
            for key, value in kwargs.items():
                if key == 'status' and isinstance(value, JobStatus):
                    job_dict[key] = value.value
                elif key in ['started_at', 'completed_at'] and isinstance(value, datetime):
                    job_dict[key] = value.isoformat()
                else:
                    job_dict[key] = value
            
            self.redis_client.hset(self.jobs_key, job_id, json.dumps(job_dict))
    
    def get_next_job(self) -> Optional[str]:
        """Get next job from queue (blocking pop)"""
        result = self.redis_client.brpop(self.queue_key, timeout=1)
        if result:
            _, job_id = result
            # Move to processing set
            self.redis_client.sadd(self.processing_key, job_id)
            self._update_queue_positions()
            return job_id
        return None
    
    def complete_job(self, job_id: str):
        """Remove job from processing set when completed"""
        self.redis_client.srem(self.processing_key, job_id)
        self._update_queue_positions()
    
    def get_user_jobs(self, user_id: str) -> List[Job]:
        """Get all jobs for a specific user"""
        all_jobs = self.redis_client.hgetall(self.jobs_key)
        user_jobs = []
        
        for job_data in all_jobs.values():
            job = Job.from_dict(json.loads(job_data))
            if job.user_id == user_id:
                user_jobs.append(job)
        
        return sorted(user_jobs, key=lambda x: x.created_at, reverse=True)
    
    def _update_queue_positions(self):
        """Update queue positions for all pending jobs"""
        pending_jobs = self.redis_client.lrange(self.queue_key, 0, -1)
        
        for position, job_id in enumerate(reversed(pending_jobs), 1):
            job_data = self.redis_client.hget(self.jobs_key, job_id)
            if job_data:
                job_dict = json.loads(job_data)
                job_dict['queue_position'] = position
                self.redis_client.hset(self.jobs_key, job_id, json.dumps(job_dict))
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics"""
        pending_count = self.redis_client.llen(self.queue_key)
        processing_count = self.redis_client.scard(self.processing_key)
        total_jobs = self.redis_client.hlen(self.jobs_key)
        
        return {
            'pending': pending_count,
            'processing': processing_count,
            'total': total_jobs
        }
    
    def get_queue_position(self, job_id: str) -> int:
        """Get the position of a job in the queue (1-based index)"""
        try:
            pending_jobs = self.redis_client.lrange(self.queue_key, 0, -1)
            job_id_bytes = job_id.encode('utf-8')
            
            for i, pending_job_id in enumerate(pending_jobs):
                if pending_job_id == job_id_bytes:
                    return i + 1  # 1-based position
            
            # If not in pending queue, check if it's processing or completed
            job = self.get_job(job_id)
            if job and job.status in [JobStatus.PROCESSING, JobStatus.COMPLETED, JobStatus.FAILED]:
                return 0  # Not in queue anymore
                
            return -1  # Job not found
            
        except Exception as e:
            print(f"Error getting queue position for job {job_id}: {e}")
            return -1
    
    def get_estimated_time(self, job_id: str) -> int:
        """Get estimated time until job completion in seconds"""
        try:
            position = self.get_queue_position(job_id)
            if position <= 0:
                return 0  # Job not in queue or not found
            
            # Estimate 30 seconds per job ahead in queue
            return (position - 1) * 30
            
        except Exception as e:
            print(f"Error getting estimated time for job {job_id}: {e}")
            return 0

class LLMProcessor:
    """LLM processor that runs in a separate process"""
    
    def __init__(self):
        self.mcp_client = MCPClient()
    
    def _check_ollama_health(self) -> bool:
        """Check if Ollama is running and accessible"""
        try:
            import httpx
            client = httpx.Client(timeout=5.0)
            response = client.get("http://localhost:11434/api/tags")
            return response.status_code == 200
        except Exception:
            return False
    
    def process_prompt(self, job_id: str, prompt: str, job_queue) -> Dict[str, Any]:
        """Process a prompt with LLM and MCP integration"""
        try:
            # Update progress
            job_queue.update_job(job_id, progress=5, progress_message="Checking service health...")
            
            # Check if Ollama is running
            if not self._check_ollama_health():
                raise Exception("Ollama service is not running. Please start Ollama first.")
            
            job_queue.update_job(job_id, progress=10, progress_message="Initializing MCP clients...")
            
            # Get MCP tools with error handling
            try:
                tools_by_server = asyncio.run(self.mcp_client.list_tools())
            except Exception as e:
                print(f"Warning: MCP servers not available: {e}")
                tools_by_server = {}
            
            tool_to_server_map = {}
            
            job_queue.update_job(job_id, progress=20, progress_message="Preparing tools...")
            
            ollama_tools = []
            for server, tools in tools_by_server.items():
                for tool in tools:
                    tool_to_server_map[tool.name] = server
                    
                    ollama_tool = {
                        "type": "function",
                        "function": {
                            "name": tool.name,
                            "description": tool.description,
                        }
                    }
                    
                    if hasattr(tool, 'inputSchema') and tool.inputSchema:
                        ollama_tool["function"]["parameters"] = tool.inputSchema
                    
                    ollama_tools.append(ollama_tool)
            
            job_queue.update_job(job_id, progress=30, progress_message="Calling LLM...")
            
            # Prepare messages
            messages = [
                {
                    "role": "system", 
                    "content": "You are a security analysis assistant. Analyze user prompts and use available tools when appropriate for security operations. Be decisive about tool usage."
                },
                {
                    "role": "user", 
                    "content": prompt
                }
            ]
            
            # Call LLM
            llm = OllamaProvider(model="llama3.2")
            response = llm.generate_with_tools(messages, ollama_tools)
            
            # Check if we got a valid response or an error
            if "Error:" in response.get("content", ""):
                raise Exception(f"LLM Error: {response.get('content', 'Unknown error')}")
            
            job_queue.update_job(job_id, progress=50, progress_message="Processing tool calls...")
            
            # Process tool calls
            try:
                available_servers = self.mcp_client.get_available_servers()
            except Exception as e:
                print(f"Warning: Could not get available servers: {e}")
                available_servers = {}
            
            total_mcps = len(available_servers)
            used_servers = set()
            tool_call_results = []
            llm_message = response.get("content", "No response from LLM")
            
            tool_calls = response.get("tool_calls", [])
            
            if tool_calls:
                progress_step = 40 / len(tool_calls)
                current_progress = 50
                
                for i, tool_call in enumerate(tool_calls):
                    try:
                        job_queue.update_job(
                            job_id, 
                            progress=int(current_progress + (i * progress_step)), 
                            progress_message=f"Executing tool {i+1}/{len(tool_calls)}..."
                        )
                        
                        if "function" in tool_call:
                            function_info = tool_call["function"]
                            tool_name = function_info.get("name")
                            
                            args_raw = function_info.get("arguments", {})
                            if isinstance(args_raw, str):
                                args = json.loads(args_raw)
                            else:
                                args = args_raw
                            
                            if tool_name in tool_to_server_map:
                                server_name = tool_to_server_map[tool_name]
                                
                                # Type conversion logic
                                tool_schema = None
                                for server, tools in tools_by_server.items():
                                    if server == server_name:
                                        for tool in tools:
                                            if tool.name == tool_name:
                                                tool_schema = tool.inputSchema
                                                break
                                
                                if tool_schema and 'properties' in tool_schema:
                                    converted_args = {}
                                    for arg_name, arg_value in args.items():
                                        if arg_name in tool_schema['properties']:
                                            expected_type = tool_schema['properties'][arg_name].get('type', 'string')
                                            
                                            try:
                                                if expected_type == 'number' and isinstance(arg_value, str):
                                                    converted_args[arg_name] = float(arg_value)
                                                elif expected_type == 'integer' and isinstance(arg_value, str):
                                                    converted_args[arg_name] = int(arg_value)
                                                elif expected_type == 'boolean' and isinstance(arg_value, str):
                                                    converted_args[arg_name] = arg_value.lower() in ('true', '1', 'yes')
                                                else:
                                                    converted_args[arg_name] = arg_value
                                            except (ValueError, TypeError):
                                                converted_args[arg_name] = arg_value
                                        else:
                                            converted_args[arg_name] = arg_value
                                    args = converted_args
                                
                                used_servers.add(server_name)
                                try:
                                    result = asyncio.run(self.mcp_client.call_tool(server_name, tool_name, args))
                                    tool_call_results.append((tool_name, result))
                                except Exception as tool_error:
                                    error_msg = f"Tool execution failed: {str(tool_error)}"
                                    print(f"Error calling tool {tool_name}: {tool_error}")
                                    tool_call_results.append((tool_name, error_msg))
                            else:
                                print(f"Tool {tool_name} not found in server mapping")
                            
                    except Exception as e:
                        error_msg = f"Error processing tool call: {str(e)}"
                        print(f"Error in tool call processing: {e}")
                        tool_call_results.append((tool_call.get("function", {}).get("name", "unknown"), error_msg))
            
            job_queue.update_job(job_id, progress=90, progress_message="Finalizing results...")
            
            # Prepare final result
            used_servers = list(used_servers)
            num_servers_triggered = len(used_servers)
            risk_level = 'HIGH' if used_servers else 'SAFE'
            risk_color = 'red' if used_servers else 'green'
            
            result = {
                'prompt': prompt,
                'risk_level': risk_level,
                'risk_color': risk_color,
                'total_mcps': total_mcps,
                'used_servers': used_servers,
                'num_servers_triggered': num_servers_triggered,
                'llm_message': llm_message,
                'llm_content': response.get("content", ""),
                'llm_tool_calls': response.get("tool_calls", []),
                'tool_call_results': tool_call_results,
                'analysis': llm_message
            }
            
            job_queue.update_job(job_id, progress=100, progress_message="Completed")
            
            return result
            
        except Exception as e:
            raise Exception(f"Error processing prompt: {str(e)}")

def worker_process(redis_url: str, max_concurrent_jobs: int = 1):
    """Worker process that processes jobs from the queue"""
    print(f"Starting worker process (PID: {os.getpid()})")
    
    # Create job queue and processor
    job_queue = RedisJobQueue(redis_url)
    processor = LLMProcessor()
    
    # Handle shutdown signals
    def signal_handler(signum, frame):
        print(f"Worker {os.getpid()} received shutdown signal")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Process jobs
    while True:
        try:
            job_id = job_queue.get_next_job()
            if job_id:
                print(f"📋 Processing job {job_id}")
                job = job_queue.get_job(job_id)
                if not job:
                    continue
                
                try:
                    # Update job status
                    job_queue.update_job(
                        job_id,
                        status=JobStatus.PROCESSING,
                        started_at=datetime.now(),
                        progress=5,
                        progress_message="Starting processing..."
                    )
                    
                    # Process the job
                    result = processor.process_prompt(job_id, job.prompt, job_queue)
                    
                    # Update job with result
                    job_queue.update_job(
                        job_id,
                        status=JobStatus.COMPLETED,
                        completed_at=datetime.now(),
                        result=result,
                        progress=100,
                        progress_message="Completed successfully"
                    )
                    
                    print(f"✅ Job {job_id} completed successfully")
                    
                except Exception as e:
                    # Update job with error
                    job_queue.update_job(
                        job_id,
                        status=JobStatus.FAILED,
                        completed_at=datetime.now(),
                        error=str(e),
                        progress=0,
                        progress_message=f"Failed: {str(e)}"
                    )
                    
                    print(f"Job {job_id} failed: {e}")
                
                finally:
                    # Mark job as no longer processing
                    job_queue.complete_job(job_id)
            
        except Exception as e:
            print(f"Worker error: {e}")
            time.sleep(1)

class JobManager:
    """Main job manager that coordinates between web app and workers"""
    
    def __init__(self, redis_url: str = "redis://localhost:6379/0", num_workers: int = 1):
        self.redis_url = redis_url
        self.num_workers = num_workers
        self.workers = []
        
        # Create job queue
        self.job_queue = RedisJobQueue(redis_url)
    
    def start_workers(self):
        """Start worker processes"""
        print(f"Starting {self.num_workers} worker processes...")
        
        for i in range(self.num_workers):
            worker = multiprocessing.Process(
                target=worker_process,
                args=(self.redis_url, 1),
                name=f"JobWorker-{i}"
            )
            worker.start()
            self.workers.append(worker)
            print(f"✅ Started worker {i} (PID: {worker.pid})")
    
    def stop_workers(self):
        """Stop all worker processes"""
        print("Stopping worker processes...")
        
        for worker in self.workers:
            worker.terminate()
            worker.join(timeout=5)
            if worker.is_alive():
                worker.kill()
        
        self.workers = []
        print("✅ All workers stopped")
    
    def get_job_queue(self):
        """Get the job queue instance"""
        return self.job_queue
    
    def get_queue_stats(self):
        """Get queue statistics"""
        return self.job_queue.get_queue_stats()

# Global job manager instance
job_manager = None

def init_job_manager(redis_url: str = "redis://localhost:6379/0", num_workers: int = 1):
    """Initialize the global job manager"""
    global job_manager
    job_manager = JobManager(redis_url, num_workers)
    return job_manager

def get_job_queue():
    """Get the job queue from the global manager"""
    if job_manager:
        return job_manager.get_job_queue()
    else:
        # Fallback for development - requires Redis
        return RedisJobQueue()

# Health check functions
def check_services():
    """Check if required services are running"""
    print("🔍 Checking service health...")
    
    # Check Redis
    try:
        r = redis.Redis(host='localhost', port=6379, db=0)
        r.ping()
        print("✅ Redis is running")
    except Exception as e:
        print(f"❌ Redis not accessible: {e}")
        print("   Please start Redis with: redis-server")
    
    # Check Ollama
    try:
        import httpx
        client = httpx.Client(timeout=5.0)
        response = client.get("http://localhost:11434/api/tags")
        if response.status_code == 200:
            print("✅ Ollama service is running")
        else:
            print("⚠️  Ollama service responded with error")
    except Exception:
        print("Ollama service is not running")
        print("   Please start Ollama with: ollama serve")
    
    # Check MCP servers
    try:
        mcp_client = MCPClient()
        servers = mcp_client.get_available_servers()
        if servers:
            print(f"✅ MCP servers available: {list(servers.keys())}")
        else:
            print("⚠️  No MCP servers available")
    except Exception as e:
        print(f"MCP servers not accessible: {e}")

# Run health check when module is imported
if __name__ != "__main__":
    check_services()
