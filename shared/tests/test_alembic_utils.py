"""
Tests for alembic_utils.py
"""

import os
import subprocess
from unittest.mock import MagicMock, mock_open, patch

import pytest

from shared.scripts.alembic_utils import (
    backup_database,
    get_current_revision,
    get_migration_history,
    validate_migrations,
)


def test_get_current_revision():
    """Test getting current database revision."""
    mock_output = "Current revision for xxxxxx: abcd123 (head)\n  Rev: abcd123 (head)\n  Parent: None\n  Path: xxx/migrations/versions/file.py\n"

    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run:

        mock_run.return_value.stdout = mock_output
        mock_run.return_value.returncode = 0

        result = get_current_revision("test/alembic.ini")
        assert result == "abcd123"

        mock_run.assert_called_with(
            ["alembic", "-c", "test/alembic.ini", "current"],
            capture_output=True,
            text=True,
            check=True,
        )


def test_get_current_revision_none():
    """Test when no current revision exists."""
    mock_output = "Current revision for xxxxx: None\n"

    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run:

        mock_run.return_value.stdout = mock_output
        mock_run.return_value.returncode = 0

        result = get_current_revision("test/alembic.ini")
        assert result == "None"


def test_get_current_revision_file_not_found():
    """Test error handling when alembic.ini is not found."""
    with patch("os.path.exists", return_value=False), patch("logging.Logger.error") as mock_log:

        result = get_current_revision("missing/alembic.ini")
        assert result == "None"
        mock_log.assert_called_once()


def test_get_migration_history():
    """Test getting migration history."""
    mock_output = """
Rev: abcd123 (head): add users table
Date: 2023-01-15
Parent: efgh456
Path: migrations/versions/abcd123_add_users_table.py

Rev: efgh456: initial migration
Date: 2023-01-10
Parent: None
Path: migrations/versions/efgh456_initial_migration.py
"""

    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run:

        mock_run.return_value.stdout = mock_output
        mock_run.return_value.returncode = 0

        result = get_migration_history("test/alembic.ini")
        assert len(result) == 2
        assert result[0] == ("Rev", "abcd123 (head): add users table")
        assert result[1] == ("Rev", "efgh456: initial migration")


def test_validate_migrations_success():
    """Test successful migration validation."""
    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run:

        mock_run.return_value.returncode = 0

        result = validate_migrations("test/alembic.ini", "postgresql")
        assert result is True

        mock_run.assert_called_with(
            [
                "alembic",
                "-c",
                "test/alembic.ini",
                "upgrade",
                "head",
                "--sql",
                "--dialect=postgresql",
            ],
            capture_output=True,
            text=True,
            check=True,
        )


def test_validate_migrations_failure():
    """Test failed migration validation."""
    with patch("os.path.exists", return_value=True), patch(
        "subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")
    ), patch("logging.Logger.error") as mock_log:

        result = validate_migrations("test/alembic.ini", "postgresql")
        assert result is False
        assert mock_log.call_count >= 1


def test_backup_database_postgres():
    """Test PostgreSQL database backup."""
    with patch("subprocess.run") as mock_run, patch("os.environ.copy", return_value={}):

        mock_run.return_value.returncode = 0

        result = backup_database(
            "postgresql", "postgresql://user:pass@localhost:5432/testdb", "backup.sql"
        )

        assert result is True
        mock_run.assert_called_once()
        # Verify pg_dump command has correct arguments
        args = mock_run.call_args[0][0]
        assert "pg_dump" in args
        assert "testdb" in args
