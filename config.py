"""Configuration module for the Launch the Nukes application.

Supports both local development and GCP production deployment.
"""

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class Config:
    """Base configuration class."""
    
    # Flask settings
    SECRET_KEY: str = os.environ.get('SECRET_KEY', 'launch-the-nukes-secret-key-2025-dev')
    DEBUG: bool = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Redis settings
    REDIS_URL: str = os.environ.get('REDIS_URL', 'redis://localhost:6379/0')
    
    # Job processing settings
    NUM_WORKERS: int = int(os.environ.get('NUM_WORKERS', '2'))
    JOB_TIMEOUT: int = int(os.environ.get('JOB_TIMEOUT', '300'))  # 5 minutes
    
    # MCP settings
    MCP_CACHE_DURATION: int = int(os.environ.get('MCP_CACHE_DURATION', '300'))  # 5 minutes
    
    # Server settings
    HOST: str = os.environ.get('HOST', '0.0.0.0')
    PORT: int = int(os.environ.get('PORT', '8080'))
    
    # LLM Provider settings
    OLLAMA_URL: str = os.environ.get('OLLAMA_URL', 'http://localhost:11434')
    OLLAMA_CLOUD_URL: Optional[str] = os.environ.get('OLLAMA_CLOUD_URL')  # Cloud Run Ollama service
    GEMINI_API_KEY: Optional[str] = os.environ.get('GEMINI_API_KEY')
    
    # Use cloud Ollama in production, local in development
    @property
    def effective_ollama_url(self) -> str:
        if self.is_production and self.OLLAMA_CLOUD_URL:
            return self.OLLAMA_CLOUD_URL
        return self.OLLAMA_URL
    
    # Google Cloud settings
    GOOGLE_CLOUD_PROJECT: Optional[str] = os.environ.get('GOOGLE_CLOUD_PROJECT', 'launch-the-nukes')
    CLOUD_RUN_SERVICE_URL: Optional[str] = os.environ.get('CLOUD_RUN_SERVICE_URL')
    
    @property
    def is_production(self) -> bool:
        """Check if running in production (GCP Cloud Run)."""
        return bool(self.GOOGLE_CLOUD_PROJECT and self.CLOUD_RUN_SERVICE_URL)
    
    @property
    def is_local_development(self) -> bool:
        """Check if running in local development mode."""
        return not self.is_production and self.DEBUG


@dataclass
class LocalConfig(Config):
    """Configuration for local development."""
    
    DEBUG: bool = True
    REDIS_URL: str = 'redis://localhost:6379/0'
    NUM_WORKERS: int = 2
    HOST: str = '127.0.0.1'
    PORT: int = 8080


@dataclass
class ProductionConfig(Config):
    """Configuration for GCP production deployment."""
    
    DEBUG: bool = False
    # Redis URL will be set to Cloud Memorystore instance
    NUM_WORKERS: int = 0  # Workers run as separate Cloud Run Jobs
    HOST: str = '0.0.0.0'
    PORT: int = int(os.environ.get('PORT', '8080'))
    
    def __post_init__(self):
        # Ensure we have required production settings
        if not self.GOOGLE_CLOUD_PROJECT:
            raise ValueError("GOOGLE_CLOUD_PROJECT must be set in production")
        
        # Set Redis URL for Cloud Memorystore if not explicitly provided
        if self.REDIS_URL == 'redis://localhost:6379/0':
            # This will be replaced with actual Cloud Memorystore instance
            redis_host = os.environ.get('REDIS_HOST', 'localhost')
            redis_port = os.environ.get('REDIS_PORT', '6379')
            self.REDIS_URL = f'redis://{redis_host}:{redis_port}/0'


def get_config() -> Config:
    """Get configuration based on environment."""
    if os.environ.get('GOOGLE_CLOUD_PROJECT'):
        return ProductionConfig()
    else:
        return LocalConfig()


# Global config instance
config = get_config()
