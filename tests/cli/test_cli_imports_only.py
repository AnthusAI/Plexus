"""
Ultra-fast CLI import validation tests

These tests only validate imports work correctly, without running actual CLI commands.
They should run in < 5 seconds and catch import-related restructuring issues.
"""

import pytest


class TestCLIImportsOnly:
    """Test that all CLI modules can be imported without errors"""
    
    def test_main_cli_modules(self):
        """Test core CLI modules that were affected by restructuring"""
        # These imports were broken during restructuring
        try:
            from plexus.cli.shared.CommandLineInterface import main, cli
            assert callable(main)
        except ImportError as e:
            pytest.fail(f"Failed to import CommandLineInterface: {e}")
    
    def test_command_tasks_module(self):
        """Test CommandTasks module that had broken imports"""
        try:
            from plexus.cli.shared.CommandTasks import register_tasks
            assert callable(register_tasks)
        except ImportError as e:
            pytest.fail(f"Failed to import CommandTasks: {e}")
    
    def test_command_dispatch_module(self):
        """Test CommandDispatch module that had broken imports"""
        try:
            from plexus.cli.shared.CommandDispatch import get_celery_app, create_celery_app
            assert callable(get_celery_app)
            assert callable(create_celery_app)
        except ImportError as e:
            pytest.fail(f"Failed to import CommandDispatch: {e}")
    
    def test_score_chat_module(self):
        """Test score chat module that had broken import path"""
        try:
            from plexus.cli.score_chat.chat import register_tasks
            assert callable(register_tasks)
        except ImportError as e:
            pytest.fail(f"Failed to import score_chat.chat: {e}")
    
    def test_all_command_modules(self):
        """Test all command modules can be imported"""
        command_modules = [
            'plexus.cli.score.scores',
            'plexus.cli.scorecard.scorecards',
            'plexus.cli.evaluation.evaluations',
            'plexus.cli.report.reports',
            'plexus.cli.item.items',
            'plexus.cli.task.tasks',
            'plexus.cli.batch.operations',
            'plexus.cli.data.operations',
            'plexus.cli.feedback.commands'
        ]
        
        for module_name in command_modules:
            try:
                __import__(module_name)
            except ImportError as e:
                pytest.fail(f"Failed to import {module_name}: {e}")
    
    def test_scorecard_commands_import(self):
        """Test that both scorecard and scorecards can be imported"""
        try:
            from plexus.cli.scorecard.scorecards import scorecard, scorecards
            # These should be Click command groups
            assert hasattr(scorecard, '__call__')
            assert hasattr(scorecards, '__call__')
        except ImportError as e:
            pytest.fail(f"Failed to import scorecard commands: {e}")


if __name__ == "__main__":
    print("Running ultra-fast CLI import tests...")
    
    # Test critical imports directly
    try:
        from plexus.cli.shared.CommandLineInterface import main
        print("✓ CommandLineInterface import")
    except Exception as e:
        print(f"✗ CommandLineInterface import: {e}")
        exit(1)
    
    try:
        from plexus.cli.shared.CommandTasks import register_tasks
        print("✓ CommandTasks import")
    except Exception as e:
        print(f"✗ CommandTasks import: {e}")
        exit(1)
    
    try:
        from plexus.cli.score_chat.chat import register_tasks
        print("✓ Score chat import")
    except Exception as e:
        print(f"✗ Score chat import: {e}")
        exit(1)
    
    try:
        from plexus.cli.scorecard.scorecards import scorecard, scorecards
        print("✓ Scorecard commands import")
    except Exception as e:
        print(f"✗ Scorecard commands import: {e}")
        exit(1)
        
    print("All import tests passed! 🚀")
