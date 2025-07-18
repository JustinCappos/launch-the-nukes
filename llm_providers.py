import json
import logging
import os
import time
from abc import ABC, abstractmethod

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str) -> str:
        pass

    @abstractmethod
    def generate_response_sync(self, prompt: str) -> str:
        pass

    def generate_with_tools_streaming(self, messages: list, tools: list = None, progress_callback=None) -> dict:
        """Optional streaming method. Default implementation falls back to non-streaming."""
        # Default implementation - subclasses can override for streaming support
        return self.generate_with_tools(messages, tools) if hasattr(self, 'generate_with_tools') else {}

    @abstractmethod
    def close(self):
        pass

class OllamaProvider(LLMProvider):
    def __init__(self, model: str = "llama3.2", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url
        self.client = None
        self._init_client()

    def _init_client(self):
        try:
            import httpx
            self.client = httpx.Client(timeout=300.0)
        except ImportError:
            logger.warning("httpx not available. Ollama provider will use mock responses.")

    async def generate_response(self, prompt: str) -> str:
        if not self.client:
            return self._mock_response(prompt)
        try:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "num_predict": 2048,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return self._mock_response(prompt, error=str(e))

    def generate_response_sync(self, prompt: str) -> str:
        if not self.client:
            return self._mock_response(prompt)
        try:
            response = self.client.post(
                f"{self.base_url}/api/generate",
                json={
                    "model": self.model,
                    "prompt": prompt,
                    "stream": False,
                    "options": {
                        "temperature": 0.1,
                        "top_p": 0.9,
                        "num_predict": 2048,
                    },
                },
            )
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            logger.error(f"Error calling Ollama: {e}")
            return self._mock_response(prompt, error=str(e))

    def generate_with_tools(self, messages: list, tools: list = None) -> dict:
        """Generate response with tool calling support using Ollama's chat API."""
        if not self.client:
            return self._mock_tool_response(messages)
        
        try:
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 2048,
                },
            }
            
            # Add tools if provided (for models that support it)
            if tools:
                payload["tools"] = tools
            
            response = self.client.post(
                f"{self.base_url}/api/chat",
                json=payload
            )
            response.raise_for_status()
            result = response.json()
            
            return {
                "message": result.get("message", {}),
                "content": result.get("message", {}).get("content", ""),
                "tool_calls": result.get("message", {}).get("tool_calls", [])
            }
        except Exception as e:
            logger.error(f"Error calling Ollama with tools: {e}")
            return self._mock_tool_response(messages, error=str(e))

    def generate_with_tools_streaming(self, messages: list, tools: list = None, progress_callback=None) -> dict:
        """Generate response with tool calling support using Ollama's streaming API for real-time progress."""
        if not self.client:
            logger.warning("No HTTP client available - falling back to non-streaming")
            return self._mock_tool_response(messages)
        
        try:
            logger.info("Starting Ollama streaming API call...")
            
            payload = {
                "model": self.model,
                "messages": messages,
                "stream": True,  # Enable streaming
                "options": {
                    "temperature": 0.1,
                    "top_p": 0.9,
                    "num_predict": 2048,
                },
            }
            
            # Add tools if provided (for models that support it)
            if tools:
                payload["tools"] = tools
                logger.info(f"Added {len(tools)} tools to payload")
            
            response = self.client.post(
                f"{self.base_url}/api/chat",
                json=payload,
                headers={"Accept": "application/x-ndjson"}
            )
            
            response.raise_for_status()
            
            # Stream processing with throttled progress updates
            full_content = ""
            tool_calls = []
            token_count = 0
            max_tokens = 2048
            last_update_time = 0
            UPDATE_INTERVAL = 0.5  # Update every 0.5 seconds for responsive feedback
            
            # Progress range: 20% (LLM start) to 80% (LLM complete)
            PROGRESS_START = 20
            PROGRESS_END = 80
            
            # Initial progress update
            if progress_callback:
                progress_callback(PROGRESS_START, "Starting LLM response generation...")
            
            for line in response.iter_lines():
                if line:
                    try:
                        # Parse streaming response
                        data = json.loads(line)
                        
                        # Extract message content
                        if "message" in data:
                            message = data["message"]
                            
                            # Handle content chunks
                            if "content" in message and message["content"]:
                                content_chunk = message["content"]
                                full_content += content_chunk
                                
                                # Rough token estimation (word count approximation)
                                token_count += len(content_chunk.split())
                                
                                # Throttled progress updates
                                current_time = time.time()
                                if current_time - last_update_time > UPDATE_INTERVAL:
                                    # Calculate progress within the 20-80% range
                                    token_progress = min(token_count / max_tokens, 1.0)
                                    current_progress = PROGRESS_START + (PROGRESS_END - PROGRESS_START) * token_progress
                                    
                                    if progress_callback:
                                        progress_callback(
                                            int(current_progress), 
                                            f"Generating response... {token_count}/{max_tokens} tokens ({int(token_progress*100)}%)"
                                        )
                                    last_update_time = current_time
                            
                            # Extract tool calls if present
                            if "tool_calls" in message and message["tool_calls"]:
                                tool_calls.extend(message["tool_calls"])
                                
                                # For tool-only responses, show progress based on tool calls
                                if not full_content and tool_calls:
                                    current_time = time.time()
                                    if current_time - last_update_time > UPDATE_INTERVAL:
                                        # Progress for tool-only responses
                                        tool_progress = min(len(tool_calls) / 10, 1.0)  # Assume max 10 tools
                                        current_progress = PROGRESS_START + (PROGRESS_END - PROGRESS_START) * tool_progress
                                        
                                        if progress_callback:
                                            progress_callback(
                                                int(current_progress), 
                                                f"Processing tool calls... {len(tool_calls)} tools found"
                                            )
                                        last_update_time = current_time
                        
                        # Check if this is the final chunk
                        if data.get("done", False):
                            # Final progress update
                            if progress_callback:
                                if full_content:
                                    progress_callback(PROGRESS_END, f"Response complete - {token_count} tokens generated")
                                elif tool_calls:
                                    progress_callback(PROGRESS_END, f"Tool calls complete - {len(tool_calls)} tools selected")
                                else:
                                    progress_callback(PROGRESS_END, f"Response complete - no content generated")
                            
                            logger.info(f"Streaming complete - {token_count} tokens, {len(tool_calls)} tool calls")
                            break
                            
                    except json.JSONDecodeError:
                        continue
                    except Exception as e:
                        logger.warning(f"Error processing streaming chunk: {e}")
                        continue
            
            return {
                "message": {"content": full_content, "role": "assistant"},
                "content": full_content,
                "tool_calls": tool_calls
            }
            
        except Exception as e:
            logger.error(f"Streaming failed with error: {e}")
            logger.info("Falling back to non-streaming mode")
            return self.generate_with_tools(messages, tools)

    def _mock_response(self, prompt: str, error: str | None = None) -> str:
        content = (
            f"Error occurred: {error}"
            if error
            else "This is a mock response - httpx not available"
        )
        return json.dumps(
            {
                "original_prompt": prompt,
                "sub_prompts": [
                    {
                        "id": 1,
                        "content": content,
                        "opaque_values": {},
                        "suggested_tools": ["file-operations.read_file"],
                    }
                ],
            }
        )

    def _mock_tool_response(self, messages: list, error: str | None = None) -> dict:
        """Mock response for tool calling when client is unavailable."""
        content = (
            f"Mock response - Error: {error}" if error 
            else "Mock response - httpx not available"
        )
        return {
            "message": {"content": content, "role": "assistant"},
            "content": content,
            "tool_calls": []
        }

    def close(self):
        if self.client:
            self.client.close()

class GeminiProvider(LLMProvider):
    def __init__(self, model: str = "gemini-2.0-flash-exp", api_key: str | None = None):
        self.model = model
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        self.client = None
        self.GenerationConfig = None
        self._init_client()

    def _init_client(self):
        if not self.api_key:
            logger.warning("No Gemini API key provided. Provider will use mock responses.")
            return
        try:
            from google.generativeai.client import configure
            from google.generativeai.generative_models import GenerativeModel
            from google.generativeai.types import GenerationConfig
            configure(api_key=self.api_key)
            self.client = GenerativeModel(self.model)
            self.GenerationConfig = GenerationConfig
            logger.info(f"Initialized Gemini client with model: {self.model}")
        except ImportError:
            logger.warning("google-generativeai not available. Gemini provider will use mock responses.")
        except Exception as e:
            logger.error(f"Error initializing Gemini client: {e}")

    async def generate_response(self, prompt: str) -> str:
        if not self.client or not self.api_key or not self.GenerationConfig:
            return self._mock_response(prompt)
        try:
            config = self.GenerationConfig(
                temperature=0.1,
                top_p=0.9,
                max_output_tokens=2048,
            )
            response = self.client.generate_content(
                prompt,
                generation_config=config,
            )
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return self._mock_response(prompt, error=str(e))

    def generate_response_sync(self, prompt: str) -> str:
        if not self.client or not self.api_key or not self.GenerationConfig:
            return self._mock_response(prompt)
        try:
            config = self.GenerationConfig(
                temperature=0.1,
                top_p=0.9,
                max_output_tokens=2048,
            )
            response = self.client.generate_content(
                prompt,
                generation_config=config,
            )
            return response.text
        except Exception as e:
            logger.error(f"Error calling Gemini: {e}")
            return self._mock_response(prompt, error=str(e))

    def _mock_response(self, prompt: str, error: str | None = None) -> str:
        content = (
            f"Error occurred: {error}"
            if error
            else "This is a mock response - Gemini API not available"
        )
        return json.dumps(
            {
                "original_prompt": prompt,
                "sub_prompts": [
                    {
                        "id": 1,
                        "content": content,
                        "opaque_values": {},
                        "suggested_tools": ["file-operations.read_file"],
                    }
                ],
            }
        )

    def close(self):
        pass