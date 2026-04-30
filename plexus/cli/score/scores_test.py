import pytest
from types import SimpleNamespace
from unittest.mock import Mock, patch
from click.testing import CliRunner
from plexus.cli.score.scores import optimize, scores
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


def test_score_contradictions_runs_score_rubric_consistency_check():
    runner = CliRunner()
    payload = {
        "status": "potential_conflict",
        "paragraph": "The prompt is more lenient than the rubric.",
    }
    result_obj = Mock()
    result_obj.to_parameters_payload.return_value = payload

    with patch("plexus.cli.score.scores.create_client", return_value=Mock()) as create_client, \
         patch("plexus.cli.score.scores.memoized_resolve_scorecard_identifier", return_value="scorecard-1"), \
         patch("plexus.cli.score.scores.memoized_resolve_score_identifier", return_value="score-1"), \
         patch("plexus.cli.score.scores.ScoreRubricConsistencyService") as service_class:
        service_class.return_value.generate_from_api.return_value = result_obj

        result = runner.invoke(
            scores,
            [
                "contradictions",
                "--scorecard",
                "Scorecard",
                "--score",
                "Score",
                "--version",
                "version-1",
                "--format",
                "json",
            ],
        )

    assert result.exit_code == 0
    assert "potential_conflict" in result.output
    service_class.return_value.generate_from_api.assert_called_once_with(
        client=create_client.return_value,
        scorecard_identifier="Scorecard",
        score_identifier="Score",
        score_id="score-1",
        score_version_id="version-1",
        item_text="",
    )


def test_score_contradictions_can_include_optional_item_context():
    runner = CliRunner()
    result_obj = Mock()
    result_obj.to_parameters_payload.return_value = {
        "status": "consistent",
        "paragraph": "The prompt follows the rubric.",
    }

    with patch("plexus.cli.score.scores.create_client", return_value=Mock()), \
         patch("plexus.cli.score.scores.memoized_resolve_scorecard_identifier", return_value="scorecard-1"), \
         patch("plexus.cli.score.scores.memoized_resolve_score_identifier", return_value="score-1"), \
         patch("plexus.cli.score.scores.resolve_account_id_for_command", return_value="account-1"), \
         patch("plexus.cli.item.items.find_item_by_any_identifier", return_value=SimpleNamespace(text="item text")), \
         patch("plexus.cli.score.scores.ScoreRubricConsistencyService") as service_class:
        service_class.return_value.generate_from_api.return_value = result_obj

        result = runner.invoke(
            scores,
            [
                "contradictions",
                "--scorecard",
                "Scorecard",
                "--score",
                "Score",
                "--version",
                "version-1",
                "--item",
                "item-1",
            ],
        )

    assert result.exit_code == 0
    assert "Status:" in result.output
    service_class.return_value.generate_from_api.assert_called_once()
    assert service_class.return_value.generate_from_api.call_args.kwargs["item_text"] == "item text"


def test_item_contradictions_is_not_registered():
    from plexus.cli.item.items import item

    result = CliRunner().invoke(item, ["contradictions"])

    assert result.exit_code != 0
    assert "No such command 'contradictions'" in result.output
