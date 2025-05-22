import os
import subprocess
import sys
from unittest.mock import ANY, MagicMock, mock_open, patch

import pytest

from shared.scripts.generate_sql import check_migrations, generate_sql


def test_check_migrations_with_github_output():
    """Test check_migrations when GITHUB_OUTPUT environment variable is set."""
    mock_env = {"GITHUB_OUTPUT": "/tmp/github_output"}
    mock_file = mock_open()

    with patch.dict(os.environ, mock_env), patch("builtins.open", mock_file), patch(
        "subprocess.run"
    ) as mock_run:

        mock_run.return_value.stdout = "migrations/001_initial.py\nother_file.txt\n"
        mock_run.return_value.returncode = 0

        check_migrations()

        mock_file().write.assert_called_with("has_migrations=true\n")


def test_check_migrations_without_github_output():
    """Test check_migrations without GITHUB_OUTPUT (local development)."""
    with patch.dict(os.environ, {}, clear=True), patch("subprocess.run") as mock_run, patch(
        "logging.Logger.info"
    ) as mock_log, patch("builtins.print") as mock_print:

        mock_run.return_value.stdout = "migrations/001_initial.py\nother_file.txt\n"
        mock_run.return_value.returncode = 0

        check_migrations()

        mock_print.assert_called_with("has_migrations=true")
        mock_log.assert_called_with("Found migrations: True")


def test_check_migrations_custom_path():
    """Test check_migrations with custom migration path."""
    with patch.dict(os.environ, {}, clear=True), patch("subprocess.run") as mock_run, patch(
        "builtins.print"
    ) as mock_print:

        mock_run.return_value.stdout = "custom_path/001_initial.py\nother_file.txt\n"
        mock_run.return_value.returncode = 0

        check_migrations(migration_path="custom_path")

        mock_print.assert_called_with("has_migrations=true")


def test_check_migrations_no_changes():
    """Test check_migrations with no migration changes."""
    with patch.dict(os.environ, {}, clear=True), patch("subprocess.run") as mock_run, patch(
        "builtins.print"
    ) as mock_print:

        mock_run.return_value.stdout = "other_file.txt\n"
        mock_run.return_value.returncode = 0

        check_migrations()

        mock_print.assert_called_with("has_migrations=false")


def test_check_migrations_error():
    """Test error handling in check_migrations."""
    with patch("subprocess.run", side_effect=subprocess.CalledProcessError(1, "cmd")), patch(
        "logging.Logger.error"
    ) as mock_log:

        with pytest.raises(SystemExit):
            check_migrations()

        mock_log.assert_called_once()


def test_generate_sql_success():
    """Test successful SQL generation."""
    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run, patch(
        "builtins.open", mock_open()
    ), patch("logging.Logger.info") as mock_log:

        generate_sql("postgresql", "migrations/alembic.ini")

        # Check if subprocess.run was called with the correct command
        assert mock_run.call_count == 1

        # Extract the arguments from the actual call
        args, kwargs = mock_run.call_args

        # Check that the command is correct
        assert args[0] == [
            "alembic",
            "-c",
            "migrations/alembic.ini",
            "upgrade",
            "head",
            "--sql",
        ]

        # Check that check=True was passed
        assert kwargs.get("check") == True

        # Check that env contains ALEMBIC_DIALECT with the correct value
        assert "env" in kwargs
        assert "ALEMBIC_DIALECT" in kwargs["env"]
        assert kwargs["env"]["ALEMBIC_DIALECT"] == "postgresql"

        assert mock_log.call_count >= 2


def test_generate_sql_with_custom_options():
    """Test SQL generation with custom options."""
    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run, patch(
        "builtins.open", mock_open()
    ):

        generate_sql(
            dialect="mysql",
            alembic_ini="custom/alembic.ini",
            migration_path="custom_migrations",
            range_option="base:head",
        )

        # Check if subprocess.run was called with the correct command
        assert mock_run.call_count == 1

        # Extract the arguments from the actual call
        args, kwargs = mock_run.call_args

        # Check that the command is correct
        assert args[0] == [
            "alembic",
            "-c",
            "custom/alembic.ini",
            "upgrade",
            "base:head",
            "--sql",
        ]

        # Check that check=True was passed
        assert kwargs.get("check") == True

        # Check that env contains ALEMBIC_DIALECT with the correct value
        assert "env" in kwargs
        assert "ALEMBIC_DIALECT" in kwargs["env"]
        assert kwargs["env"]["ALEMBIC_DIALECT"] == "mysql"


def test_generate_sql_missing_alembic_ini():
    """Test error when alembic.ini is missing."""
    with patch("os.path.exists", return_value=False), patch("logging.Logger.error") as mock_log:

        with pytest.raises(SystemExit):
            generate_sql("postgresql", "migrations/alembic.ini")

        mock_log.assert_called_with("Error: alembic.ini not found at migrations/alembic.ini")


def test_generate_sql_subprocess_error():
    """Test error handling when subprocess fails."""
    error = subprocess.CalledProcessError(1, "cmd")

    with patch("os.path.exists", return_value=True), patch(
        "subprocess.run", side_effect=error
    ), patch("logging.Logger.error") as mock_log:

        with pytest.raises(SystemExit):
            generate_sql("postgresql", "migrations/alembic.ini")

        mock_log.assert_called_with(f"Error generating SQL: {error}")


def test_generate_sql_with_nonexistent_revision():
    """Test handling of specific revisions that don't exist in migration history."""
    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run, patch(
        "builtins.open", mock_open()
    ), patch("logging.Logger.warning") as mock_warning, patch("logging.Logger.error") as mock_error:

        # Mock the subprocess calls to simulate revision not found scenario
        def subprocess_side_effect(command, **kwargs):
            if "history" in command:
                # Simulate "alembic history" failing for nonexistent revision
                raise subprocess.CalledProcessError(255, command)
            elif "show" in command:
                # Simulate "alembic show" also failing for nonexistent revision
                raise subprocess.CalledProcessError(255, command)
            else:
                # For other commands, return success
                mock_result = MagicMock()
                mock_result.stdout = "-- Sample SQL output\n"
                return mock_result

        mock_run.side_effect = subprocess_side_effect

        # Call generate_sql with a specific revision that doesn't exist
        generate_sql(
            dialect="postgresql",
            alembic_ini="migrations/alembic.ini",
            specific_revisions=["34d7a17ebdd5"],
        )

        # Verify that warning and error messages were logged appropriately
        mock_warning.assert_called()
        mock_error.assert_called_with("Revision 34d7a17ebdd5 does not exist. Skipping.")


def test_generate_sql_with_pr_migrations():
    """Test generating SQL using PR migration parsing."""
    from shared.scripts.alembic_utils import MigrationInfo

    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run, patch(
        "builtins.open", mock_open()
    ) as mock_file, patch("shared.scripts.generate_sql.MigrationManager") as mock_manager_class:

        # Create mock manager instance
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        # Mock PR migrations
        mock_migrations = {
            "abc123": MigrationInfo("abc123", "migrations/versions/001_test.py", None),
            "def456": MigrationInfo("def456", "migrations/versions/002_test.py", "abc123"),
        }
        mock_manager.get_migrations_from_pr.return_value = mock_migrations
        mock_manager.get_migration_order.return_value = ["abc123", "def456"]

        # Mock successful subprocess calls
        mock_result = MagicMock()
        mock_result.stdout = "-- SQL content here --\n"
        mock_run.return_value = mock_result

        generate_sql(
            dialect="postgresql",
            alembic_ini="migrations/alembic.ini",
            specific_revisions=["abc123", "def456"],
        )

        # Verify that MigrationManager was instantiated correctly
        mock_manager_class.assert_called_once_with("migrations", None)

        # Verify that get_migrations_from_pr was called
        mock_manager.get_migrations_from_pr.assert_called()

        # Verify that get_migration_order was called with the right migrations
        mock_manager.get_migration_order.assert_called_once_with(mock_migrations)

        # Verify subprocess calls for each migration
        assert mock_run.call_count == 2

        # Check first migration call (base:abc123)
        first_call = mock_run.call_args_list[0]
        assert first_call[0][0] == [
            "alembic",
            "-c",
            "migrations/alembic.ini",
            "upgrade",
            "base:abc123",
            "--sql",
        ]

        # Check second migration call (abc123:def456)
        second_call = mock_run.call_args_list[1]
        assert second_call[0][0] == [
            "alembic",
            "-c",
            "migrations/alembic.ini",
            "upgrade",
            "abc123:def456",
            "--sql",
        ]


def test_generate_sql_with_merge_migration():
    """Test generating SQL for merge migrations."""
    from shared.scripts.alembic_utils import MigrationInfo

    with patch("os.path.exists", return_value=True), patch("subprocess.run") as mock_run, patch(
        "builtins.open", mock_open()
    ) as mock_file, patch("shared.scripts.generate_sql.MigrationManager") as mock_manager_class:

        # Create mock manager instance
        mock_manager = MagicMock()
        mock_manager_class.return_value = mock_manager

        # Mock merge migration
        mock_migrations = {
            "merge123": MigrationInfo(
                "merge123", "migrations/versions/003_merge.py", ["abc123", "def456"]
            ),
        }
        mock_manager.get_migrations_from_pr.return_value = mock_migrations
        mock_manager.get_migration_order.return_value = ["merge123"]

        # Mock successful subprocess calls
        mock_result = MagicMock()
        mock_result.stdout = "-- Merge SQL content --\n"
        mock_run.return_value = mock_result

        generate_sql(
            dialect="postgresql",
            alembic_ini="migrations/alembic.ini",
            specific_revisions=["merge123"],
        )

        # Verify subprocess call uses base:merge123 for merge migrations
        mock_run.assert_called_once()
        call_args = mock_run.call_args_list[0]
        assert call_args[0][0] == [
            "alembic",
            "-c",
            "migrations/alembic.ini",
            "upgrade",
            "base:merge123",
            "--sql",
        ]

        # Since we're not actually writing files during pytest, we verify the manager was called
        mock_manager.get_migrations_from_pr.assert_called()
        mock_manager.get_migration_order.assert_called_once_with(mock_migrations)
