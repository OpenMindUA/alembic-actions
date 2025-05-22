"""
Tests for multi-database functionality in alembic_utils.
"""

import os
import tempfile
import unittest
from unittest.mock import patch

from ..scripts.alembic_utils import (
    get_databases_from_config,
    resolve_database_name,
    get_databases_for_deploy,
)


class TestMultiDatabase(unittest.TestCase):
    """Test multi-database configuration parsing and resolution."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_files = []

    def tearDown(self):
        """Clean up temporary files."""
        for temp_file in self.temp_files:
            if os.path.exists(temp_file):
                os.unlink(temp_file)

    def create_temp_ini(self, content: str) -> str:
        """Create a temporary alembic.ini file with given content."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.ini', delete=False) as f:
            f.write(content)
            temp_path = f.name
        self.temp_files.append(temp_path)
        return temp_path

    def test_get_databases_from_config_explicit(self):
        """Test database detection from explicit 'databases' setting."""
        ini_content = """
[alembic]
databases = main, auth, logs

[main]
sqlalchemy.url = postgresql://user:pass@localhost/main_db

[auth]
sqlalchemy.url = postgresql://user:pass@localhost/auth_db

[logs]
sqlalchemy.url = postgresql://user:pass@localhost/logs_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        databases = get_databases_from_config(ini_path)
        self.assertEqual(databases, ['main', 'auth', 'logs'])

    def test_get_databases_from_config_sections(self):
        """Test database detection from sections with sqlalchemy.url."""
        ini_content = """
[alembic]
script_location = migrations

[main]
sqlalchemy.url = postgresql://user:pass@localhost/main_db

[auth]
sqlalchemy.url = postgresql://user:pass@localhost/auth_db

[some_other_section]
other_setting = value
"""
        ini_path = self.create_temp_ini(ini_content)
        
        databases = get_databases_from_config(ini_path)
        self.assertEqual(set(databases), {'main', 'auth'})

    def test_get_databases_from_config_single_db(self):
        """Test single database configuration (no multi-DB setup)."""
        ini_content = """
[alembic]
script_location = migrations
sqlalchemy.url = postgresql://user:pass@localhost/single_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        databases = get_databases_from_config(ini_path)
        self.assertEqual(databases, [])

    def test_resolve_database_name_explicit(self):
        """Test database name resolution with explicit database specified."""
        ini_content = """
[alembic]
databases = main, auth

[main]
sqlalchemy.url = postgresql://user:pass@localhost/main_db

[auth]
sqlalchemy.url = postgresql://user:pass@localhost/auth_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        resolved = resolve_database_name(ini_path, 'auth')
        self.assertEqual(resolved, 'auth')

    def test_resolve_database_name_auto_select(self):
        """Test database name resolution with auto-selection."""
        ini_content = """
[alembic]
databases = main, auth

[main]
sqlalchemy.url = postgresql://user:pass@localhost/main_db

[auth]
sqlalchemy.url = postgresql://user:pass@localhost/auth_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        resolved = resolve_database_name(ini_path, None)
        self.assertEqual(resolved, 'main')  # First database

    def test_resolve_database_name_single_db(self):
        """Test database name resolution for single database setup."""
        ini_content = """
[alembic]
script_location = migrations
sqlalchemy.url = postgresql://user:pass@localhost/single_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        resolved = resolve_database_name(ini_path, None)
        self.assertIsNone(resolved)

    def test_resolve_database_name_invalid(self):
        """Test database name resolution with invalid database name."""
        ini_content = """
[alembic]
databases = main, auth

[main]
sqlalchemy.url = postgresql://user:pass@localhost/main_db

[auth]
sqlalchemy.url = postgresql://user:pass@localhost/auth_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        with self.assertRaises(ValueError):
            resolve_database_name(ini_path, 'nonexistent')

    def test_get_databases_for_deploy_all(self):
        """Test getting all databases for deploy operation."""
        ini_content = """
[alembic]
databases = main, auth, logs

[main]
sqlalchemy.url = postgresql://user:pass@localhost/main_db

[auth]
sqlalchemy.url = postgresql://user:pass@localhost/auth_db

[logs]
sqlalchemy.url = postgresql://user:pass@localhost/logs_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        databases = get_databases_for_deploy(ini_path, None)
        self.assertEqual(databases, ['main', 'auth', 'logs'])

    def test_get_databases_for_deploy_specific(self):
        """Test getting specific database for deploy operation."""
        ini_content = """
[alembic]
databases = main, auth, logs

[main]
sqlalchemy.url = postgresql://user:pass@localhost/main_db

[auth]
sqlalchemy.url = postgresql://user:pass@localhost/auth_db

[logs]
sqlalchemy.url = postgresql://user:pass@localhost/logs_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        databases = get_databases_for_deploy(ini_path, 'auth')
        self.assertEqual(databases, ['auth'])

    def test_get_databases_for_deploy_single_db(self):
        """Test getting databases for deploy with single database setup."""
        ini_content = """
[alembic]
script_location = migrations
sqlalchemy.url = postgresql://user:pass@localhost/single_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        databases = get_databases_for_deploy(ini_path, None)
        self.assertEqual(databases, [])

    @patch('shared.scripts.alembic_utils.logger')
    def test_logging_behavior(self, mock_logger):
        """Test that appropriate logging messages are generated."""
        ini_content = """
[alembic]
databases = main, auth

[main]
sqlalchemy.url = postgresql://user:pass@localhost/main_db

[auth]
sqlalchemy.url = postgresql://user:pass@localhost/auth_db
"""
        ini_path = self.create_temp_ini(ini_content)
        
        # Test auto-selection logging
        resolve_database_name(ini_path, None)
        mock_logger.info.assert_called()


if __name__ == '__main__':
    unittest.main()