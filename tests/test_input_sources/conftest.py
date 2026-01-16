"""Pytest configuration for input source tests."""
import pytest


@pytest.fixture(autouse=True, scope='function')
def isolate_tests():
    """Ensure complete test isolation by clearing module cache and resetting imports."""
    import sys
    import importlib
    from unittest.mock import _patch

    # Reload modules BEFORE each test to ensure clean state
    modules_to_reload = [
        'plexus.utils.score_result_s3_utils',
        'plexus.input_sources.TextFileInputSource',
        'plexus.input_sources.DeepgramInputSource',
    ]
    for module_name in modules_to_reload:
        if module_name in sys.modules:
            try:
                importlib.reload(sys.modules[module_name])
            except:
                pass

    # Store original state
    original_modules = set(sys.modules.keys())

    yield

    # Stop all active patches to prevent pollution
    try:
        import unittest.mock as mock
        # Clear any lingering mock state
        mock._patch._active_patches[:] = []
    except:
        pass

    # Clean up any modules loaded during the test
    new_modules = set(sys.modules.keys()) - original_modules
    for module_name in new_modules:
        if module_name.startswith('plexus.input_sources') or module_name.startswith('plexus.utils.score_result'):
            sys.modules.pop(module_name, None)
