"""
File Primitive - File I/O operations for workflows.

Provides:
- File.read(path) - Read file contents
- File.write(path, content) - Write content to file
- File.exists(path) - Check if file exists
- File.size(path) - Get file size in bytes
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


class FilePrimitive:
    """
    Handles file operations for procedures.

    Enables workflows to:
    - Read file contents
    - Write data to files
    - Check file existence
    - Get file metadata
    """

    def __init__(self, base_path: Optional[str] = None):
        """
        Initialize File primitive.

        Args:
            base_path: Optional base directory for relative paths (defaults to cwd)
        """
        self.base_path = Path(base_path) if base_path else Path.cwd()
        logger.debug(f"FilePrimitive initialized with base_path: {self.base_path}")

    def read(self, path: str) -> str:
        """
        Read file contents as string.

        Args:
            path: File path to read (absolute or relative to base_path)

        Returns:
            File contents as string

        Raises:
            FileNotFoundError: If file doesn't exist
            IOError: If file cannot be read

        Example (Lua):
            local config = File.read("config.json")
            Log.info("Config loaded", {length = #config})
        """
        file_path = self._resolve_path(path)

        try:
            logger.debug(f"Reading file: {file_path}")
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            logger.info(f"Read {len(content)} bytes from {file_path}")
            return content

        except FileNotFoundError:
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        except Exception as e:
            error_msg = f"Failed to read file {file_path}: {e}"
            logger.error(error_msg)
            raise IOError(error_msg)

    def write(self, path: str, content: str) -> bool:
        """
        Write content to file.

        Args:
            path: File path to write (absolute or relative to base_path)
            content: Content to write

        Returns:
            True if successful

        Raises:
            IOError: If file cannot be written

        Example (Lua):
            local data = Json.encode({status = "complete"})
            File.write("output.json", data)
            Log.info("Data written")
        """
        file_path = self._resolve_path(path)

        try:
            # Create parent directories if needed
            file_path.parent.mkdir(parents=True, exist_ok=True)

            logger.debug(f"Writing to file: {file_path}")
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            logger.info(f"Wrote {len(content)} bytes to {file_path}")
            return True

        except Exception as e:
            error_msg = f"Failed to write file {file_path}: {e}"
            logger.error(error_msg)
            raise IOError(error_msg)

    def exists(self, path: str) -> bool:
        """
        Check if file exists.

        Args:
            path: File path to check (absolute or relative to base_path)

        Returns:
            True if file exists, False otherwise

        Example (Lua):
            if File.exists("cache.json") then
                local data = File.read("cache.json")
                Log.info("Using cached data")
            else
                Log.info("No cache found")
            end
        """
        file_path = self._resolve_path(path)
        exists = file_path.exists() and file_path.is_file()
        logger.debug(f"File exists check for {file_path}: {exists}")
        return exists

    def size(self, path: str) -> int:
        """
        Get file size in bytes.

        Args:
            path: File path to check (absolute or relative to base_path)

        Returns:
            File size in bytes

        Raises:
            FileNotFoundError: If file doesn't exist

        Example (Lua):
            local size = File.size("data.csv")
            Log.info("File size", {bytes = size, kb = size / 1024})
        """
        file_path = self._resolve_path(path)

        if not file_path.exists():
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            raise FileNotFoundError(error_msg)

        size = file_path.stat().st_size
        logger.debug(f"File size for {file_path}: {size} bytes")
        return size

    def _resolve_path(self, path: str) -> Path:
        """
        Resolve file path relative to base_path with security validation.

        Args:
            path: File path to resolve (must be relative)

        Returns:
            Resolved Path object

        Raises:
            ValueError: If absolute path or path traversal detected
        """
        path_obj = Path(path)

        # Security: Never allow absolute paths
        if path_obj.is_absolute():
            raise ValueError(f"Absolute paths not allowed: {path}")

        # Resolve relative to base_path
        resolved = (self.base_path / path_obj).resolve()

        # Security: Verify resolved path is under base_path
        try:
            resolved.relative_to(self.base_path)
        except ValueError:
            raise ValueError(f"Path traversal detected: {path} resolves outside base directory")

        return resolved

    def __repr__(self) -> str:
        return f"FilePrimitive(base_path={self.base_path})"
