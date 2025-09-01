"""
Tests for YAML parsing functionality.
"""

import pytest
import os
from pathlib import Path
from parse_fake_mcp_server_yaml import parse_fake_MCP_YAML_file, parse_fake_MCP_YAML_directory


class TestYAMLParsing:
    """Test YAML parsing functionality."""
    
    def test_parse_valid_simple_yaml(self):
        """Test parsing a simple valid YAML file."""
        yaml_content = """
server: test-server
description: A test server
tools:
  - name: test_tool
    description: A test tool
    properties:
      - name: param1
        type: string
        description: A string parameter
"""
        
        with open("temp_test.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            result = parse_fake_MCP_YAML_file("temp_test.yaml")
            assert result["server"] == "test-server"
            assert result["description"] == "A test server"
            assert len(result["tools"]) == 1
            assert result["tools"][0]["name"] == "test_tool"
            assert len(result["tools"][0]["properties"]) == 1
        finally:
            os.remove("temp_test.yaml")
    
    def test_parse_valid_complex_yaml(self):
        """Test parsing a complex valid YAML file."""
        yaml_content = """
server: complex-server
description: A complex test server
tools:
  - name: tool1
    description: First tool
    properties:
      - name: str_param
        type: string
        description: String parameter
      - name: num_param
        type: number
        description: Number parameter
      - name: bool_param
        type: boolean
        description: Boolean parameter
  - name: tool2
    description: Second tool
    properties:
      - name: array_param
        type: array
        description: Array parameter
"""
        
        with open("temp_complex.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            result = parse_fake_MCP_YAML_file("temp_complex.yaml")
            assert result["server"] == "complex-server"
            assert len(result["tools"]) == 2
            assert result["tools"][0]["name"] == "tool1"
            assert result["tools"][1]["name"] == "tool2"
            assert len(result["tools"][0]["properties"]) == 3
            assert len(result["tools"][1]["properties"]) == 1
        finally:
            os.remove("temp_complex.yaml")
    
    def test_parse_missing_server_field(self):
        """Test that missing server field raises ValueError."""
        yaml_content = """
description: Missing server field
tools:
  - name: test_tool
    description: A test tool
    properties:
      - name: param1
        type: string
        description: A parameter
"""
        
        with open("temp_missing_server.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            with pytest.raises(ValueError):
                parse_fake_MCP_YAML_file("temp_missing_server.yaml")
        finally:
            os.remove("temp_missing_server.yaml")
    
    def test_parse_missing_description_field(self):
        """Test that missing description field raises ValueError."""
        yaml_content = """
server: test-server
tools:
  - name: test_tool
    description: A test tool
    properties:
      - name: param1
        type: string
        description: A parameter
"""
        
        with open("temp_missing_desc.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            with pytest.raises(ValueError):
                parse_fake_MCP_YAML_file("temp_missing_desc.yaml")
        finally:
            os.remove("temp_missing_desc.yaml")
    
    def test_parse_missing_tools_field(self):
        """Test that missing tools field raises ValueError."""
        yaml_content = """
server: test-server
description: A test server
"""
        
        with open("temp_missing_tools.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            with pytest.raises(ValueError):
                parse_fake_MCP_YAML_file("temp_missing_tools.yaml")
        finally:
            os.remove("temp_missing_tools.yaml")
    
    def test_parse_duplicate_tool_names(self):
        """Test that duplicate tool names raise ValueError."""
        yaml_content = """
server: test-server
description: A test server
tools:
  - name: same_tool
    description: First tool
    properties:
      - name: param1
        type: string
        description: A parameter
  - name: same_tool
    description: Second tool
    properties:
      - name: param2
        type: string
        description: Another parameter
"""
        
        with open("temp_duplicate_tools.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            with pytest.raises(ValueError, match="duplicate tool name"):
                parse_fake_MCP_YAML_file("temp_duplicate_tools.yaml")
        finally:
            os.remove("temp_duplicate_tools.yaml")
    
    def test_parse_duplicate_property_names(self):
        """Test that duplicate property names raise ValueError."""
        yaml_content = """
server: test-server
description: A test server
tools:
  - name: test_tool
    description: A test tool
    properties:
      - name: same_prop
        type: string
        description: First property
      - name: same_prop
        type: number
        description: Second property
"""
        
        with open("temp_duplicate_props.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            with pytest.raises(ValueError, match="duplicate property name"):
                parse_fake_MCP_YAML_file("temp_duplicate_props.yaml")
        finally:
            os.remove("temp_duplicate_props.yaml")
    
    def test_parse_invalid_property_type(self):
        """Test that invalid property types raise ValueError."""
        yaml_content = """
server: test-server
description: A test server
tools:
  - name: test_tool
    description: A test tool
    properties:
      - name: param1
        type: invalid_type
        description: Invalid type
"""
        
        with open("temp_invalid_type.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            with pytest.raises(ValueError, match="invalid type"):
                parse_fake_MCP_YAML_file("temp_invalid_type.yaml")
        finally:
            os.remove("temp_invalid_type.yaml")
    
    def test_parse_extra_fields(self):
        """Test that extra fields raise ValueError."""
        yaml_content = """
server: test-server
description: A test server
extra_field: should not be here
tools:
  - name: test_tool
    description: A test tool
    properties:
      - name: param1
        type: string
        description: A parameter
"""
        
        with open("temp_extra_fields.yaml", "w") as f:
            f.write(yaml_content.strip())
        
        try:
            with pytest.raises(ValueError, match="unexpected field"):
                parse_fake_MCP_YAML_file("temp_extra_fields.yaml")
        finally:
            os.remove("temp_extra_fields.yaml")
    
    def test_parse_directory(self):
        """Test parsing a directory of YAML files."""
        # Create a temporary directory with test files
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create valid YAML files
            files = {
                "server1.yaml": """server: server1
description: First server
tools:
  - name: tool1
    description: First tool
    properties:
      - name: param1
        type: string
        description: A parameter
""",
                "server2.yaml": """server: server2
description: Second server
tools:
  - name: tool2
    description: Second tool
    properties:
      - name: param2
        type: number
        description: Another parameter
"""
            }
            
            for filename, content in files.items():
                with open(os.path.join(temp_dir, filename), "w") as f:
                    f.write(content.strip())
            
            results = parse_fake_MCP_YAML_directory(temp_dir)
            assert len(results) == 2
            
            # Check that both servers are present (order doesn't matter)
            server_names = [result["server"] for result in results]
            assert "server1" in server_names
            assert "server2" in server_names
            
        finally:
            shutil.rmtree(temp_dir)
    
    def test_parse_large_directory(self):
        """Test parsing a directory with many YAML files (pass_dir3)."""
        yaml_dir = "tests/fake_mcp_server_yaml/pass_dir3"
        if os.path.exists(yaml_dir):
            results = parse_fake_MCP_YAML_directory(yaml_dir)
            
            # Should have multiple servers
            assert len(results) > 5
            
            # Check that each result has the required structure
            for result in results:
                assert "server" in result
                assert "description" in result
                assert "tools" in result
                assert isinstance(result["server"], str)
                assert isinstance(result["description"], str)
                assert isinstance(result["tools"], list)
                assert len(result["server"]) > 0
                assert len(result["description"]) > 0
                assert len(result["tools"]) > 0
                
                # Check that each tool has required structure
                for tool in result["tools"]:
                    assert "name" in tool
                    assert "description" in tool
                    assert "properties" in tool
                    assert isinstance(tool["name"], str)
                    assert isinstance(tool["description"], str)
                    assert isinstance(tool["properties"], list)
                    assert len(tool["name"]) > 0
                    assert len(tool["description"]) > 0
                    assert len(tool["properties"]) > 0
                    
                    # Check that each property has required structure
                    for prop in tool["properties"]:
                        assert "name" in prop
                        assert "type" in prop
                        assert "description" in prop
                        assert isinstance(prop["name"], str)
                        assert isinstance(prop["type"], str)
                        assert isinstance(prop["description"], str)
                        assert len(prop["name"]) > 0
                        assert len(prop["type"]) > 0
                        assert len(prop["description"]) > 0
    
    def test_parse_directory_with_duplicates(self):
        """Test that directory parsing fails with duplicate server names."""
        import tempfile
        import shutil
        
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Create files with duplicate server names
            files = {
                "server1.yaml": """
server: same_server
description: First server
tools:
  - name: tool1
    description: First tool
    properties:
      - name: param1
        type: string
        description: A parameter
""",
                "server2.yaml": """
server: same_server
description: Second server
tools:
  - name: tool2
    description: Second tool
    properties:
      - name: param2
        type: number
        description: Another parameter
"""
            }
            
            for filename, content in files.items():
                with open(os.path.join(temp_dir, filename), "w") as f:
                    f.write(content.strip())
            
            with pytest.raises(ValueError, match="Duplicate server name"):
                parse_fake_MCP_YAML_directory(temp_dir)
            
        finally:
            shutil.rmtree(temp_dir)


class TestExistingYAMLTests:
    """Test using the existing YAML test files."""
    
    def test_pass_simple_yaml(self):
        """Test the existing pass_simple.yaml file."""
        yaml_path = "tests/fake_mcp_server_yaml/pass_simple.yaml"
        if os.path.exists(yaml_path):
            result = parse_fake_MCP_YAML_file(yaml_path)
            assert result["server"] == "test-server-1"
            assert result["description"] == "A minimal working MCP server configuration."
            assert len(result["tools"]) == 1
            assert result["tools"][0]["name"] == "tool-one"
    
    def test_pass_complex_yaml(self):
        """Test the existing pass_complex.yaml file."""
        yaml_path = "tests/fake_mcp_server_yaml/pass_complex.yaml"
        if os.path.exists(yaml_path):
            result = parse_fake_MCP_YAML_file(yaml_path)
            assert result["server"] == "test-server-2"
            assert len(result["tools"]) == 2
            assert result["tools"][0]["name"] == "tool-a"
            assert result["tools"][1]["name"] == "tool-b"
    
    def test_fail_missing_server_yaml(self):
        """Test the existing fail_missing_server.yaml file."""
        yaml_path = "tests/fake_mcp_server_yaml/fail_missing_server.yaml"
        if os.path.exists(yaml_path):
            with pytest.raises(ValueError):
                parse_fake_MCP_YAML_file(yaml_path)
    
    def test_fail_duplicate_tool_name_yaml(self):
        """Test the existing fail_duplicate_tool_name.yaml file."""
        yaml_path = "tests/fake_mcp_server_yaml/fail_duplicate_tool_name.yaml"
        if os.path.exists(yaml_path):
            with pytest.raises(ValueError, match="duplicate tool name"):
                parse_fake_MCP_YAML_file(yaml_path)
    
    def test_fail_duplicate_property_yaml(self):
        """Test the existing fail_duplicate_property.yaml file."""
        yaml_path = "tests/fake_mcp_server_yaml/fail_duplicate_property.yaml"
        if os.path.exists(yaml_path):
            with pytest.raises(ValueError, match="duplicate property name"):
                parse_fake_MCP_YAML_file(yaml_path)
    
    def test_fail_invalid_property_type_yaml(self):
        """Test the existing fail_invalid_property_type.yaml file."""
        yaml_path = "tests/fake_mcp_server_yaml/fail_invalid_property_type.yaml"
        if os.path.exists(yaml_path):
            with pytest.raises(ValueError, match="invalid type"):
                parse_fake_MCP_YAML_file(yaml_path)
    
    def test_fail_extra_fields_yaml(self):
        """Test the existing fail_extra_fields.yaml file."""
        yaml_path = "tests/fake_mcp_server_yaml/fail_extra_fields.yaml"
        if os.path.exists(yaml_path):
            with pytest.raises(ValueError, match="unexpected field"):
                parse_fake_MCP_YAML_file(yaml_path)
    
    def test_fail_tools_not_list_yaml(self):
        """Test the existing fail_tools_not_list.yaml file."""
        yaml_path = "tests/fake_mcp_server_yaml/fail_tools_not_list.yaml"
        if os.path.exists(yaml_path):
            with pytest.raises(ValueError, match="must be a list"):
                parse_fake_MCP_YAML_file(yaml_path) 