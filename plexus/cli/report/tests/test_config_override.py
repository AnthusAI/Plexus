"""
Test that config_content_override parameter works in _generate_report_core.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, ANY
from plexus.reports.service import _generate_report_core


class TestConfigContentOverride:
    """Test that config_content_override is used instead of loading from DB."""
    
    @patch('plexus.reports.service._load_report_configuration')
    @patch('plexus.reports.service.Report.create')
    @patch('plexus.reports.service._parse_report_configuration')
    @patch('plexus.reports.service.ReportBlock.create')
    @patch('plexus.reports.service._instantiate_and_run_block')
    def test_uses_override_content_when_provided(
        self, 
        mock_run_block,
        mock_block_create,
        mock_parse,
        mock_report_create,
        mock_load_config
    ):
        """Test that override content is used instead of DB content."""
        
        # Mock config loaded from DB (with template syntax)
        mock_config = MagicMock()
        mock_config.id = 'config-123'
        mock_config.name = 'Test Config'
        mock_config.accountId = 'account-123'
        mock_config.configuration = 'Original content with {{ template }}'
        mock_load_config.return_value = mock_config
        
        # Mock tracker
        mock_tracker = MagicMock()
        mock_tracker.task_id = 'task-123'
        
        # Mock report creation
        mock_report = MagicMock()
        mock_report.id = 'report-123'
        mock_report_create.return_value = mock_report
        
        # Mock parsing to return no blocks
        mock_parse.return_value = []
        
        # Rendered content (without template syntax)
        rendered_content = 'Rendered content with actual value'
        
        # Call with override
        report_id, error = _generate_report_core(
            report_config_id='config-123',
            account_id='account-123',
            run_parameters={},
            client=MagicMock(),
            tracker=mock_tracker,
            config_content_override=rendered_content
        )
        
        # Verify parse was called with RENDERED content, not original
        mock_parse.assert_called_once()
        parse_call_args = mock_parse.call_args[0][0]
        
        assert parse_call_args == rendered_content, \
            "Parser should receive rendered content, not original template"
        assert '{{ template }}' not in parse_call_args, \
            "Rendered content should not contain template syntax"
        
        # Verify report was created with rendered content
        mock_report_create.assert_called_once()
        report_create_kwargs = mock_report_create.call_args[1]
        assert report_create_kwargs['output'] == rendered_content
    
    @patch('plexus.reports.service._load_report_configuration')
    @patch('plexus.reports.service.Report.create')
    @patch('plexus.reports.service._parse_report_configuration')
    def test_uses_db_content_when_no_override(
        self,
        mock_parse,
        mock_report_create,
        mock_load_config
    ):
        """Test that DB content is used when no override provided."""
        
        # Mock config loaded from DB
        db_content = 'Content from database'
        mock_config = MagicMock()
        mock_config.id = 'config-123'
        mock_config.name = 'Test Config'
        mock_config.accountId = 'account-123'
        mock_config.configuration = db_content
        mock_load_config.return_value = mock_config
        
        # Mock tracker
        mock_tracker = MagicMock()
        mock_tracker.task_id = 'task-123'
        
        # Mock report creation
        mock_report = MagicMock()
        mock_report.id = 'report-123'
        mock_report_create.return_value = mock_report
        
        # Mock parsing to return no blocks
        mock_parse.return_value = []
        
        # Call WITHOUT override (default behavior)
        report_id, error = _generate_report_core(
            report_config_id='config-123',
            account_id='account-123',
            run_parameters={},
            client=MagicMock(),
            tracker=mock_tracker
            # No config_content_override parameter
        )
        
        # Verify parse was called with DB content
        mock_parse.assert_called_once()
        parse_call_args = mock_parse.call_args[0][0]
        
        assert parse_call_args == db_content, \
            "Parser should receive DB content when no override provided"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

