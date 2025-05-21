"""
Utility functions for working with Alembic migrations.
"""

import ast
import logging
import os
import re
import subprocess
import sys
from typing import Dict, List, Optional, Set, Tuple, Union

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


class MigrationInfo:
    """Represents information about a single migration file."""

    def __init__(
        self, revision: str, file_path: str, down_revision: Optional[Union[str, List[str]]] = None
    ):
        self.revision = revision
        self.file_path = file_path
        self.down_revision = down_revision

    @property
    def is_merge(self) -> bool:
        """Check if this is a merge migration (has multiple down_revisions)."""
        return isinstance(self.down_revision, list) and len(self.down_revision) > 1

    @property
    def is_initial(self) -> bool:
        """Check if this is an initial migration (no down_revision)."""
        return self.down_revision is None or (
            isinstance(self.down_revision, list) and not self.down_revision
        )

    def get_down_revisions(self) -> List[str]:
        """Get list of down revisions (empty list if None)."""
        if self.down_revision is None:
            return []
        elif isinstance(self.down_revision, str):
            return [self.down_revision]
        else:
            return list(self.down_revision)

    def __repr__(self) -> str:
        """String representation for debugging."""
        return f"MigrationInfo(revision='{self.revision}', down_revision={self.down_revision}, is_merge={self.is_merge})"


def _parse_revision_from_ast(
    tree: ast.AST,
) -> Tuple[Optional[str], Optional[Union[str, List[str]]]]:
    """Extract revision info from AST."""
    revision = None
    down_revision = None

    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    if target.id == "revision":
                        if isinstance(node.value, ast.Constant):
                            revision = node.value.value
                    elif target.id == "down_revision":
                        if isinstance(node.value, ast.Constant):
                            down_revision = node.value.value
                        elif isinstance(node.value, (ast.Tuple, ast.List)):
                            # Handle tuple/list of revisions (merge migrations)
                            down_revisions = []
                            for elt in node.value.elts:
                                if isinstance(elt, ast.Constant) and elt.value:
                                    down_revisions.append(elt.value)
                            down_revision = down_revisions if down_revisions else None

    return revision, down_revision


def _parse_down_revision_from_regex(content: str) -> Optional[Union[str, List[str]]]:
    """Parse down_revision using regex patterns."""
    # Look for down_revision variable assignment
    down_rev_match = re.search(r"^down_revision\s*=\s*(.+)", content, re.MULTILINE)
    if down_rev_match:
        down_rev_value = down_rev_match.group(1).strip()

        if down_rev_value == "None":
            return None
        elif down_rev_value.startswith('"') or down_rev_value.startswith("'"):
            # Single revision string
            return down_rev_value.strip("\"'")
        elif down_rev_value.startswith("(") or down_rev_value.startswith("["):
            # Tuple or list of revisions (merge migration)
            rev_matches = re.findall(r'["\']([a-f0-9]+)["\']', down_rev_value)
            return rev_matches if rev_matches else None

    # Try comment format "Revises: xxx"
    revises_match = re.search(r"^Revises:\s*(.+)", content, re.MULTILINE)
    if revises_match:
        revises_value = revises_match.group(1).strip()
        if revises_value and revises_value != "":
            # Check if it's a tuple format like "('abc', 'def')"
            if "(" in revises_value and ")" in revises_value:
                rev_matches = re.findall(r'["\']([a-f0-9]+)["\']', revises_value)
                if len(rev_matches) > 1:
                    return rev_matches
                elif len(rev_matches) == 1:
                    return str(rev_matches[0])
                else:
                    # Fallback: try unquoted hex IDs
                    rev_matches = re.findall(r"([a-f0-9]{12,})", revises_value)
                    if rev_matches:
                        return rev_matches if len(rev_matches) > 1 else str(rev_matches[0])
            else:
                return str(revises_value)

    return None


def parse_migration_file(file_path: str) -> Optional[MigrationInfo]:
    """
    Parse an Alembic migration file to extract revision information.

    Args:
        file_path: Path to the migration file

    Returns:
        MigrationInfo object or None if parsing failed
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Try to parse using AST for variable assignments
        try:
            tree = ast.parse(content)
            revision, down_revision = _parse_revision_from_ast(tree)
            if revision:
                return MigrationInfo(revision, file_path, down_revision)
        except SyntaxError:
            logger.debug(f"Failed to parse {file_path} with AST, trying regex fallback")

        # Fallback to regex parsing
        revision_match = re.search(r'^revision\s*=\s*["\']([^"\']+)["\']', content, re.MULTILINE)
        if not revision_match:
            # Try comment format "Revision ID: xxx"
            revision_match = re.search(r"^Revision ID:\s*([a-f0-9]+)", content, re.MULTILINE)

        if not revision_match:
            logger.warning(f"Could not find revision in {file_path}")
            return None

        revision = revision_match.group(1)
        down_revision = _parse_down_revision_from_regex(content)

        return MigrationInfo(revision, file_path, down_revision)

    except Exception as e:
        logger.error(f"Error parsing migration file {file_path}: {e}")
        return None


class MigrationManager:
    """Manages Alembic migrations for a project."""

    def __init__(self, migration_path: str = "migrations"):
        self.migration_path = migration_path
        self._migrations_cache: Optional[Dict[str, MigrationInfo]] = None

    def get_migrations_from_pr(self) -> Dict[str, MigrationInfo]:
        """Get migration information for all migrations in the current PR."""
        if self._migrations_cache is not None:
            return self._migrations_cache

        try:
            # Get changed files from git
            result = subprocess.run(
                ["git", "diff", "--name-only", "origin/main...HEAD"],
                capture_output=True,
                text=True,
                check=True,
            )

            changed_files = result.stdout.splitlines()
            migration_files = [
                file
                for file in changed_files
                if file.startswith(f"{self.migration_path}/") and file.endswith(".py")
            ]

            migrations = {}
            for file_path in migration_files:
                if os.path.exists(file_path):
                    migration_info = parse_migration_file(file_path)
                    if migration_info:
                        migrations[migration_info.revision] = migration_info

            self._migrations_cache = migrations
            return migrations

        except (subprocess.CalledProcessError, Exception) as e:
            logger.error(f"Error getting PR migrations: {e}")
            return {}

    def build_dependency_graph(
        self, migrations: Optional[Dict[str, MigrationInfo]] = None
    ) -> Dict[str, List[str]]:
        """Build a dependency graph showing which migrations depend on others."""
        if migrations is None:
            migrations = self.get_migrations_from_pr()

        dependency_graph: Dict[str, List[str]] = {}

        for revision, migration in migrations.items():
            # Initialize entry for this revision
            if revision not in dependency_graph:
                dependency_graph[revision] = []

            # Add dependencies
            for down_rev in migration.get_down_revisions():
                if down_rev not in dependency_graph:
                    dependency_graph[down_rev] = []
                dependency_graph[down_rev].append(revision)

        return dependency_graph

    def get_migration_order(
        self, migrations: Optional[Dict[str, MigrationInfo]] = None
    ) -> List[str]:
        """Get the correct order to apply migrations based on their dependencies."""
        if migrations is None:
            migrations = self.get_migrations_from_pr()

        if not migrations:
            return []

        # Build dependency graph
        dependency_graph = self.build_dependency_graph(migrations)

        # Find root migrations (those with no down_revision or down_revision not in PR)
        roots = []
        for revision, migration in migrations.items():
            down_revs = migration.get_down_revisions()
            if not down_revs or not any(dr in migrations for dr in down_revs):
                roots.append(revision)

        # Topological sort
        ordered = []
        visited = set()

        def visit(revision: str):
            if revision in visited or revision not in migrations:
                return
            visited.add(revision)

            # Visit dependencies first
            for down_rev in migrations[revision].get_down_revisions():
                if down_rev in migrations:
                    visit(down_rev)

            ordered.append(revision)

        # Start from roots
        for root in sorted(roots):  # Sort for consistent ordering
            visit(root)

        # Visit any remaining nodes (in case of cycles or disconnected components)
        for revision in sorted(migrations.keys()):
            visit(revision)

        return ordered

    def get_merge_migrations(
        self, migrations: Optional[Dict[str, MigrationInfo]] = None
    ) -> List[MigrationInfo]:
        """Get all merge migrations from the set."""
        if migrations is None:
            migrations = self.get_migrations_from_pr()

        return [migration for migration in migrations.values() if migration.is_merge]

    def get_initial_migrations(
        self, migrations: Optional[Dict[str, MigrationInfo]] = None
    ) -> List[MigrationInfo]:
        """Get all initial migrations from the set."""
        if migrations is None:
            migrations = self.get_migrations_from_pr()

        return [migration for migration in migrations.values() if migration.is_initial]


# Backward compatibility functions
def get_migrations_from_pr(migration_path: str = "migrations") -> Dict[str, MigrationInfo]:
    """Get migration information for all migrations in the current PR."""
    manager = MigrationManager(migration_path)
    return manager.get_migrations_from_pr()


def build_migration_dependency_graph(migrations: Dict[str, MigrationInfo]) -> Dict[str, List[str]]:
    """Build a dependency graph showing which migrations depend on others."""
    manager = MigrationManager()
    return manager.build_dependency_graph(migrations)


def get_migration_order(migrations: Dict[str, MigrationInfo]) -> List[str]:
    """Get the correct order to apply migrations based on their dependencies."""
    manager = MigrationManager()
    return manager.get_migration_order(migrations)
