"""
CLI Smoke Tests - Fast Tests for CI

These are lightweight tests that can run quickly in CI to catch basic CLI issues.
They focus on import validation and basic command availability.
"""

import subprocess
import pytest
import sys
import os


class TestCLISmokeTests:
    """Quick smoke tests for CLI functionality"""
    
    def test_entry_point_exists(self):
        """Test that plexus command exists and can show help"""
        result = subprocess.run(['plexus', '--help'], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"plexus --help failed: {result.stderr}"
        assert any(x in result.stdout.lower() for x in ['usage', 'commands', 'plexus']), "Help output seems malformed"
    
    def test_core_commands_exist(self):
        """Test that core commands don't fail with import errors"""
        core_commands = ['score', 'scorecard', 'evaluate', 'command']
        
        for cmd in core_commands:
            result = subprocess.run(['plexus', cmd, '--help'], capture_output=True, text=True, timeout=30)
            
            # Should not fail with import errors
            assert "ModuleNotFoundError" not in result.stderr, f"Import error in '{cmd}': {result.stderr}"
            assert "ImportError" not in result.stderr, f"Import error in '{cmd}': {result.stderr}"
    
    def test_worker_command_basic(self):
        """Test that worker command doesn't crash on startup"""
        result = subprocess.run(['plexus', 'command', 'worker', '--help'], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"Worker command failed: {result.stderr}"
        assert "ModuleNotFoundError" not in result.stderr, f"Worker import error: {result.stderr}"
    
    def test_main_imports_work(self):
        """Test that main CLI modules can be imported"""
        critical_imports = [
            'plexus.cli.shared.CommandLineInterface',
            'plexus.cli.shared.CommandTasks',
            'plexus.cli.shared.CommandDispatch'
        ]
        
        for module_name in critical_imports:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Critical import failed: {module_name} - {e}")


if __name__ == "__main__":
    # Quick smoke test when run directly
    print("Running CLI smoke tests...")
    
    # Test 1: Basic help
    result = subprocess.run(['plexus', '--help'], capture_output=True, text=True, timeout=30)
    print(f"✓ plexus --help: {'PASS' if result.returncode == 0 else 'FAIL'}")
    
    # Test 2: Worker command
    result = subprocess.run(['plexus', 'command', 'worker', '--help'], capture_output=True, text=True, timeout=30)
    print(f"✓ worker command: {'PASS' if result.returncode == 0 else 'FAIL'}")
    
    # Test 3: Import test
    try:
        import plexus.cli.shared.CommandLineInterface
        print("✓ CLI imports: PASS")
    except Exception as e:
        print(f"✗ CLI imports: FAIL - {e}")
    
    print("Smoke tests complete!")
