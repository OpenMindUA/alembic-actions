import os
import subprocess
import sys
from unittest.mock import MagicMock, mock_open, patch, ANY

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
