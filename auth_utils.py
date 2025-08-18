"""Authentication utilities for Google Cloud service-to-service communication."""

import os
import logging
from typing import Optional
from config import config

logger = logging.getLogger(__name__)

def get_identity_token(target_audience: str) -> Optional[str]:
    """
    Get an identity token for service-to-service authentication in Google Cloud.
    
    Args:
        target_audience: The URL of the target service
        
    Returns:
        Identity token string or None if not in GCP environment
    """
    if not config.is_production:
        # In local development, no authentication needed
        return None
        
    try:
        # Preferred: use Google Auth library to fetch an ID token for Cloud Run audience
        from google.auth.transport.requests import Request
        from google.oauth2 import id_token

        req = Request()
        token = id_token.fetch_id_token(req, target_audience)
        if token:
            return token
    except Exception as e:
        logger.warning(f"fetch_id_token failed, falling back to metadata service: {e}")

    # Fallback: metadata identity endpoint (works on Cloud Run/Compute/GKE)
    try:
        import requests
        metadata_url = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/identity"
        params = {'audience': target_audience, 'format': 'full'}
        headers = {'Metadata-Flavor': 'Google'}
        response = requests.get(metadata_url, params=params, headers=headers, timeout=10)
        if response.status_code == 200:
            return response.text
        logger.warning(f"Metadata identity endpoint returned {response.status_code}")
    except Exception as e:
        logger.warning(f"Metadata identity token fetch failed: {e}")

    return None

def get_authenticated_headers(target_url: str) -> dict:
    """
    Get HTTP headers with authentication for service-to-service calls.
    
    Args:
        target_url: The URL of the target service
        
    Returns:
        Dictionary of HTTP headers
    """
    headers = {
        'Content-Type': 'application/json',
        'User-Agent': 'launch-the-nukes-client/1.0'
    }
    
    # Add authentication in production
    if config.is_production:
        token = get_identity_token(target_url)
        if token:
            headers['Authorization'] = f'Bearer {token}'
        else:
            logger.warning(f"No identity token available for {target_url}")
    
    return headers
