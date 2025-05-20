"""
Utility functions for working with Alembic migrations.
"""

import logging
import os
import subprocess
import sys
from typing import List, Optional, Tuple

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def get_current_revision(alembic_ini: str) -> str:
    """
    Get the current revision of the database.

    Args:
        alembic_ini: Path to alembic.ini file

    Returns:
        The current revision or "None" if no revision
    """
    if not os.path.exists(alembic_ini):
        logger.error(f"Error: alembic.ini not found at {alembic_ini}")
        return "None"

    try:
        result = subprocess.run(
            ["alembic", "-c", alembic_ini, "current"], capture_output=True, text=True, check=True
        )
        # Parse the output to extract the revision ID
        output = result.stdout
        if "head" in output:
            # Extract the revision ID from output
            for line in output.splitlines():
                if line.strip().startswith("Rev:"):
                    return line.split(":")[1].strip().split(" ")[0]
        return "None"
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting current revision: {e}")
        return "None"


def get_migration_history(alembic_ini: str) -> List[Tuple[str, str]]:
    """
    Get the migration history as a list of (key, value) tuples.

    Args:
        alembic_ini: Path to alembic.ini file

    Returns:
        List of tuples containing revision information
    """
    if not os.path.exists(alembic_ini):
        logger.error(f"Error: alembic.ini not found at {alembic_ini}")
        return []

    try:
        result = subprocess.run(
            ["alembic", "-c", alembic_ini, "history"], capture_output=True, text=True, check=True
        )

        # Extract revision information from lines like "Rev: abcd123 (head): add users table"
        history = []
        current_rev = None

        for line in result.stdout.splitlines():
            if line.startswith("Rev:"):
                current_rev = line.strip()
                if ":" in current_rev:
                    parts = current_rev.split(":", 1)
                    if len(parts) == 2:
                        history.append(("Rev", parts[1].strip()))

        return history
    except subprocess.CalledProcessError as e:
        logger.error(f"Error getting migration history: {e}")
        return []


def validate_migrations(alembic_ini: str, dialect: str) -> bool:
    """
    Validates migrations by checking if they can be compiled to SQL.

    Args:
        alembic_ini: Path to alembic.ini file
        dialect: SQL dialect to use

    Returns:
        True if all migrations are valid, False otherwise
    """
    if not os.path.exists(alembic_ini):
        logger.error(f"Error: alembic.ini not found at {alembic_ini}")
        return False

    try:
        # Try to generate SQL - if it fails, migrations are invalid
        result = subprocess.run(
            ["alembic", "-c", alembic_ini, "upgrade", "head", "--sql", f"--dialect={dialect}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"Error validating migrations: {e}")
        logger.error(f"Error details: {e.stderr}")
        return False


def backup_database(dialect: str, database_url: str, backup_path: Optional[str] = None) -> bool:
    """
    Creates a backup of the database.

    Args:
        dialect: Database dialect (postgresql, mysql, etc.)
        database_url: URL of the database to backup
        backup_path: Path to save the backup (optional)

    Returns:
        True if backup was successful, False otherwise
    """
    if backup_path is None:
        # Create a timestamped backup path if none provided
        import datetime

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = f"backup_{timestamp}.sql"

    logger.info(f"Creating database backup at {backup_path}")

    try:
        if dialect == "postgresql":
            # Extract connection details from database_url
            # Example: postgresql://user:pass@localhost:5432/dbname
            import re

            match = re.match(r"postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)", database_url)
            if match:
                user, password, host, port, dbname = match.groups()

                # Set environment variables for password
                env = os.environ.copy()
                env["PGPASSWORD"] = password

                # Run pg_dump
                result = subprocess.run(
                    ["pg_dump", "-h", host, "-p", port, "-U", user, "-f", backup_path, dbname],
                    env=env,
                    check=True,
                )
                return True

        elif dialect == "mysql":
            # Similar implementation for MySQL
            # ...
            pass

        logger.error(f"Backup not implemented for dialect: {dialect}")
        return False

    except subprocess.CalledProcessError as e:
        logger.error(f"Error backing up database: {e}")
        return False
    except Exception as e:
        logger.error(f"Unexpected error during backup: {e}")
        return False
