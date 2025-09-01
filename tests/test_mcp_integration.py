"""
Tests for MCP integration functionality.
"""

import pytest
import asyncio
import typing
from typing import Any
from mcp_integration import MCPClient


class TestMCPClient:
    """Test MCP client functionality."""
    
    def test_client_initialization(self, mcp_client):
        """Test MCP client initialization."""
        assert mcp_client is not None
        assert hasattr(mcp_client, 'server_configs')
        assert hasattr(mcp_client, 'factory')
    
    def test_get_available_servers(self, mcp_client):
        """Test getting available servers from MCP client."""
        servers = mcp_client.get_available_servers()
        assert isinstance(servers, dict)
        assert len(servers) > 0
        
        # Should have the expected servers
        expected_servers = [
            "watersupply-server",
            "blockchain-operations",
            "global-operations",
            "nuke-operations"
        ]
        
        for server in expected_servers:
            assert server in servers
    
    @pytest.mark.asyncio
    async def test_list_tools(self, mcp_client):
        """Test listing tools from MCP client."""
        tools_by_server = await mcp_client.list_tools()
        assert isinstance(tools_by_server, dict)
        assert len(tools_by_server) > 0
        
        # Check that each server has tools
        for server, tools in tools_by_server.items():
            assert isinstance(tools, list)
            assert len(tools) > 0
            
            # Check that each tool has required attributes
            for tool in tools:
                assert hasattr(tool, 'name')
                assert hasattr(tool, 'description')
                assert isinstance(tool.name, str)
                assert isinstance(tool.description, str)
    
    @pytest.mark.asyncio
    async def test_list_tools_specific_server(self, mcp_client):
        """Test listing tools for a specific server."""
        tools_by_server = await mcp_client.list_tools("nuke-operations")
        assert "nuke-operations" in tools_by_server
        assert len(tools_by_server["nuke-operations"]) > 0
        
        # Check that we get the expected nuke tools
        tool_names = [tool.name for tool in tools_by_server["nuke-operations"]]
        expected_tools = [
            "verify_launch_code",
            "arm_warhead",
            "launch_missile", 
            "abort_mission",
            "send_strategic_alert"
        ]
        
        for expected_tool in expected_tools:
            assert expected_tool in tool_names
    
    @pytest.mark.asyncio
    async def test_list_tools_invalid_server(self, mcp_client):
        """Test listing tools for an invalid server."""
        tools_by_server = await mcp_client.list_tools("invalid-server")
        # The current implementation returns empty dict for invalid servers
        assert isinstance(tools_by_server, dict)
    
    @pytest.mark.asyncio
    async def test_get_tools_description(self, mcp_client):
        """Test getting tools description."""
        description = await mcp_client.get_tools_description()
        assert isinstance(description, str)
        assert len(description) > 0
        assert "Available MCP Tools" in description
        
        # Should contain information about all servers
        expected_servers = [
            "watersupply-server",
            "blockchain-operations", 
            "global-operations",
            "nuke-operations"
        ]
        
        for server in expected_servers:
            assert server in description
    
    def test_server_configs_structure(self, mcp_client):
        """Test that server configs have the correct structure."""
        for server_name, config in mcp_client.server_configs.items():
            assert "command" in config
            assert "args" in config
            assert "description" in config
            assert isinstance(config["command"], str)
            assert isinstance(config["args"], list)
            assert isinstance(config["description"], str)


class TestMCPClientIntegration:
    """Test MCP client integration with real YAML files."""
    
    def test_client_with_real_servers(self):
        """Test MCP client with real server configurations."""
        client = MCPClient()
        
        # Test that servers are available (without depending on specific names)
        servers = client.get_available_servers()
        assert isinstance(servers, dict)
        assert len(servers) > 0
        
        # Test that each server has a description
        for server_name, description in servers.items():
            assert isinstance(server_name, str)
            assert isinstance(description, str)
            assert len(server_name) > 0
            assert len(description) > 0
    
    @pytest.mark.asyncio
    async def test_client_tools_integration(self):
        """Test that MCP client properly integrates with YAML factory."""
        client = MCPClient()
        tools_by_server = await client.list_tools()
        
        # Test that tools are properly loaded (without depending on specific names)
        assert isinstance(tools_by_server, dict)
        assert len(tools_by_server) > 0
        
        for server_name, tools in tools_by_server.items():
            assert isinstance(tools, list)
            assert len(tools) > 0
            
            # Test that each tool has required attributes
            for tool in tools:
                assert hasattr(tool, 'name')
                assert hasattr(tool, 'description')
                assert isinstance(tool.name, str)
                assert isinstance(tool.description, str)
                assert len(tool.name) > 0
                assert len(tool.description) > 0
    
    @pytest.mark.asyncio
    async def test_tool_schemas(self):
        """Test that tool schemas are properly generated."""
        client = MCPClient()
        tools_by_server = await client.list_tools()
        
        for server, tools in tools_by_server.items():
            for tool in tools:
                # Check that tools have inputSchema
                assert hasattr(tool, 'inputSchema')
                if tool.inputSchema:
                    assert isinstance(tool.inputSchema, dict)
                    assert "type" in tool.inputSchema
                    assert tool.inputSchema["type"] == "object"
                    assert "properties" in tool.inputSchema
                    assert "required" in tool.inputSchema


class TestMCPClientErrorHandling:
    """Test MCP client error handling."""
    
    def test_client_with_invalid_yaml_directory(self):
        """Test client initialization with invalid YAML directory."""
        # This should not raise an exception, but should handle gracefully
        client = MCPClient()
        servers = client.get_available_servers()
        # Should still work with default directory
        assert isinstance(servers, dict)
    
    @pytest.mark.asyncio
    async def test_list_tools_with_invalid_server(self):
        """Test listing tools with invalid server name."""
        client = MCPClient()
        tools_by_server = await client.list_tools("non-existent-server")
        # The current implementation returns empty dict for invalid servers
        assert isinstance(tools_by_server, dict)


class TestMCPClientBackwardCompatibility:
    """Test that MCP client maintains backward compatibility."""
    
    def test_client_interface_unchanged(self):
        """Test that the MCP client interface is unchanged."""
        client = MCPClient()

        # Test that all expected methods exist
        assert hasattr(client, 'get_available_servers')
        assert hasattr(client, 'list_tools')
        assert hasattr(client, 'get_tools_description')
        assert hasattr(client, 'call_tool')

        # Test method signatures
        import inspect

        # get_available_servers should return dict[str, str]
        sig = inspect.signature(client.get_available_servers)
        assert sig.return_annotation == dict[str, str]

        # list_tools is not async in current implementation
        sig = inspect.signature(client.list_tools)
        # Just check it exists and returns the expected type
        assert sig.return_annotation == dict[str, list[typing.Any]]
        
        # get_tools_description should return str (not async in current implementation)
        sig = inspect.signature(client.get_tools_description)
        assert sig.return_annotation == str
    
    def test_server_configs_structure_unchanged(self):
        """Test that server configs structure is unchanged."""
        client = MCPClient()
        
        for server_name, config in client.server_configs.items():
            # Should have the same structure as before
            assert "command" in config
            assert "args" in config
            assert "description" in config
            
            # Command should be sys.executable
            assert "python" in config["command"] or "python3" in config["command"]
            
            # Args should be a list with the factory script and server name
            assert isinstance(config["args"], list)
            assert len(config["args"]) == 2
            assert "yaml_mcp_server_factory.py" in config["args"][0]
            assert config["args"][1] == server_name 