"""
Tests for File Primitive - File I/O operations.

Tests all File primitive methods:
- File.read(path) - Read file contents
- File.write(path, content) - Write content to file
- File.exists(path) - Check if file exists
- File.size(path) - Get file size in bytes

Includes critical security tests for path traversal prevention.
"""

import pytest
import tempfile
import os
from pathlib import Path
from plexus.cli.procedure.lua_dsl.primitives.file import FilePrimitive


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def file_primitive(temp_dir):
    """Create a File primitive with temp directory as base."""
    # Ensure we use resolved absolute path
    return FilePrimitive(base_path=str(temp_dir.resolve()))


@pytest.fixture
def sample_files(temp_dir):
    """Create sample files for testing."""
    # Create test files
    (temp_dir / "test.txt").write_text("Hello, World!")
    (temp_dir / "empty.txt").write_text("")
    (temp_dir / "unicode.txt").write_text("こんにちは世界 🌍")

    # Create subdirectory with file
    subdir = temp_dir / "subdir"
    subdir.mkdir()
    (subdir / "nested.txt").write_text("Nested content")

    return temp_dir


class TestFileRead:
    """Tests for File.read()"""

    def test_read_existing_file(self, file_primitive, sample_files):
        """Should read existing file contents."""
        content = file_primitive.read("test.txt")
        assert content == "Hello, World!"

    def test_read_empty_file(self, file_primitive, sample_files):
        """Should read empty file."""
        content = file_primitive.read("empty.txt")
        assert content == ""

    def test_read_unicode_content(self, file_primitive, sample_files):
        """Should read unicode content correctly."""
        content = file_primitive.read("unicode.txt")
        assert "こんにちは世界" in content
        assert "🌍" in content

    def test_read_nested_file(self, file_primitive, sample_files):
        """Should read file in subdirectory."""
        content = file_primitive.read("subdir/nested.txt")
        assert content == "Nested content"

    def test_read_nonexistent_file_raises_error(self, file_primitive):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            file_primitive.read("nonexistent.txt")

    def test_read_preserves_whitespace(self, file_primitive, temp_dir):
        """Should preserve whitespace in content."""
        test_file = temp_dir / "whitespace.txt"
        test_file.write_text("  spaces  \n\ttabs\t\n\n")

        content = file_primitive.read("whitespace.txt")
        assert content == "  spaces  \n\ttabs\t\n\n"

    def test_read_multiline_content(self, file_primitive, temp_dir):
        """Should read multiline content."""
        test_file = temp_dir / "multiline.txt"
        test_file.write_text("Line 1\nLine 2\nLine 3\n")

        content = file_primitive.read("multiline.txt")
        assert content == "Line 1\nLine 2\nLine 3\n"

    def test_read_large_file(self, file_primitive, temp_dir):
        """Should read large files."""
        large_content = "x" * 100000
        test_file = temp_dir / "large.txt"
        test_file.write_text(large_content)

        content = file_primitive.read("large.txt")
        assert len(content) == 100000


class TestFileWrite:
    """Tests for File.write()"""

    def test_write_new_file(self, file_primitive, temp_dir):
        """Should create and write new file."""
        result = file_primitive.write("new.txt", "New content")

        assert result is True
        assert (temp_dir / "new.txt").read_text() == "New content"

    def test_write_overwrites_existing(self, file_primitive, temp_dir):
        """Should overwrite existing file."""
        test_file = temp_dir / "existing.txt"
        test_file.write_text("Old content")

        result = file_primitive.write("existing.txt", "New content")

        assert result is True
        assert test_file.read_text() == "New content"

    def test_write_empty_content(self, file_primitive, temp_dir):
        """Should write empty content."""
        result = file_primitive.write("empty.txt", "")

        assert result is True
        assert (temp_dir / "empty.txt").read_text() == ""

    def test_write_unicode_content(self, file_primitive, temp_dir):
        """Should write unicode content."""
        unicode_text = "日本語テキスト 🎌"
        result = file_primitive.write("unicode.txt", unicode_text)

        assert result is True
        assert (temp_dir / "unicode.txt").read_text() == unicode_text

    def test_write_multiline_content(self, file_primitive, temp_dir):
        """Should write multiline content."""
        multiline = "Line 1\nLine 2\nLine 3\n"
        result = file_primitive.write("multiline.txt", multiline)

        assert result is True
        assert (temp_dir / "multiline.txt").read_text() == multiline

    def test_write_creates_parent_directories(self, file_primitive, temp_dir):
        """Should create parent directories if needed."""
        result = file_primitive.write("deep/nested/path/file.txt", "Content")

        assert result is True
        assert (temp_dir / "deep/nested/path/file.txt").read_text() == "Content"

    def test_write_large_content(self, file_primitive, temp_dir):
        """Should write large content."""
        large_content = "y" * 100000
        result = file_primitive.write("large.txt", large_content)

        assert result is True
        assert (temp_dir / "large.txt").read_text() == large_content

    def test_write_special_characters(self, file_primitive, temp_dir):
        """Should write special characters."""
        special = "Special: <>&\"'\n\t"
        result = file_primitive.write("special.txt", special)

        assert result is True
        # Note: \r may be converted on Unix systems
        content = (temp_dir / "special.txt").read_text()
        assert "Special: <>&\"'" in content
        assert "\n" in content
        assert "\t" in content


class TestFileExists:
    """Tests for File.exists()"""

    def test_exists_returns_true_for_existing_file(self, file_primitive, sample_files):
        """Should return True for existing file."""
        assert file_primitive.exists("test.txt") is True

    def test_exists_returns_false_for_nonexistent(self, file_primitive):
        """Should return False for nonexistent file."""
        assert file_primitive.exists("nonexistent.txt") is False

    def test_exists_returns_true_for_nested_file(self, file_primitive, sample_files):
        """Should return True for file in subdirectory."""
        assert file_primitive.exists("subdir/nested.txt") is True

    def test_exists_returns_false_for_directory(self, file_primitive, temp_dir):
        """Should return False for directories."""
        subdir = temp_dir / "testdir"
        subdir.mkdir()

        assert file_primitive.exists("testdir") is False

    def test_exists_after_write(self, file_primitive):
        """Should return True after writing file."""
        assert file_primitive.exists("new.txt") is False

        file_primitive.write("new.txt", "content")

        assert file_primitive.exists("new.txt") is True

    def test_exists_with_empty_file(self, file_primitive, temp_dir):
        """Should return True for empty files."""
        empty_file = temp_dir / "empty.txt"
        empty_file.write_text("")

        assert file_primitive.exists("empty.txt") is True


class TestFileSize:
    """Tests for File.size()"""

    def test_size_returns_correct_size(self, file_primitive, sample_files):
        """Should return correct file size in bytes."""
        size = file_primitive.size("test.txt")
        assert size == len("Hello, World!")

    def test_size_of_empty_file(self, file_primitive, sample_files):
        """Should return 0 for empty file."""
        size = file_primitive.size("empty.txt")
        assert size == 0

    def test_size_of_unicode_file(self, file_primitive, sample_files):
        """Should return correct size for unicode content."""
        size = file_primitive.size("unicode.txt")
        # Unicode characters may be multiple bytes
        assert size > 0

    def test_size_of_large_file(self, file_primitive, temp_dir):
        """Should return correct size for large files."""
        large_content = "z" * 50000
        test_file = temp_dir / "large.txt"
        test_file.write_text(large_content)

        size = file_primitive.size("large.txt")
        assert size == 50000

    def test_size_nonexistent_file_raises_error(self, file_primitive):
        """Should raise FileNotFoundError for missing file."""
        with pytest.raises(FileNotFoundError, match="File not found"):
            file_primitive.size("nonexistent.txt")

    def test_size_after_write(self, file_primitive):
        """Should return correct size after writing."""
        content = "Test content"
        file_primitive.write("test.txt", content)

        size = file_primitive.size("test.txt")
        assert size == len(content)


class TestFilePathTraversalSecurity:
    """CRITICAL: Tests for path traversal security vulnerabilities."""

    def test_absolute_path_rejected(self, file_primitive):
        """Should reject absolute paths."""
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            file_primitive.read("/etc/passwd")

        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            file_primitive.write("/tmp/evil.txt", "content")

    def test_parent_directory_traversal_rejected(self, file_primitive):
        """Should reject parent directory traversal."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            file_primitive.read("../../../etc/passwd")

        with pytest.raises(ValueError, match="Path traversal detected"):
            file_primitive.write("../outside.txt", "content")

    def test_hidden_traversal_rejected(self, file_primitive):
        """Should reject hidden traversal attempts."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            file_primitive.read("subdir/../../../../../../etc/passwd")

    def test_mixed_traversal_rejected(self, file_primitive):
        """Should reject mixed traversal patterns."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            file_primitive.read("./subdir/../../../outside.txt")

    def test_traversal_in_exists_rejected(self, file_primitive):
        """Should reject traversal in exists() check."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            file_primitive.exists("../outside.txt")

    def test_traversal_in_size_rejected(self, file_primitive):
        """Should reject traversal in size() check."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            file_primitive.size("../outside.txt")

    def test_safe_subdirectory_access_allowed(self, file_primitive, temp_dir):
        """Should allow safe subdirectory access."""
        subdir = temp_dir / "safe" / "nested"
        subdir.mkdir(parents=True)
        (subdir / "file.txt").write_text("Safe content")

        # Should work fine
        content = file_primitive.read("safe/nested/file.txt")
        assert content == "Safe content"

    def test_relative_path_within_base_allowed(self, file_primitive, temp_dir):
        """Should allow paths that stay within base directory."""
        # Create nested structure
        (temp_dir / "a").mkdir()
        (temp_dir / "b").mkdir()
        (temp_dir / "a" / "test.txt").write_text("Content A")
        (temp_dir / "b" / "test.txt").write_text("Content B")

        # Moving between subdirectories should work
        content_a = file_primitive.read("a/test.txt")
        content_b = file_primitive.read("b/test.txt")

        assert content_a == "Content A"
        assert content_b == "Content B"

    def test_symlink_escape_prevented(self, file_primitive, temp_dir):
        """Should prevent symlink escape attempts."""
        # Create a file outside base directory
        outside_dir = temp_dir.parent / "outside"
        outside_dir.mkdir(exist_ok=True)
        outside_file = outside_dir / "secret.txt"
        outside_file.write_text("Secret data")

        # Try to create symlink inside base pointing outside
        try:
            symlink = temp_dir / "symlink.txt"
            symlink.symlink_to(outside_file)

            # Attempt to read through symlink should fail
            with pytest.raises(ValueError, match="Path traversal detected"):
                file_primitive.read("symlink.txt")
        except OSError:
            # Symlink creation might fail on some systems, that's ok
            pass
        finally:
            # Cleanup
            if outside_dir.exists():
                for f in outside_dir.iterdir():
                    f.unlink()
                outside_dir.rmdir()

    def test_windows_absolute_path_rejected(self, file_primitive):
        """Should reject Windows-style absolute paths on Windows."""
        import platform
        if platform.system() == "Windows":
            # Windows absolute paths only work on Windows
            with pytest.raises(ValueError, match="Absolute paths not allowed"):
                file_primitive.read("C:\\Windows\\System32\\config\\sam")

            with pytest.raises(ValueError, match="Absolute paths not allowed"):
                file_primitive.write("D:\\evil.txt", "content")
        else:
            # On Unix, these look like relative paths but should still fail gracefully
            # They won't match real files in any case
            pass


class TestFileReadWrite:
    """Integration tests for read/write operations."""

    def test_write_then_read(self, file_primitive):
        """Should write and then read same content."""
        content = "Test content"
        file_primitive.write("test.txt", content)

        read_content = file_primitive.read("test.txt")
        assert read_content == content

    def test_overwrite_preserves_no_old_content(self, file_primitive):
        """Should completely overwrite old content."""
        file_primitive.write("test.txt", "Old content is longer")
        file_primitive.write("test.txt", "Short")

        content = file_primitive.read("test.txt")
        assert content == "Short"

    def test_write_read_multiple_files(self, file_primitive):
        """Should handle multiple files independently."""
        file_primitive.write("file1.txt", "Content 1")
        file_primitive.write("file2.txt", "Content 2")
        file_primitive.write("file3.txt", "Content 3")

        assert file_primitive.read("file1.txt") == "Content 1"
        assert file_primitive.read("file2.txt") == "Content 2"
        assert file_primitive.read("file3.txt") == "Content 3"


class TestFileIntegration:
    """Integration tests combining multiple operations."""

    def test_typical_workflow(self, file_primitive):
        """Test typical file workflow."""
        filename = "data.txt"

        # Check if file exists
        assert file_primitive.exists(filename) is False

        # Write file
        file_primitive.write(filename, "Initial data")

        # Check exists now
        assert file_primitive.exists(filename) is True

        # Check size
        size = file_primitive.size(filename)
        assert size == len("Initial data")

        # Read content
        content = file_primitive.read(filename)
        assert content == "Initial data"

        # Update file
        file_primitive.write(filename, "Updated data")

        # Verify update
        assert file_primitive.read(filename) == "Updated data"
        assert file_primitive.size(filename) == len("Updated data")

    def test_cache_file_pattern(self, file_primitive):
        """Test cache file pattern."""
        cache_file = "cache.json"

        # Check for cache
        if not file_primitive.exists(cache_file):
            # Write new cache
            file_primitive.write(cache_file, '{"cached": true}')

        # Read cache
        content = file_primitive.read(cache_file)
        assert "cached" in content

    def test_nested_directory_workflow(self, file_primitive):
        """Test working with nested directories."""
        # Write to nested path (creates directories)
        file_primitive.write("data/processed/output.txt", "Result")

        # Verify
        assert file_primitive.exists("data/processed/output.txt")
        assert file_primitive.read("data/processed/output.txt") == "Result"

    def test_multiple_operations_sequence(self, file_primitive):
        """Test sequence of multiple operations."""
        # Write initial files
        file_primitive.write("step1.txt", "Step 1 complete")
        file_primitive.write("step2.txt", "Step 2 complete")

        # Verify both exist
        assert file_primitive.exists("step1.txt")
        assert file_primitive.exists("step2.txt")

        # Read and combine
        content1 = file_primitive.read("step1.txt")
        content2 = file_primitive.read("step2.txt")
        combined = content1 + "\n" + content2

        # Write combined result
        file_primitive.write("final.txt", combined)

        # Verify final
        final_content = file_primitive.read("final.txt")
        assert "Step 1" in final_content
        assert "Step 2" in final_content


class TestFileEdgeCases:
    """Edge case and error condition tests."""

    def test_filename_with_spaces(self, file_primitive):
        """Should handle filenames with spaces."""
        file_primitive.write("file with spaces.txt", "content")

        assert file_primitive.exists("file with spaces.txt")
        assert file_primitive.read("file with spaces.txt") == "content"

    def test_filename_with_special_chars(self, file_primitive):
        """Should handle filenames with special characters."""
        # Note: Some chars are not allowed in filenames on all systems
        filename = "file-with_special.chars.txt"
        file_primitive.write(filename, "content")

        assert file_primitive.exists(filename)

    def test_very_long_filename(self, file_primitive):
        """Should handle long filenames."""
        # Most filesystems support up to 255 chars
        long_name = "a" * 200 + ".txt"
        file_primitive.write(long_name, "content")

        assert file_primitive.exists(long_name)
        assert file_primitive.read(long_name) == "content"

    def test_deeply_nested_path(self, file_primitive):
        """Should handle deeply nested paths."""
        deep_path = "/".join([f"level{i}" for i in range(10)]) + "/file.txt"
        file_primitive.write(deep_path, "deep content")

        assert file_primitive.exists(deep_path)
        assert file_primitive.read(deep_path) == "deep content"

    def test_unicode_filename(self, file_primitive):
        """Should handle unicode filenames."""
        filename = "ファイル.txt"
        file_primitive.write(filename, "content")

        assert file_primitive.exists(filename)
        assert file_primitive.read(filename) == "content"

    def test_dot_prefix_filename(self, file_primitive):
        """Should handle dot-prefixed filenames."""
        file_primitive.write(".hidden", "hidden content")

        assert file_primitive.exists(".hidden")
        assert file_primitive.read(".hidden") == "hidden content"

    def test_current_directory_notation(self, file_primitive):
        """Should handle ./ notation."""
        file_primitive.write("./file.txt", "content")

        assert file_primitive.exists("file.txt")
        assert file_primitive.read("./file.txt") == "content"


class TestFileResolvePath:
    """Tests for _resolve_path() helper."""

    def test_resolve_simple_path(self, file_primitive, temp_dir):
        """Should resolve simple relative path."""
        resolved = file_primitive._resolve_path("test.txt")

        # Should return resolved absolute path
        assert resolved == (temp_dir / "test.txt").resolve()

    def test_resolve_nested_path(self, file_primitive, temp_dir):
        """Should resolve nested path."""
        resolved = file_primitive._resolve_path("subdir/file.txt")

        # Should return resolved absolute path
        assert resolved == (temp_dir / "subdir" / "file.txt").resolve()

    def test_resolve_absolute_raises_error(self, file_primitive):
        """Should raise error for absolute paths."""
        with pytest.raises(ValueError, match="Absolute paths not allowed"):
            file_primitive._resolve_path("/absolute/path")

    def test_resolve_traversal_raises_error(self, file_primitive):
        """Should raise error for path traversal."""
        with pytest.raises(ValueError, match="Path traversal detected"):
            file_primitive._resolve_path("../outside")


class TestFileBasePath:
    """Tests for base_path handling."""

    def test_default_base_path(self):
        """Should use cwd as default base path."""
        file_prim = FilePrimitive()
        assert file_prim.base_path == Path.cwd()

    def test_custom_base_path(self, temp_dir):
        """Should use custom base path."""
        file_prim = FilePrimitive(base_path=str(temp_dir))
        assert file_prim.base_path == temp_dir

    def test_base_path_in_repr(self, temp_dir):
        """Should include base_path in repr."""
        file_prim = FilePrimitive(base_path=str(temp_dir))
        assert str(temp_dir) in repr(file_prim)


class TestFileRepr:
    """Tests for __repr__()"""

    def test_repr_format(self, file_primitive, temp_dir):
        """Should show base_path in repr."""
        repr_str = repr(file_primitive)
        assert "FilePrimitive" in repr_str
        assert str(temp_dir) in repr_str

    def test_repr_with_cwd(self):
        """Should show cwd when no base_path specified."""
        file_prim = FilePrimitive()
        repr_str = repr(file_prim)
        assert "FilePrimitive" in repr_str


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
