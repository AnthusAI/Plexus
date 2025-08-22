"""
Comprehensive CLI Integration Tests

These tests validate that the CLI entry points work correctly and would catch
issues like broken imports, missing command registrations, and restructuring problems.

The tests in this file should have caught all the CLI issues we just fixed:
- Entry point import errors
- Missing command registrations  
- Broken internal imports
- Worker command failures
"""

import subprocess
import pytest
import sys
import os
from pathlib import Path


class TestCLIEntryPoints:
    """Test that CLI entry points are properly configured and functional"""
    
    def test_plexus_command_exists_in_path(self):
        """Test that plexus command is available in PATH"""
        result = subprocess.run(['which', 'plexus'], capture_output=True, text=True)
        assert result.returncode == 0, "plexus command not found in PATH"
        assert 'plexus' in result.stdout, f"Unexpected which output: {result.stdout}"
    
    def test_plexus_entry_point_works(self):
        """Test that plexus --help works without import errors"""
        result = subprocess.run(['plexus', '--help'], capture_output=True, text=True, timeout=30)
        
        # Should not fail with import errors
        assert result.returncode == 0, f"plexus --help failed with code {result.returncode}. STDERR: {result.stderr}"
        
        # Should contain expected CLI content
        assert "Plexus CLI" in result.stdout or "Usage: plexus" in result.stdout, f"Unexpected help output: {result.stdout}"
        
        # Should not have critical import errors in stderr
        critical_errors = ["ModuleNotFoundError", "ImportError", "No module named"]
        for error in critical_errors:
            assert error not in result.stderr, f"Found import error in stderr: {result.stderr}"
    
    def test_python_module_execution(self):
        """Test that 'python -m plexus.cli.shared.CommandLineInterface' works"""
        result = subprocess.run([
            sys.executable, '-m', 'plexus.cli.shared.CommandLineInterface', '--help'
        ], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"Module execution failed: {result.stderr}"
        assert "Usage:" in result.stdout or "Commands:" in result.stdout


class TestCLICommands:
    """Test that all major CLI commands are registered and accessible"""
    
    @pytest.mark.parametrize("command", [
        "score",
        "scores", 
        "scorecard",
        "scorecards",
        "evaluate",
        "predict",
        "analyze",
        "report",
        "items",
        "item",
        "tasks", 
        "task",
        "batch",
        "data",
        "feedback",
        "dataset",
        "count"
    ])
    def test_top_level_commands_available(self, command):
        """Test that all major CLI commands are registered and show help"""
        result = subprocess.run(['plexus', command, '--help'], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"Command '{command}' failed with: {result.stderr}"
        assert "Usage:" in result.stdout, f"Command '{command}' help output malformed: {result.stdout}"
    
    def test_command_worker_available(self):
        """Test that 'plexus command worker' is available (this was broken)"""
        result = subprocess.run(['plexus', 'command', 'worker', '--help'], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"'plexus command worker' failed: {result.stderr}"
        assert "Start a Celery worker" in result.stdout or "worker" in result.stdout.lower()
    
    def test_score_chat_available(self):
        """Test that 'plexus score-chat' is available"""
        result = subprocess.run(['plexus', 'score-chat', '--help'], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"'plexus score-chat' failed: {result.stderr}"
        assert "Usage:" in result.stdout


class TestCLIImports:
    """Test that all CLI imports work correctly after restructuring"""
    
    def test_main_cli_import(self):
        """Test that the main CLI module can be imported"""
        try:
            from plexus.cli.shared.CommandLineInterface import main, cli
            assert callable(main)
            assert hasattr(cli, 'commands') or callable(cli)
        except ImportError as e:
            pytest.fail(f"Failed to import main CLI components: {e}")
    
    def test_all_command_modules_importable(self):
        """Test that all command modules can be imported without errors"""
        command_modules = [
            'plexus.cli.score.scores',
            'plexus.cli.scorecard.scorecards', 
            'plexus.cli.evaluation.evaluations',
            'plexus.cli.prediction.predictions',
            'plexus.cli.analyze.analysis',
            'plexus.cli.report.reports',
            'plexus.cli.item.items',
            'plexus.cli.task.tasks',
            'plexus.cli.batch.operations',
            'plexus.cli.data.operations',
            'plexus.cli.feedback.commands',
            'plexus.cli.dataset.datasets',
            'plexus.cli.record_count.counting',
            'plexus.cli.experiment.experiments'
        ]
        
        for module_name in command_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")
    
    def test_shared_modules_importable(self):
        """Test that shared CLI modules can be imported"""
        shared_modules = [
            'plexus.cli.shared.CommandTasks',
            'plexus.cli.shared.CommandDispatch',
            'plexus.cli.shared.client_utils',
            'plexus.cli.shared.console',
            'plexus.cli.shared.file_editor'
        ]
        
        for module_name in shared_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")


class TestCLICommandStructure:
    """Test the internal structure and registration of CLI commands"""
    
    def test_all_commands_registered(self):
        """Test that expected commands are registered in the CLI"""
        from plexus.cli.shared.CommandLineInterface import cli
        
        # Get list of registered command names
        if hasattr(cli, 'commands'):
            registered_commands = list(cli.commands.keys())
        else:
            # Fallback method if commands dict not available
            result = subprocess.run(['plexus', '--help'], capture_output=True, text=True)
            registered_commands = []
            if result.returncode == 0:
                # Parse command names from help output
                lines = result.stdout.split('\n')
                in_commands = False
                for line in lines:
                    if 'Commands:' in line:
                        in_commands = True
                        continue
                    if in_commands and line.strip():
                        if line.startswith('  ') and not line.startswith('    '):
                            cmd_name = line.strip().split()[0]
                            registered_commands.append(cmd_name)
        
        # Essential commands that should be registered
        essential_commands = [
            'score', 'scorecard', 'scorecards', 'evaluate', 'predict',
            'report', 'items', 'tasks', 'command', 'data'
        ]
        
        for cmd in essential_commands:
            assert cmd in registered_commands, f"Essential command '{cmd}' not registered. Available: {registered_commands}"
    
    def test_worker_command_structure(self):
        """Test that the worker command has proper subcommand structure"""
        result = subprocess.run(['plexus', 'command', '--help'], capture_output=True, text=True, timeout=30)
        
        assert result.returncode == 0, f"'plexus command' help failed: {result.stderr}"
        assert 'worker' in result.stdout, "worker subcommand not found in command group"


class TestCLIErrorHandling:
    """Test that CLI handles errors gracefully"""
    
    def test_invalid_command_handling(self):
        """Test that invalid commands produce helpful error messages"""
        result = subprocess.run(['plexus', 'nonexistent-command'], capture_output=True, text=True, timeout=15)
        
        # Should fail with non-zero exit code
        assert result.returncode != 0, "Invalid command should fail"
        
        # Should provide helpful error message
        assert "No such command" in result.stderr or "Error:" in result.stderr
    
    def test_missing_required_args_handling(self):
        """Test commands that require args fail gracefully"""
        # Most commands should at least show help when run without required args
        commands_to_test = ['score', 'scorecard', 'evaluate']
        
        for cmd in commands_to_test:
            result = subprocess.run(['plexus', cmd], capture_output=True, text=True, timeout=15)
            
            # Should either succeed with help or fail gracefully
            if result.returncode != 0:
                # Should show usage information on failure
                assert "Usage:" in result.stdout or "Usage:" in result.stderr, f"Command '{cmd}' failed without usage info"


class TestCLIPerformance:
    """Test CLI performance and responsiveness"""
    
    def test_help_command_speed(self):
        """Test that help commands respond quickly"""
        import time
        
        start_time = time.time()
        result = subprocess.run(['plexus', '--help'], capture_output=True, text=True, timeout=30)
        end_time = time.time()
        
        assert result.returncode == 0, "Help command failed"
        
        # Should respond within reasonable time (30 seconds is very generous)
        response_time = end_time - start_time
        assert response_time < 30, f"Help command took too long: {response_time:.2f} seconds"


# Utility function for debugging test failures
def debug_cli_state():
    """Helper function to debug CLI state when tests fail"""
    print("\n=== CLI Debug Information ===")
    
    # Check if plexus is in PATH
    which_result = subprocess.run(['which', 'plexus'], capture_output=True, text=True)
    print(f"which plexus: {which_result.stdout.strip()} (exit code: {which_result.returncode})")
    
    # Try basic help
    help_result = subprocess.run(['plexus', '--help'], capture_output=True, text=True, timeout=10)
    print(f"plexus --help exit code: {help_result.returncode}")
    if help_result.stderr:
        print(f"STDERR: {help_result.stderr[:500]}")
    
    # Check Python module path
    try:
        import plexus.cli.shared.CommandLineInterface
        print("✓ Can import plexus.cli.shared.CommandLineInterface")
    except Exception as e:
        print(f"✗ Cannot import CLI: {e}")


if __name__ == "__main__":
    # When run directly, do a quick smoke test
    debug_cli_state()
