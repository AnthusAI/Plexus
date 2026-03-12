"""
Tests for Plexus configuration loader.
"""

import os
import tempfile
import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
import yaml

from .loader import ConfigLoader, load_config


class TestConfigLoader:
    """Test cases for ConfigLoader class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.loader = ConfigLoader()
        # Store original environment to restore later
        self.original_env = dict(os.environ)
        # Clear Plexus-related environment variables for testing
        self._clear_plexus_env_vars()
    
    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
    
    def _clear_plexus_env_vars(self):
        """Clear Plexus-related environment variables for clean testing."""
        for env_var in self.loader.ENV_VAR_MAPPING.values():
            if env_var != '_PLEXUS_WORKING_DIRECTORY':
                os.environ.pop(env_var, None)
    
    def test_init(self):
        """Test ConfigLoader initialization."""
        assert isinstance(self.loader.config_sources, list)
        assert len(self.loader.config_sources) == 4  # 2 filenames x 2 locations
        assert self.loader.loaded_config == {}
        assert self.loader.env_vars_set == 0
    
    def test_discover_config_sources(self):
        """Test configuration source discovery."""
        sources = self.loader._discover_config_sources()
        
        assert len(sources) == 4
        
        # Current working directory .plexus subdirectory (highest priority)
        expected_cwd_config_yaml = Path.cwd() / ".plexus" / "config.yaml"
        expected_cwd_config_yml = Path.cwd() / ".plexus" / "config.yml"
        assert sources[0].path == expected_cwd_config_yaml
        assert sources[0].priority == 1
        assert sources[1].path == expected_cwd_config_yml
        assert sources[1].priority == 2
        
        # Home directory .plexus sources (lowest priority)
        expected_home_config_yaml = Path.home() / ".plexus" / "config.yaml"
        expected_home_config_yml = Path.home() / ".plexus" / "config.yml"
        assert sources[2].path == expected_home_config_yaml
        assert sources[2].priority == 3
        assert sources[3].path == expected_home_config_yml
        assert sources[3].priority == 4
    
    def test_get_nested_value(self):
        """Test getting nested values from configuration."""
        config = {
            'plexus': {
                'api_url': 'https://test.com',
                'nested': {
                    'deep': {
                        'value': 'found'
                    }
                }
            },
            'simple': 'value'
        }
        
        # Test simple key
        assert self.loader._get_nested_value(config, 'simple') == 'value'
        
        # Test nested key
        assert self.loader._get_nested_value(config, 'plexus.api_url') == 'https://test.com'
        
        # Test deeply nested key
        assert self.loader._get_nested_value(config, 'plexus.nested.deep.value') == 'found'
        
        # Test non-existent key
        assert self.loader._get_nested_value(config, 'nonexistent') is None
        assert self.loader._get_nested_value(config, 'plexus.nonexistent') is None
    
    def test_set_nested_value(self):
        """Test setting nested values in configuration."""
        config = {}
        
        # Test simple key
        self.loader._set_nested_value(config, 'simple', 'value')
        assert config['simple'] == 'value'
        
        # Test nested key
        self.loader._set_nested_value(config, 'plexus.api_url', 'https://test.com')
        assert config['plexus']['api_url'] == 'https://test.com'
        
        # Test deeply nested key
        self.loader._set_nested_value(config, 'deep.nested.value', 'found')
        assert config['deep']['nested']['value'] == 'found'
    
    def test_load_yaml_file(self):
        """Test loading YAML configuration files."""
        test_config = {
            'plexus': {
                'api_url': 'https://test.com',
                'api_key': 'test-key'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = Path(f.name)
        
        try:
            loaded = self.loader._load_yaml_file(temp_path)
            assert loaded == test_config
        finally:
            temp_path.unlink()
    
    def test_load_yaml_file_missing(self):
        """Test loading non-existent YAML file."""
        missing_path = Path('/nonexistent/file.yaml')
        loaded = self.loader._load_yaml_file(missing_path)
        assert loaded == {}
    
    def test_merge_configs(self):
        """Test merging configuration dictionaries."""
        base_config = {
            'plexus': {
                'api_url': 'https://base.com',
                'timeout': 30
            },
            'database': {
                'host': 'localhost'
            }
        }
        
        new_config = {
            'plexus': {
                'api_url': 'https://override.com',
                'api_key': 'new-key'
            },
            'aws': {
                'region': 'us-west-2'
            }
        }
        
        merged = self.loader._merge_configs(base_config, new_config)
        
        # Check overrides
        assert merged['plexus']['api_url'] == 'https://override.com'
        
        # Check preserved values
        assert merged['plexus']['timeout'] == 30
        assert merged['database']['host'] == 'localhost'
        
        # Check new values
        assert merged['plexus']['api_key'] == 'new-key'
        assert merged['aws']['region'] == 'us-west-2'
    
    @patch('os.chdir')
    @patch('os.path.isdir')
    @patch('os.path.expanduser')
    def test_change_working_directory(self, mock_expanduser, mock_isdir, mock_chdir):
        """Test changing working directory."""
        mock_expanduser.return_value = '/expanded/path'
        mock_isdir.return_value = True
        
        result = self.loader._change_working_directory('~/test/path')
        
        assert result is True
        mock_expanduser.assert_called_once_with('~/test/path')
        mock_isdir.assert_called_once_with('/expanded/path')
        mock_chdir.assert_called_once_with('/expanded/path')
    
    @patch('os.chdir')
    @patch('os.path.isdir')
    @patch('os.path.expanduser')
    def test_change_working_directory_missing(self, mock_expanduser, mock_isdir, mock_chdir):
        """Test changing to non-existent working directory."""
        mock_expanduser.return_value = '/nonexistent/path'
        mock_isdir.return_value = False
        
        result = self.loader._change_working_directory('/nonexistent/path')
        
        assert result is False
        mock_chdir.assert_not_called()
    
    def test_set_environment_variables(self):
        """Test setting environment variables from configuration."""
        config = {
            'plexus': {
                'api_url': 'https://test.com',
                'api_key': 'test-key',
                'working_directory': '/tmp/test'
            },
            'aws': {
                'region_name': 'us-west-2'
            },
            'openai': {
                'api_key': 'openai-key'
            }
        }
        
        with patch.object(self.loader, '_change_working_directory', return_value=True):
            env_vars_set = self.loader._set_environment_variables(config)
        
        # Check environment variables were set
        assert os.environ.get('PLEXUS_API_URL') == 'https://test.com'
        assert os.environ.get('PLEXUS_API_KEY') == 'test-key'
        assert os.environ.get('AWS_REGION_NAME') == 'us-west-2'
        assert os.environ.get('OPENAI_API_KEY') == 'openai-key'
        
        # Expected: 4 env vars + 1 working directory = 5 total
        assert env_vars_set == 5
    
    def test_set_environment_variables_no_working_dir_change(self):
        """Test setting environment variables when working directory change fails."""
        config = {
            'plexus': {
                'api_url': 'https://test.com',
                'working_directory': '/nonexistent'
            }
        }
        
        with patch.object(self.loader, '_change_working_directory', return_value=False):
            env_vars_set = self.loader._set_environment_variables(config)
        
        # Only api_url should be set, working_directory change failed
        assert os.environ.get('PLEXUS_API_URL') == 'https://test.com'
        assert env_vars_set == 1
    
    @patch.object(ConfigLoader, '_load_yaml_file')
    def test_load_config_single_file(self, mock_load_yaml):
        """Test loading configuration from a single file."""
        mock_config = {
            'plexus': {
                'api_url': 'https://test.com',
                'api_key': 'test-key'
            }
        }
        
        # Mock one source as existing
        self.loader.config_sources[0].exists = True
        mock_load_yaml.return_value = mock_config
        
        with patch.object(self.loader, '_set_environment_variables', return_value=2) as mock_set_env:
            result = self.loader.load_config()
        
        assert result == mock_config
        assert self.loader.loaded_config == mock_config
        assert self.loader.env_vars_set == 2
        mock_set_env.assert_called_once_with(mock_config)
    
    @patch.object(ConfigLoader, '_load_yaml_file')
    def test_load_config_multiple_files(self, mock_load_yaml):
        """Test loading and merging configuration from multiple files."""
        # Mock configs for different sources
        cwd_config = {
            'plexus': {
                'api_url': 'https://cwd.com',
                'timeout': 60
            }
        }
        
        home_config = {
            'plexus': {
                'api_url': 'https://home.com',
                'api_key': 'home-key'
            },
            'aws': {
                'region_name': 'us-east-1'
            }
        }
        
        # Mock CWD and home sources as existing
        self.loader.config_sources[0].exists = True  # CWD .plexus/config.yaml
        self.loader.config_sources[2].exists = True  # Home .plexus/config.yaml
        
        # Mock load_yaml_file to return different configs based on path
        def side_effect(path):
            if 'config.yaml' in str(path) and str(Path.cwd()) in str(path):
                return cwd_config
            elif 'config.yaml' in str(path) and str(Path.home()) in str(path):
                return home_config
            else:
                return {}
        
        mock_load_yaml.side_effect = side_effect
        
        with patch.object(self.loader, '_set_environment_variables', return_value=3):
            result = self.loader.load_config()
        
        # Current working directory should override home directory
        assert result['plexus']['api_url'] == 'https://cwd.com'  # CWD wins
        assert result['plexus']['api_key'] == 'home-key'         # From home
        assert result['plexus']['timeout'] == 60                # From CWD
        assert result['aws']['region_name'] == 'us-east-1'      # From home
    
    def test_load_config_no_files(self):
        """Test loading configuration when no files exist."""
        # Mock no sources as existing
        for source in self.loader.config_sources:
            source.exists = False
        
        result = self.loader.load_config()
        
        assert result == {}
        assert self.loader.loaded_config == {}
        assert self.loader.env_vars_set == 0
    
    def test_get_config_value(self):
        """Test getting configuration values after loading."""
        self.loader.loaded_config = {
            'plexus': {
                'api_url': 'https://test.com',
                'nested': {
                    'value': 'found'
                }
            }
        }
        
        assert self.loader.get_config_value('plexus.api_url') == 'https://test.com'
        assert self.loader.get_config_value('plexus.nested.value') == 'found'
        assert self.loader.get_config_value('nonexistent') is None
        assert self.loader.get_config_value('nonexistent', 'default') == 'default'
    
    def test_get_available_sources(self):
        """Test getting available configuration sources."""
        # Mock only the first source as existing, all others as not existing
        for i, source in enumerate(self.loader.config_sources):
            source.exists = (i == 0)
        
        available = self.loader.get_available_sources()
        
        assert len(available) == 1
        assert str(self.loader.config_sources[0].path) in available[0]
    
    def test_environment_variable_precedence(self):
        """Test that environment variables take precedence over YAML config."""
        # Clear environment first, then set a specific variable
        self._clear_plexus_env_vars()
        os.environ['PLEXUS_API_URL'] = 'https://env-override.com'
        
        config = {
            'plexus': {
                'api_url': 'https://yaml-config.com',
                'api_key': 'yaml-key'
            }
        }
        
        env_vars_set = self.loader._set_environment_variables(config)
        
        # Environment variable should not be overridden
        assert os.environ.get('PLEXUS_API_URL') == 'https://env-override.com'
        # New variable should be set from YAML
        assert os.environ.get('PLEXUS_API_KEY') == 'yaml-key'
        # Only one env var should be counted as "set" (the one not already in env)
        assert env_vars_set == 1
    
    def test_yaml_vs_yml_extension_precedence(self):
        """Test that .yaml extension takes precedence over .yml in same directory."""
        yaml_config = {
            'plexus': {
                'api_url': 'https://yaml-file.com'
            }
        }
        
        yml_config = {
            'plexus': {
                'api_url': 'https://yml-file.com'
            }
        }
        
        # Mock both files as existing in CWD
        self.loader.config_sources[0].exists = True  # plexus.yaml in CWD
        self.loader.config_sources[1].exists = True  # plexus.yml in CWD
        
        def mock_load_yaml(path):
            if str(path).endswith('.yaml'):
                return yaml_config
            elif str(path).endswith('.yml'):
                return yml_config
            return {}
        
        with patch.object(self.loader, '_load_yaml_file', side_effect=mock_load_yaml):
            with patch.object(self.loader, '_set_environment_variables', return_value=1):
                result = self.loader.load_config()
        
        # .yaml should take precedence over .yml
        assert result['plexus']['api_url'] == 'https://yaml-file.com'
    
    def test_current_directory_vs_home_directory_precedence(self):
        """Test that current directory config takes precedence over home directory."""
        cwd_config = {
            'plexus': {
                'api_url': 'https://cwd.com',
                'timeout': 30
            }
        }
        
        home_config = {
            'plexus': {
                'api_url': 'https://home.com',
                'api_key': 'home-key'
            }
        }
        
        # Mock CWD .yaml and home .yaml as existing
        self.loader.config_sources[0].exists = True  # CWD .plexus/config.yaml
        self.loader.config_sources[2].exists = True  # Home .plexus/config.yaml
        
        def mock_load_yaml(path):
            if 'config.yaml' in str(path) and str(Path.cwd()) in str(path):
                return cwd_config
            elif '.plexus' in str(path) and str(Path.home()) in str(path):
                return home_config
            return {}
        
        with patch.object(self.loader, '_load_yaml_file', side_effect=mock_load_yaml):
            with patch.object(self.loader, '_set_environment_variables', return_value=2):
                result = self.loader.load_config()
        
        # CWD should override home for api_url
        assert result['plexus']['api_url'] == 'https://cwd.com'
        # CWD-only values should be preserved
        assert result['plexus']['timeout'] == 30
        # Home-only values should be preserved
        assert result['plexus']['api_key'] == 'home-key'
    
    def test_load_yaml_file_yml_extension(self):
        """Test loading YAML configuration files with .yml extension."""
        test_config = {
            'plexus': {
                'api_url': 'https://test.com',
                'api_key': 'test-key'
            }
        }
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yml', delete=False) as f:
            yaml.dump(test_config, f)
            temp_path = Path(f.name)
        
        try:
            loaded = self.loader._load_yaml_file(temp_path)
            assert loaded == test_config
        finally:
            temp_path.unlink()
    
    def test_missing_config_files(self):
        """Test behavior when no config files exist."""
        # Mock all sources as non-existent
        for source in self.loader.config_sources:
            source.exists = False
        
        result = self.loader.load_config()
        
        assert result == {}
        assert self.loader.loaded_config == {}
        assert self.loader.env_vars_set == 0


class TestLoadConfigFunction:
    """Test the convenience load_config function."""
    
    def setup_method(self):
        """Set up test fixtures."""
        # Store original environment to restore later
        self.original_env = dict(os.environ)
    
    def teardown_method(self):
        """Clean up after tests."""
        # Restore original environment
        os.environ.clear()
        os.environ.update(self.original_env)
    
    @patch.object(ConfigLoader, 'load_config')
    def test_load_config_function(self, mock_load_config):
        """Test the convenience load_config function."""
        mock_config = {'test': 'config'}
        mock_load_config.return_value = mock_config
        
        result = load_config()
        
        assert result == mock_config
        mock_load_config.assert_called_once()


class TestEnvironmentVariableMapping:
    """Test environment variable mapping completeness."""
    
    def test_env_var_mapping_completeness(self):
        """Test that all important environment variables are mapped."""
        loader = ConfigLoader()
        
        # Check that core Plexus variables are mapped
        core_vars = [
            'PLEXUS_API_URL', 'PLEXUS_API_KEY', 'PLEXUS_ACCOUNT_KEY',
            'AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION_NAME',
            'OPENAI_API_KEY', 'CELERY_QUEUE_NAME'
        ]
        
        mapped_env_vars = set(loader.ENV_VAR_MAPPING.values())
        
        for var in core_vars:
            assert var in mapped_env_vars, f"Core environment variable {var} not mapped"
    
    def test_yaml_key_format(self):
        """Test that YAML keys follow consistent naming conventions."""
        loader = ConfigLoader()
        
        for yaml_key in loader.ENV_VAR_MAPPING.keys():
            # Should not start with underscore (except special cases)
            if not yaml_key.startswith('_'):
                # Should use dot notation for nesting
                assert '.' in yaml_key or yaml_key in ['environment', 'debug'], \
                    f"YAML key {yaml_key} should use dot notation for nesting"