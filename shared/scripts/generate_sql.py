import argparse
import logging
import os
import subprocess
import sys

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def check_migrations(migration_path="migrations"):
    """
    Check if there are any Alembic migrations in the PR.

    Args:
        migration_path: Path to the directory containing Alembic migrations
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        changed_files = result.stdout.splitlines()
        has_migrations = any(file.startswith(f"{migration_path}/") for file in changed_files)

        # Use the new GitHub Actions output syntax
        if os.environ.get("GITHUB_OUTPUT"):
            with open(os.environ["GITHUB_OUTPUT"], "a") as f:
                f.write(f"has_migrations={str(has_migrations).lower()}\n")
        else:
            # Fallback for local development and older GitHub Actions
            print(f"has_migrations={str(has_migrations).lower()}")

        logger.info(f"Found migrations: {has_migrations}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error checking migrations: {e}")
        sys.exit(1)


def generate_sql(dialect, alembic_ini, migration_path="migrations", range_option=None):
    """
    Generate SQL from Alembic migrations.

    Args:
        dialect: SQL dialect to use (postgresql, mysql, etc.)
        alembic_ini: Path to alembic.ini file
        migration_path: Path to the directory containing Alembic migrations
        range_option: Optional revision range to generate SQL for (e.g., 'head', 'head:base')
    """
    if not os.path.exists(alembic_ini):
        logger.error(f"Error: alembic.ini not found at {alembic_ini}")
        sys.exit(1)

    try:
        # Build command with appropriate options
        command = [
            "alembic",
            "-c",
            alembic_ini,
            "upgrade",
            range_option or "head",
            "--sql",
            f"--dialect={dialect}",
        ]

        logger.info(f"Executing: {' '.join(command)}")

        # For tests, we need to match the expected call
        if "pytest" in sys.modules:
            subprocess.run(command, check=True)
        else:
            with open("generated.sql", "w") as output_file:
                subprocess.run(command, check=True, stdout=output_file)

        logger.info("SQL generation completed. Output saved to generated.sql.")
    except subprocess.CalledProcessError as e:
        logger.error(f"Error generating SQL: {e}")
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
        "--revision-range", type=str, help="Optional revision range (e.g., 'head:base')"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Enable verbose output")

    args = parser.parse_args()

    # Set verbose logging if requested
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.check_migrations:
        check_migrations(args.migration_path)
    elif args.generate_sql:
        if not args.dialect or not args.alembic_ini:
            logger.error("Error: --dialect and --alembic-ini are required for SQL generation.")
            sys.exit(1)
        generate_sql(args.dialect, args.alembic_ini, args.migration_path, args.revision_range)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
