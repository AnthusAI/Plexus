#!/usr/bin/env python3
"""
Guidelines validation tool for Plexus MCP Server.
"""
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Dict, Any, Optional
from fastmcp import FastMCP


@lru_cache(maxsize=1)
def _load_guidelines_validator():
    """Dynamically load the guidelines validator from the Plexus skill."""
    import importlib.util

    # Resolve repo root from this file: MCP/tools/score/guidelines.py -> repo root
    repo_root = Path(__file__).resolve().parents[3]
    candidate_paths = [
        repo_root / "skills" / "plexus-guidelines" / "validate_guidelines.py",
        repo_root / ".claude" / "skills" / "plexus-guidelines" / "validate_guidelines.py",
    ]
    validator_path = next((path for path in candidate_paths if path.exists()), None)
    if validator_path is None:
        joined = ", ".join(str(path) for path in candidate_paths)
        raise FileNotFoundError(f"Guidelines validator not found. Checked: {joined}")

    spec = importlib.util.spec_from_file_location("plexus_guidelines_validator", str(validator_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load validator module from {validator_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[union-attr]

    if not hasattr(module, "validate_guidelines"):
        raise AttributeError("validate_guidelines function not found in validator module")

    return module


def register_guidelines_tools(mcp: FastMCP):
    """Register guidelines validation tool with the MCP server."""

    @mcp.tool()
    async def plexus_guidelines_validate(
        guidelines_markdown: Optional[str] = None,
        input: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Validate Plexus score guidelines markdown and return structured results.

        Parameters:
        - guidelines_markdown: Markdown content to validate

        Returns:
        - Validation result fields:
          is_valid, classifier_type, missing_sections, found_sections, unknown_sections, messages
        """
        if (guidelines_markdown is None or not str(guidelines_markdown).strip()) and input:
            guidelines_markdown = input

        if guidelines_markdown is None or not str(guidelines_markdown).strip():
            return {
                "success": False,
                "error": "guidelines_markdown is required and cannot be empty"
            }

        try:
            module = _load_guidelines_validator()
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to load guidelines validator: {str(e)}"
            }

        tmp_path: Optional[Path] = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                tmp_file.write(guidelines_markdown)

            result = module.validate_guidelines(tmp_path)

            return {
                "success": True,
                "is_valid": result.is_valid,
                "classifier_type": result.classifier_type,
                "missing_sections": result.missing_sections,
                "found_sections": result.found_sections,
                "unknown_sections": result.unknown_sections,
                "messages": result.messages
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Guidelines validation failed: {str(e)}"
            }
        finally:
            if tmp_path and tmp_path.exists():
                try:
                    tmp_path.unlink()
                except Exception:
                    pass
