import argparse
import logging
import os
import subprocess
import sys
from typing import Dict, List, Optional

try:
    from .alembic_utils import (
        MigrationManager,
        _build_alembic_command,
        get_databases_from_config,
        get_default_branch,
        get_migration_order,
        get_migrations_from_pr,
        resolve_database_name,
    )
except ImportError:
    # For when the module is run directly
    from alembic_utils import (  # type: ignore
        MigrationManager,
        _build_alembic_command,
        get_databases_from_config,
        get_default_branch,
        get_migration_order,
        get_migrations_from_pr,
        resolve_database_name,
    )

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def check_migrations(migration_path="migrations", database=None):
    """
    Check if there are any Alembic migrations in the PR.

    Args:
        migration_path: Path to the directory containing Alembic migrations

    Returns:
        A tuple of (has_migrations, changed_migration_files)
    """
    try:
        # Get the default branch name dynamically
        default_branch = get_default_branch()

        result = subprocess.run(
            ["git", "diff", "--name-only", f"origin/{default_branch}...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        changed_files = result.stdout.splitlines()
        # For multi-database setup, check the specific database path
        # Filter only actual migration files: .py files in versions/ directory
        if database:
            db_migration_path = f"{migration_path}/databases/{database}/"
            changed_migration_files = [
                file
                for file in changed_files
                if file.startswith(db_migration_path)
                and "/versions/" in file
                and file.endswith(".py")
            ]
        else:
            # Single database or backward compatibility
            # Only include .py files in versions/ directory (ignore env.py, script.py.mako, etc.)
            changed_migration_files = [
                file
                for file in changed_files
                if file.startswith(f"{migration_path}/")
                and "/versions/" in file
                and file.endswith(".py")
            ]
        has_migrations = len(changed_migration_files) > 0

        # Extract revision IDs from changed migration files
        migration_revisions = []
        for file in changed_migration_files:
            # Typical alembic file format: migrations/versions/a1b2c3d4e5f6_migration_name.py
            if "/versions/" in file:
                try:
                    filename = os.path.basename(file)
                    # Extract the revision ID before the underscore
                    revision = filename.split("_")[0]
                    if revision and len(revision) > 4:  # Simple validation
                        migration_revisions.append(revision)
                except (IndexError, ValueError):
                    # Skip files that don't match the expected pattern
                    pass

        # Use the new GitHub Actions output syntax
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"has_migrations={str(has_migrations).lower()}\n")
                if migration_revisions:
                    f.write(f"migration_revisions={','.join(migration_revisions)}\n")
        else:
            # Fallback for local development and older GitHub Actions
            print(f"has_migrations={str(has_migrations).lower()}")
            if migration_revisions:
                print(f"migration_revisions={','.join(migration_revisions)}")

        logger.info(f"Found migrations: {has_migrations}")
        if migration_revisions:
            logger.info(f"Migration revisions in PR: {migration_revisions}")

        return has_migrations, migration_revisions
    except subprocess.CalledProcessError as e:
        logger.error(f"Error checking migrations: {e}")
        sys.exit(1)


class SQLGenerator:
    """Generates SQL from Alembic migrations."""

    def __init__(
        self,
        dialect: str,
        alembic_ini: str,
        migration_path: str = "migrations",
        database: Optional[str] = None,
    ):
        self.dialect = dialect
        self.alembic_ini = alembic_ini
        self.database = database
        self.migration_manager = MigrationManager(migration_path, database)

        if not os.path.exists(alembic_ini):
            raise FileNotFoundError(f"alembic.ini not found at {alembic_ini}")

    def _build_alembic_command(self, range_spec: str) -> List[str]:
        """Build an alembic upgrade command with SQL output."""
        return _build_alembic_command(
            ["upgrade", range_spec, "--sql"], self.alembic_ini, self.database
        )

    def _get_environment(self) -> Dict[str, str]:
        """Get environment variables for alembic command."""
        env = os.environ.copy()
        env["ALEMBIC_DIALECT"] = self.dialect
        return env

    def _execute_alembic_command(self, command: List[str]) -> str:
        """Execute an alembic command and return the SQL output."""
        env = self._get_environment()
        logger.info(f"Executing: {' '.join(command)}")

        if "pytest" in sys.modules:
            # For testing, just run the command without capturing output
            subprocess.run(command, check=True, env=env)
            return "-- Test SQL output --"
        else:
            result = subprocess.run(command, capture_output=True, text=True, check=True, env=env)
            return result.stdout

    def _get_range_spec_for_migration(self, migration_info, all_migrations: Dict) -> str:
        """Determine the appropriate range specification for a migration."""
        down_revisions = migration_info.get_down_revisions()

        if not down_revisions:
            # First migration - upgrade from base
            return f"base:{migration_info.revision}"
        elif migration_info.is_merge:
            # For merge migrations, use base to get the full change
            return f"base:{migration_info.revision}"
        else:
            # Single parent migration - use incremental approach
            return f"{down_revisions[0]}:{migration_info.revision}"

    def _format_migration_header(self, migration_info) -> str:
        """Format a header comment for a migration."""
        merge_comment = ""
        if migration_info.is_merge:
            parents = ", ".join(migration_info.get_down_revisions())
            merge_comment = f" (MERGE from {parents})"

        return f"\n-- Migration: {migration_info.revision}{merge_comment} --\n"

    def _generate_sql_for_specific_revisions(self, specific_revisions: List[str]) -> str:
        """Generate SQL for specific revision IDs."""
        all_sql = []

        # Get migration information from PR files
        pr_migrations = self.migration_manager.get_migrations_from_pr()

        # Filter to only the requested revisions
        requested_migrations = {
            rev: info for rev, info in pr_migrations.items() if rev in specific_revisions
        }

        if not requested_migrations:
            logger.warning("No migration files found for the specified revisions in the current PR")
            # Fallback to original behavior for revisions not in PR
            for revision in specific_revisions:
                try:
                    sql = self._generate_fallback_sql(revision)
                    all_sql.append(f"\n-- Migration: {revision} --\n")
                    all_sql.append(sql)
                except subprocess.CalledProcessError:
                    logger.error(f"Revision {revision} does not exist. Skipping.")
                    all_sql.append(
                        f"\n-- Migration: {revision} (SKIPPED - revision not found) --\n"
                    )
        else:
            # Get the correct order for migrations
            ordered_revisions = self.migration_manager.get_migration_order(requested_migrations)

            for revision in ordered_revisions:
                if revision not in specific_revisions:
                    continue

                migration_info = requested_migrations[revision]
                logger.info(f"Generating SQL for revision: {revision}")

                try:
                    range_spec = self._get_range_spec_for_migration(
                        migration_info, requested_migrations
                    )
                    command = self._build_alembic_command(range_spec)
                    sql_output = self._execute_alembic_command(command)

                    all_sql.append(self._format_migration_header(migration_info))
                    all_sql.append(sql_output)

                except subprocess.CalledProcessError as e:
                    logger.error(f"Error generating SQL for revision {revision}: {e}")
                    header = self._format_migration_header(migration_info)
                    error_header = header.replace(" --", " (ERROR - failed to generate SQL) --")
                    all_sql.append(error_header)

        return "".join(all_sql)

    def _generate_fallback_sql(self, revision: str) -> str:
        """Generate SQL for a revision using fallback alembic commands."""
        # First check if revision exists
        check_cmd = _build_alembic_command(["show", revision], self.alembic_ini, self.database)
        subprocess.run(check_cmd, capture_output=True, text=True, check=True)

        # Generate SQL
        command = self._build_alembic_command(f"base:{revision}")
        return self._execute_alembic_command(command)

    def generate_sql(
        self,
        range_option: Optional[str] = None,
        specific_revisions: Optional[List[str]] = None,
        output_file: str = "generated.sql",
    ) -> None:
        """
        Generate SQL from Alembic migrations.

        Args:
            range_option: Optional revision range to generate SQL for (e.g., 'head', 'head:base')
            specific_revisions: Optional list of specific revision IDs to generate SQL for
            output_file: Path to save the generated SQL
        """
        try:
            if specific_revisions and (range_option == "head" or range_option is None):
                sql_content = self._generate_sql_for_specific_revisions(specific_revisions)
            else:
                # Standard approach
                command = self._build_alembic_command(range_option or "head")
                sql_content = self._execute_alembic_command(command)

            # Write SQL to file (except during testing)
            if "pytest" not in sys.modules:
                with open(output_file, "w") as f:
                    f.write(sql_content)

            logger.info(f"SQL generation completed. Output saved to {output_file}.")

        except subprocess.CalledProcessError as e:
            logger.error(f"Error generating SQL: {e}")
            sys.exit(1)


def generate_sql(
    dialect,
    alembic_ini,
    migration_path="migrations",
    range_option=None,
    specific_revisions=None,
    database=None,
):
    """
    Generate SQL from Alembic migrations.

    Args:
        dialect: SQL dialect to use (postgresql, mysql, etc.)
        alembic_ini: Path to alembic.ini file
        migration_path: Path to the directory containing Alembic migrations
        range_option: Optional revision range to generate SQL for (e.g., 'head', 'head:base')
        specific_revisions: Optional list of specific revision IDs to generate SQL for
    """
    try:
        generator = SQLGenerator(dialect, alembic_ini, migration_path, database)
        generator.generate_sql(range_option, specific_revisions)
    except FileNotFoundError as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Check Alembic migrations and generate SQL.")
    parser.add_argument(
        "--check-migrations", action="store_true", help="Check for Alembic migrations in the PR."
    )
    parser.add_argument(
        "--generate-sql", action="store_true", help="Generate SQL from Alembic migrations."
    )
    parser.add_argument("--dialect", type=str, help="SQL dialect to use.")
    parser.add_argument("--alembic-ini", type=str, help="Path to alembic.ini file.")
    parser.add_argument(
        "--migration-path",
        type=str,
        default="migrations",
        help="Path to Alembic migrations directory.",
    )
    parser.add_argument(
        "--database",
        type=str,
        help="Database name for multi-database setup (optional)",
    )
    parser.add_argument(
        "--revision-range", type=str, help="Optional revision range (e.g., 'head:base')"
    )
    parser.add_argument(
        "--specific-revisions",
        type=str,
        help="Comma-separated list of specific revision IDs to generate SQL for",
    )
    parser.add_argument(
        "--pr-revisions-only",
        action="store_true",
        help="Only generate SQL for revisions in the current PR",
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Set verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.check_migrations:
        # Return value not used here, but may be useful for other scripts
        return check_migrations(args.migration_path, args.database)
    elif args.generate_sql:
        if not args.dialect or not args.alembic_ini:
            logger.error("Error: --dialect and --alembic-ini are required for SQL generation.")
            sys.exit(1)

        specific_revisions = None

        # If --pr-revisions-only is specified, get revisions from the PR
        if args.pr_revisions_only:
            has_migrations, pr_revisions = check_migrations(args.migration_path, args.database)
            if has_migrations and pr_revisions:
                specific_revisions = pr_revisions
                logger.info(f"Using revisions from PR: {specific_revisions}")
            else:
                # Don't fallback to generating ALL migrations - skip SQL generation instead
                logger.warning(
                    "No migration revisions found in PR (no .py files in versions/ directory), "
                    "skipping SQL generation"
                )
                # Create empty output file to signal no SQL was generated
                with open("generated.sql", "w") as f:
                    f.write("")
                sys.exit(0)

        # If --specific-revisions is provided, it takes precedence
        if args.specific_revisions:
            specific_revisions = args.specific_revisions.split(",")
            logger.info(f"Using specified revisions: {specific_revisions}")

        generate_sql(
            args.dialect,
            args.alembic_ini,
            args.migration_path,
            args.revision_range,
            specific_revisions,
            args.database,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
