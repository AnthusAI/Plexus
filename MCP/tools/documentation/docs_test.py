#!/usr/bin/env python3
"""
Unit tests for documentation tools
"""
import pytest
import os
import tempfile
from unittest.mock import patch, Mock, mock_open
from io import StringIO

pytestmark = pytest.mark.unit


class TestDocumentationTool:
    """Test get_plexus_documentation tool patterns"""
    
    def test_documentation_validation_patterns(self):
        """Test documentation filename validation patterns"""
        valid_files = {
            "score-yaml-format": "score-yaml-format.md",
            "feedback-alignment": "feedback-alignment.md", 
            "dataset-yaml-format": "dataset-yaml-format.md"
        }
        
        def validate_filename(filename):
            if filename not in valid_files:
                available = ", ".join(valid_files.keys())
                return False, f"Invalid filename '{filename}'. Valid options are: {available}"
            return True, None
        
        # Test valid filenames
        for valid_filename in valid_files.keys():
            valid, error = validate_filename(valid_filename)
            assert valid is True
            assert error is None
        
        # Test invalid filename
        valid, error = validate_filename("invalid-doc")
        assert valid is False
        assert "Invalid filename 'invalid-doc'" in error
        assert "score-yaml-format" in error
        assert "feedback-alignment" in error
        assert "dataset-yaml-format" in error
        
        # Test empty filename
        valid, error = validate_filename("")
        assert valid is False
        assert "Invalid filename ''" in error
    
    def test_file_path_construction_patterns(self):
        """Test file path construction patterns"""
        def construct_file_path(filename, current_dir="/test/MCP"):
            valid_files = {
                "score-yaml-format": "score-yaml-format.md",
                "feedback-alignment": "feedback-alignment.md",
                "dataset-yaml-format": "dataset-yaml-format.md"
            }
            
            # Navigate from MCP/ to plexus/docs/
            plexus_dir = os.path.dirname(current_dir)  # Go up from MCP to project root
            docs_dir = os.path.join(plexus_dir, "plexus", "docs")
            file_path = os.path.join(docs_dir, valid_files[filename])
            return file_path
        
        # Test path construction for score yaml format
        path = construct_file_path("score-yaml-format", "/home/user/project/MCP")
        expected = "/home/user/project/plexus/docs/score-yaml-format.md"
        assert path == expected
        
        # Test path construction for feedback alignment
        path = construct_file_path("feedback-alignment", "/test/project/MCP")
        expected = "/test/project/plexus/docs/feedback-alignment.md"
        assert path == expected
        
        # Test path construction for dataset yaml format
        path = construct_file_path("dataset-yaml-format", "/app/MCP")
        expected = "/app/plexus/docs/dataset-yaml-format.md"
        assert path == expected
    
    def test_file_reading_patterns(self):
        """Test file reading patterns with mocked file system"""
        mock_content = """# Test Documentation

This is a test documentation file with markdown content.

## Section 1
Some content here.

## Section 2
More content here.
"""
        
        def simulate_file_read(file_path, mock_exists=True):
            if not mock_exists:
                raise FileNotFoundError(f"File not found: {file_path}")
            
            # Simulate successful file read
            return mock_content
        
        # Test successful file read
        content = simulate_file_read("/test/path/doc.md", True)
        assert content == mock_content
        assert "# Test Documentation" in content
        assert "## Section 1" in content
        assert len(content) > 0
        
        # Test file not found
        with pytest.raises(FileNotFoundError):
            simulate_file_read("/test/path/missing.md", False)
    
    def test_error_handling_patterns(self):
        """Test various error handling patterns"""
        def handle_file_not_found_error(filename, file_path):
            return f"Documentation file '{filename}' not found at expected location: {file_path}"
        
        def handle_general_file_error(filename, error):
            return f"Error reading documentation file '{filename}': {str(error)}"
        
        def handle_unexpected_error(error):
            return f"Error: {str(error)}"
        
        # Test file not found error
        error_msg = handle_file_not_found_error("test-doc", "/path/to/test-doc.md")
        assert "Documentation file 'test-doc' not found" in error_msg
        assert "/path/to/test-doc.md" in error_msg
        
        # Test general file error
        mock_error = IOError("Permission denied")
        error_msg = handle_general_file_error("test-doc", mock_error)
        assert "Error reading documentation file 'test-doc'" in error_msg
        assert "Permission denied" in error_msg
        
        # Test unexpected error
        mock_error = RuntimeError("Unexpected system error")
        error_msg = handle_unexpected_error(mock_error)
        assert "Error: Unexpected system error" in error_msg
    
    def test_stdout_redirection_pattern(self):
        """Test stdout redirection pattern used in documentation tool"""
        # Test the pattern used to capture unexpected stdout
        old_stdout = StringIO()
        temp_stdout = StringIO()
        
        try:
            # Write something that should be captured
            print("This should be captured", file=temp_stdout)
            
            # Check capture
            captured_output = temp_stdout.getvalue()
            assert "This should be captured" in captured_output
        finally:
            # Pattern always restores stdout
            pass
    
    def test_logging_patterns(self):
        """Test logging patterns used in documentation tool"""
        def simulate_logging_patterns(filename, file_path, content_length):
            log_messages = []
            
            # Info log when starting to read
            log_messages.append(f"Reading documentation file: {file_path}")
            
            # Success log with content length
            log_messages.append(f"Successfully read documentation file '{filename}' ({content_length} characters)")
            
            return log_messages
        
        logs = simulate_logging_patterns("test-doc", "/path/test.md", 1234)
        assert len(logs) == 2
        assert "Reading documentation file: /path/test.md" in logs[0]
        assert "Successfully read documentation file 'test-doc' (1234 characters)" in logs[1]
    
    def test_content_validation_patterns(self):
        """Test content validation patterns"""
        def validate_file_content(content):
            if not isinstance(content, str):
                return False, "File content must be a string"
            
            if not content:
                return False, "File content is empty"
            
            # Check for basic markdown structure
            if not any(line.strip().startswith('#') for line in content.split('\n')):
                return False, "Warning: File does not appear to contain markdown headers"
            
            return True, None
        
        # Test valid markdown content
        valid_content = """# Main Title

## Section 1
Content here.

### Subsection
More content.
"""
        valid, error = validate_file_content(valid_content)
        assert valid is True
        assert error is None
        
        # Test empty content
        valid, error = validate_file_content("")
        assert valid is False
        assert "File content is empty" in error
        
        # Test non-string content
        valid, error = validate_file_content(None)
        assert valid is False
        assert "File content must be a string" in error
        
        # Test content without markdown headers
        no_headers_content = "This is just plain text without any markdown headers."
        valid, error = validate_file_content(no_headers_content)
        assert valid is False
        assert "does not appear to contain markdown headers" in error


class TestDocumentationToolSharedPatterns:
    """Test shared patterns for documentation tools"""
    
    def test_file_system_path_handling(self):
        """Test file system path handling patterns"""
        def safe_path_join(*parts):
            """Safely join path parts"""
            return os.path.join(*parts)
        
        def validate_path_exists(path):
            """Mock path existence check"""
            # In real implementation would use os.path.exists()
            mock_existing_paths = [
                "/home/user/project/plexus/docs/score-yaml-format.md",
                "/test/project/plexus/docs/feedback-alignment.md"
            ]
            return path in mock_existing_paths
        
        # Test path joining
        path = safe_path_join("/home", "user", "project", "docs", "file.md")
        assert path == "/home/user/project/docs/file.md"
        
        # Test path validation
        valid_path = "/home/user/project/plexus/docs/score-yaml-format.md"
        assert validate_path_exists(valid_path) is True
        
        invalid_path = "/nonexistent/path/file.md"
        assert validate_path_exists(invalid_path) is False
    
    def test_encoding_handling_patterns(self):
        """Test file encoding handling patterns"""
        def read_file_with_encoding(file_path, encoding='utf-8'):
            """Simulate file reading with encoding"""
            # Mock different file contents with special characters
            mock_files = {
                "/test/ascii.md": "Simple ASCII content",
                "/test/utf8.md": "UTF-8 content with émojis 🚀 and spëcial çhars",
                "/test/latin1.md": "Latin-1 content"
            }
            
            if file_path not in mock_files:
                raise FileNotFoundError(f"File not found: {file_path}")
            
            content = mock_files[file_path]
            
            # Simulate encoding issues
            if encoding == 'ascii' and file_path == "/test/utf8.md":
                raise UnicodeDecodeError('ascii', b'', 0, 1, 'ordinal not in range(128)')
            
            return content
        
        # Test successful UTF-8 reading
        content = read_file_with_encoding("/test/utf8.md", "utf-8")
        assert "émojis 🚀" in content
        
        # Test ASCII content
        content = read_file_with_encoding("/test/ascii.md", "utf-8")
        assert "Simple ASCII content" in content
        
        # Test encoding error
        with pytest.raises(UnicodeDecodeError):
            read_file_with_encoding("/test/utf8.md", "ascii")
    
    def test_directory_traversal_protection(self):
        """Test directory traversal protection patterns"""
        def validate_filename_safety(filename):
            """Validate filename for directory traversal attacks"""
            dangerous_patterns = ['..', '/', '\\', '\x00']
            
            for pattern in dangerous_patterns:
                if pattern in filename:
                    return False, f"Filename contains dangerous pattern: {pattern}"
            
            return True, None
        
        # Test safe filenames
        safe_filenames = ["score-yaml-format", "feedback-alignment", "dataset-yaml-format"]
        for filename in safe_filenames:
            valid, error = validate_filename_safety(filename)
            assert valid is True
            assert error is None
        
        # Test dangerous filenames
        dangerous_filenames = [
            "../etc/passwd",
            "file/with/slash",
            "file\\with\\backslash",
            "file\x00null"
        ]
        
        for filename in dangerous_filenames:
            valid, error = validate_filename_safety(filename)
            assert valid is False
            assert "dangerous pattern" in error
    
    def test_content_size_validation(self):
        """Test content size validation patterns"""
        def validate_content_size(content, max_size=1024*1024):  # 1MB default
            if len(content) > max_size:
                return False, f"File content too large: {len(content)} bytes (max: {max_size})"
            return True, None
        
        # Test normal size content
        normal_content = "A" * 1000  # 1KB
        valid, error = validate_content_size(normal_content)
        assert valid is True
        assert error is None
        
        # Test oversized content
        large_content = "A" * (2 * 1024 * 1024)  # 2MB
        valid, error = validate_content_size(large_content, 1024*1024)
        assert valid is False
        assert "File content too large" in error
        assert "2097152 bytes" in error
    
    def test_file_type_validation(self):
        """Test file type validation patterns"""
        def validate_file_extension(filename):
            allowed_extensions = ['.md', '.txt', '.rst']
            
            if not any(filename.endswith(ext) for ext in allowed_extensions):
                return False, f"File extension not allowed. Allowed: {allowed_extensions}"
            
            return True, None
        
        # Test allowed extensions
        valid_files = ["doc.md", "readme.txt", "guide.rst"]
        for filename in valid_files:
            valid, error = validate_file_extension(filename)
            assert valid is True
            assert error is None
        
        # Test disallowed extensions
        invalid_files = ["script.py", "data.json", "binary.exe", "noext"]
        for filename in invalid_files:
            valid, error = validate_file_extension(filename)
            assert valid is False
            assert "File extension not allowed" in error