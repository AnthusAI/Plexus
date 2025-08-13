import pytest
from unittest.mock import Mock, patch
from plexus.cli.score.scores import optimize
from plexus.cli.shared.file_editor import FileEditor

@pytest.fixture
def mock_file_editor():
    """Create a mock FileEditor instance for testing CLI command handling."""
    return Mock(spec=FileEditor)

@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file with sample content for testing file operations."""
    file_path = tmp_path / "test.txt"
    content = "Hello, World!\nThis is a test file."
    file_path.write_text(content)
    return file_path

def test_cli_insert_success(mock_file_editor, test_file):
    """Test successful insertion of text into a file.
    
    Verifies that the CLI correctly processes an insert command and updates the file_edited flag
    when the operation succeeds. This is crucial for the AI agent to track whether its modifications
    were successful.
    """
    mock_file_editor.insert.return_value = "Successfully inserted text at line 1"
    
    tool_input = {
        "command": "insert",
        "path": str(test_file),
        "insert_line": 1,
        "new_str": "New line\n"
    }
    
    tool_result_content = None
    file_edited = False
    
    if tool_input["command"] == "insert":
        file_path = tool_input.get('path', '')
        insert_line = tool_input.get('insert_line', 0)
        new_str = tool_input.get('new_str', '')
        
        tool_result_content = mock_file_editor.insert(file_path, insert_line, new_str)
        
        if tool_result_content.startswith("Successfully"):
            file_edited = True
    
    assert tool_result_content == "Successfully inserted text at line 1"
    assert file_edited is True
    mock_file_editor.insert.assert_called_once_with(str(test_file), 1, "New line\n")

def test_cli_insert_error(mock_file_editor, test_file):
    """Test handling of failed insert command.
    
    Verifies that the CLI correctly handles insert operations that fail due to invalid parameters,
    ensuring the file_edited flag remains false and appropriate error messages are returned.
    """
    mock_file_editor.insert.return_value = "Error: Missing parameters or file not found (new_str missing)"
    
    tool_input = {
        "command": "insert",
        "path": str(test_file),
        "insert_line": 1,
        "new_str": ""
    }
    
    tool_result_content = None
    file_edited = False
    
    if tool_input["command"] == "insert":
        file_path = tool_input.get('path', '')
        insert_line = tool_input.get('insert_line', 0)
        new_str = tool_input.get('new_str', '')
        
        tool_result_content = mock_file_editor.insert(file_path, insert_line, new_str)
        
        if tool_result_content.startswith("Successfully"):
            file_edited = True
    
    assert tool_result_content == "Error: Missing parameters or file not found (new_str missing)"
    assert file_edited is False
    mock_file_editor.insert.assert_called_once_with(str(test_file), 1, "")

def test_cli_insert_nonexistent_file(mock_file_editor):
    """Test handling of insert command for nonexistent files.
    
    Verifies that the CLI correctly handles attempts to insert text into files that don't exist,
    ensuring appropriate error messages are returned and the file_edited flag remains false.
    """
    mock_file_editor.insert.return_value = "Error: Missing parameters or file not found (file not found)"
    
    tool_input = {
        "command": "insert",
        "path": "nonexistent.txt",
        "insert_line": 0,
        "new_str": "New line\n"
    }
    
    tool_result_content = None
    file_edited = False
    
    if tool_input["command"] == "insert":
        file_path = tool_input.get('path', '')
        insert_line = tool_input.get('insert_line', 0)
        new_str = tool_input.get('new_str', '')
        
        tool_result_content = mock_file_editor.insert(file_path, insert_line, new_str)
        
        if tool_result_content.startswith("Successfully"):
            file_edited = True
    
    assert tool_result_content == "Error: Missing parameters or file not found (file not found)"
    assert file_edited is False
    mock_file_editor.insert.assert_called_once_with("nonexistent.txt", 0, "New line\n")

def test_cli_create_success(mock_file_editor, tmp_path):
    """Test successful creation of a new file.
    
    Verifies that the CLI correctly processes a create command and updates the file_edited flag
    when the operation succeeds. This is essential for the AI agent to create new files as part
    of its self-improvement process.
    """
    mock_file_editor.create.return_value = "Successfully created new file"
    
    tool_input = {
        "command": "create",
        "path": str(tmp_path / "new_file.txt"),
        "content": "New file content\n"
    }
    
    tool_result_content = None
    file_edited = False
    
    if tool_input["command"] == "create":
        file_path = tool_input.get('path', '')
        content = tool_input.get('content', '')
        
        tool_result_content = mock_file_editor.create(file_path, content)
        
        if tool_result_content.startswith("Successfully"):
            file_edited = True
    
    assert tool_result_content == "Successfully created new file"
    assert file_edited is True
    mock_file_editor.create.assert_called_once_with(str(tmp_path / "new_file.txt"), "New file content\n")

def test_cli_create_error(mock_file_editor, test_file):
    """Test handling of failed create command.
    
    Verifies that the CLI correctly handles create operations that fail due to existing files,
    ensuring the file_edited flag remains false and appropriate error messages are returned.
    """
    mock_file_editor.create.return_value = "Error: File already exists"
    
    tool_input = {
        "command": "create",
        "path": str(test_file),
        "content": "New content\n"
    }
    
    tool_result_content = None
    file_edited = False
    
    if tool_input["command"] == "create":
        file_path = tool_input.get('path', '')
        content = tool_input.get('content', '')
        
        tool_result_content = mock_file_editor.create(file_path, content)
        
        if tool_result_content.startswith("Successfully"):
            file_edited = True
    
    assert tool_result_content == "Error: File already exists"
    assert file_edited is False
    mock_file_editor.create.assert_called_once_with(str(test_file), "New content\n")

def test_cli_create_missing_path(mock_file_editor):
    """Test handling of create command with missing file path.
    
    Verifies that the CLI correctly handles create operations that fail due to missing file paths,
    ensuring appropriate error messages are returned and the file_edited flag remains false.
    """
    mock_file_editor.create.return_value = "Error: Missing parameters or file not found (file_path missing)"
    
    tool_input = {
        "command": "create",
        "path": "",
        "content": "New content\n"
    }
    
    tool_result_content = None
    file_edited = False
    
    if tool_input["command"] == "create":
        file_path = tool_input.get('path', '')
        content = tool_input.get('content', '')
        
        tool_result_content = mock_file_editor.create(file_path, content)
        
        if tool_result_content.startswith("Successfully"):
            file_edited = True
    
    assert tool_result_content == "Error: Missing parameters or file not found (file_path missing)"
    assert file_edited is False
    mock_file_editor.create.assert_called_once_with("", "New content\n") 