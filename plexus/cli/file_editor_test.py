import os
import pytest
from pathlib import Path
from plexus.cli.file_editor import FileEditor

@pytest.fixture
def file_editor():
    return FileEditor()

@pytest.fixture
def test_file(tmp_path):
    """Create a temporary test file with some content."""
    file_path = tmp_path / "test.txt"
    content = "Hello, World!\nThis is a test file.\n"  # Ensure trailing newline
    file_path.write_text(content)
    return file_path

def test_view_existing_file(file_editor, test_file):
    """Test viewing an existing file."""
    content = file_editor.view(str(test_file))
    assert content == "Hello, World!\nThis is a test file.\n"

def test_view_nonexistent_file(file_editor):
    """Test viewing a nonexistent file raises FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        file_editor.view("nonexistent.txt")

def test_str_replace_single_occurrence(file_editor, test_file):
    """Test replacing a single occurrence of text."""
    result = file_editor.str_replace(str(test_file), "Hello", "Greetings")
    assert result == "Successfully replaced text (1 occurrences)"
    
    # Verify the file contents were updated
    content = file_editor.view(str(test_file))
    assert content == "Greetings, World!\nThis is a test file.\n"

def test_str_replace_multiple_occurrences(file_editor, test_file):
    """Test replacing multiple occurrences of text."""
    # First add more occurrences
    with open(test_file, 'a') as f:
        f.write("Hello again!\n")
    
    result = file_editor.str_replace(str(test_file), "Hello", "Greetings")
    assert result == "Successfully replaced text (2 occurrences)"
    
    # Verify the file contents were updated
    content = file_editor.view(str(test_file))
    assert content == "Greetings, World!\nThis is a test file.\nGreetings again!\n"

def test_str_replace_no_matches(file_editor, test_file):
    """Test replacing text that doesn't exist in the file."""
    result = file_editor.str_replace(str(test_file), "Nonexistent", "New")
    assert result == "Error: No match found for replacement text"
    
    # Verify the file contents were not changed
    content = file_editor.view(str(test_file))
    assert content == "Hello, World!\nThis is a test file.\n"

def test_str_replace_nonexistent_file(file_editor):
    """Test replacing text in a nonexistent file."""
    result = file_editor.str_replace("nonexistent.txt", "Hello", "Greetings")
    assert result == "Error: Missing parameters or file not found (file not found)"

def test_str_replace_missing_parameters(file_editor, test_file):
    """Test replacing text with missing parameters."""
    result = file_editor.str_replace(str(test_file), "", "New")
    assert result == "Error: Missing parameters or file not found (old_str missing)"
    
    # Empty new_str is now allowed for text deletion
    result = file_editor.str_replace(str(test_file), "Hello", "")
    assert "Successfully replaced text" in result

def test_undo_edit_after_str_replace(file_editor, test_file):
    """Test undoing a str_replace operation."""
    # Make a change
    file_editor.str_replace(str(test_file), "Hello", "Greetings")
    
    # Verify the change
    content = file_editor.view(str(test_file))
    assert content == "Greetings, World!\nThis is a test file.\n"
    
    # Undo the change
    result = file_editor.undo_edit(str(test_file))
    assert result == "Successfully restored previous version"
    
    # Verify the file was restored
    content = file_editor.view(str(test_file))
    assert content == "Hello, World!\nThis is a test file.\n"

def test_undo_edit_no_previous_edit(file_editor, test_file):
    """Test undoing when there's no previous edit."""
    result = file_editor.undo_edit(str(test_file))
    assert result == "Error: No previous edit found to undo"

def test_undo_edit_nonexistent_file(file_editor):
    """Test undoing changes to a nonexistent file."""
    result = file_editor.undo_edit("nonexistent.txt")
    assert result == "Error: No previous edit found to undo"

def test_backup_directory_creation(file_editor, test_file):
    """Test that backup files are created in the same directory as the original file."""
    # Make a change to trigger backup creation
    file_editor.str_replace(str(test_file), "Hello", "Greetings")
    
    # Check that backup file exists in the same directory
    backup_files = list(test_file.parent.glob("test.txt.*.bak"))
    assert len(backup_files) > 0
    assert backup_files[0].exists()

def test_insert_at_beginning(file_editor, test_file):
    """Test inserting text at the beginning of the file."""
    result = file_editor.insert(str(test_file), 0, "New line at start\n")
    assert result == "Successfully inserted text at line 0"
    
    content = file_editor.view(str(test_file))
    assert content == "New line at start\nHello, World!\nThis is a test file.\n"

def test_insert_at_end(file_editor, test_file):
    """Test inserting text at the end of the file."""
    result = file_editor.insert(str(test_file), 2, "New line at end\n")
    assert result == "Successfully inserted text at line 2"
    
    content = file_editor.view(str(test_file))
    assert content == "Hello, World!\nThis is a test file.\nNew line at end\n"

def test_insert_in_middle(file_editor, test_file):
    """Test inserting text in the middle of the file."""
    result = file_editor.insert(str(test_file), 1, "New line in middle\n")
    assert result == "Successfully inserted text at line 1"
    
    content = file_editor.view(str(test_file))
    assert content == "Hello, World!\nNew line in middle\nThis is a test file.\n"

def test_insert_negative_line(file_editor, test_file):
    """Test inserting text with negative line number (should insert at start)."""
    result = file_editor.insert(str(test_file), -1, "New line at start\n")
    assert result == "Successfully inserted text at line 0"
    
    content = file_editor.view(str(test_file))
    assert content == "New line at start\nHello, World!\nThis is a test file.\n"

def test_insert_beyond_end(file_editor, test_file):
    """Test inserting text beyond the end of the file (should append)."""
    result = file_editor.insert(str(test_file), 999, "New line at end\n")
    assert result == "Successfully inserted text at line 2"
    
    content = file_editor.view(str(test_file))
    assert content == "Hello, World!\nThis is a test file.\nNew line at end\n"

def test_insert_nonexistent_file(file_editor):
    """Test inserting text into a nonexistent file."""
    result = file_editor.insert("nonexistent.txt", 0, "New line\n")
    assert result == "Error: Missing parameters or file not found (file not found)"

def test_insert_missing_text(file_editor, test_file):
    """Test inserting text with missing text parameter."""
    result = file_editor.insert(str(test_file), 0, "")
    assert result == "Error: Missing parameters or file not found (new_str missing)"

def test_undo_after_insert(file_editor, test_file):
    """Test undoing an insert operation."""
    # Make an insert
    file_editor.insert(str(test_file), 1, "New line\n")
    
    # Verify the change
    content = file_editor.view(str(test_file))
    assert content == "Hello, World!\nNew line\nThis is a test file.\n"
    
    # Undo the change
    result = file_editor.undo_edit(str(test_file))
    assert result == "Successfully restored previous version"
    
    # Verify the file was restored
    content = file_editor.view(str(test_file))
    assert content == "Hello, World!\nThis is a test file.\n"

def test_create_new_file(file_editor, tmp_path):
    """Test creating a new file with content."""
    file_path = tmp_path / "new_file.txt"
    file_text = "This is a new file\nWith some content\n"
    
    result = file_editor.create(str(file_path), file_text)
    
    assert result == "Successfully created new file"
    assert file_path.exists()
    assert file_path.read_text() == file_text

def test_create_empty_file(file_editor, tmp_path):
    """Test creating a new empty file."""
    file_path = tmp_path / "empty.txt"
    
    result = file_editor.create(str(file_path), "")
    
    assert result == "Successfully created new file"
    assert file_path.exists()
    assert file_path.read_text() == ""

def test_create_existing_file(file_editor, tmp_path):
    """Test creating a file that already exists."""
    file_path = tmp_path / "existing.txt"
    original_content = "Original content"
    file_path.write_text(original_content)
    
    result = file_editor.create(str(file_path), "New content")
    
    assert result == "Error: File already exists"
    assert file_path.read_text() == original_content

def test_create_with_special_chars(file_editor, tmp_path):
    """Test creating a file with special characters in the path."""
    file_path = tmp_path / "test@#$%^&.txt"
    file_text = "Test content with special chars\n"
    
    result = file_editor.create(str(file_path), file_text)
    
    assert result == "Successfully created new file"
    assert file_path.exists()
    assert file_path.read_text() == file_text

def test_create_with_long_content(file_editor, tmp_path):
    """Test creating a file with very long content."""
    file_path = tmp_path / "long_content.txt"
    # Create content with 1000 lines
    file_text = "Line " + "\nLine ".join(str(i) for i in range(1000)) + "\n"
    
    result = file_editor.create(str(file_path), file_text)
    
    assert result == "Successfully created new file"
    assert file_path.exists()
    assert file_path.read_text() == file_text

def test_create_in_nested_directory(file_editor, tmp_path):
    """Test creating a file in a nested directory."""
    nested_dir = tmp_path / "nested" / "dir" / "path"
    nested_dir.mkdir(parents=True)
    file_path = nested_dir / "test.txt"
    file_text = "Test content in nested directory\n"
    
    result = file_editor.create(str(file_path), file_text)
    
    assert result == "Successfully created new file"
    assert file_path.exists()
    assert file_path.read_text() == file_text

def test_create_with_unicode(file_editor, tmp_path):
    """Test creating a file with Unicode content."""
    file_path = tmp_path / "unicode.txt"
    file_text = "Hello 世界\nПривет мир\nمرحبا بالعالم\n"
    
    result = file_editor.create(str(file_path), file_text)
    
    assert result == "Successfully created new file"
    assert file_path.exists()
    assert file_path.read_text() == file_text 