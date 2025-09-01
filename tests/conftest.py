"""
Pytest configuration and fixtures for launch-the-nukes tests.
"""

import pytest
import tempfile
import os
import shutil
from pathlib import Path
from yaml_mcp_server_factory import YAMLMCPServerFactory
from mcp_integration import MCPClient


@pytest.fixture
def temp_yaml_dir():
    """Create a temporary directory with test YAML files."""
    temp_dir = tempfile.mkdtemp()
    
    # Create test YAML files
    test_files = {
        "valid_server.yaml": """server: test-server
description: A test server
tools:
  - name: test_tool
    description: A test tool
    properties:
      - name: param1
        type: string
        description: A string parameter
      - name: param2
        type: number
        description: A number parameter
""",
        "invalid_server.yaml": """description: Missing server field
tools:
  - name: bad_tool
    description: Bad tool
    properties:
      - name: x
        type: string
        description: test
"""
    }
    
    for filename, content in test_files.items():
        with open(os.path.join(temp_dir, filename), 'w') as f:
            f.write(content.strip())
    
    yield temp_dir
    
    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def yaml_factory(temp_yaml_dir):
    """Create a YAML factory with test configurations."""
    return YAMLMCPServerFactory(temp_yaml_dir)


@pytest.fixture
def mcp_client(yaml_factory):
    """Create an MCP client with test configurations."""
    return MCPClient()


@pytest.fixture
def flask_app():
    """Create a Flask app for testing."""
    from app import app
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    return app


@pytest.fixture
def client(flask_app):
    """Create a test client for Flask app."""
    return flask_app.test_client()


@pytest.fixture
def runner(flask_app):
    """Create a test runner for Flask app."""
    return flask_app.test_cli_runner() 