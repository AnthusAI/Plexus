"""Pytest configuration for input source tests."""
import pytest
import sys


@pytest.fixture(autouse=True)
def reset_module_cache():
    """Reset module cache between tests to prevent state pollution."""
    # Store modules before test
    modules_before = set(sys.modules.keys())

    yield

    # Clean up modules added during test (except core ones)
    modules_after = set(sys.modules.keys())
    new_modules = modules_after - modules_before

    # Remove test-created modules
    for module_name in new_modules:
        if module_name.startswith('plexus.input_sources'):
            del sys.modules[module_name]
