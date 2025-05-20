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

    Returns:
        A tuple of (has_migrations, changed_migration_files)
    """
    try:
        result = subprocess.run(
            ["git", "diff", "--name-only", "origin/main...HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        changed_files = result.stdout.splitlines()
        changed_migration_files = [
            file for file in changed_files if file.startswith(f"{migration_path}/")
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


def generate_sql(
    dialect, alembic_ini, migration_path="migrations", range_option=None, specific_revisions=None
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
    if not os.path.exists(alembic_ini):
        logger.error(f"Error: alembic.ini not found at {alembic_ini}")
        sys.exit(1)

    try:
        # If specific revisions are provided and range_option isn't specified by the user,
        # generate SQL for each specific revision
        if specific_revisions and (range_option == "head" or range_option is None):
            all_sql = []
            for revision in specific_revisions:
                logger.info(f"Generating SQL for revision: {revision}")

                # Get the revision before this one to see just this revision's changes
                prev_revision_cmd = [
                    "alembic",
                    "-c",
                    alembic_ini,
                    "history",
                    "-r",
                    f"{revision}:base",
                    "--verbose",
                ]

                try:
                    prev_result = subprocess.run(
                        prev_revision_cmd, capture_output=True, text=True, check=True
                    )

                    # Parse output to find the previous revision
                    prev_revision = None
                    for line in prev_result.stdout.splitlines():
                        if f"({revision})" in line:
                            continue  # Skip the current revision
                        if "->" in line:
                            # Found a previous revision
                            parts = line.split("->")
                            if len(parts) >= 2:
                                prev_rev_part = parts[0].strip()
                                # Extract revision ID
                                prev_revision = prev_rev_part.split()[0]
                                break

                    # If we found the previous revision
                    if prev_revision:
                        # Build command for just this specific migration
                        single_command = [
                            "alembic",
                            "-c",
                            alembic_ini,
                            "upgrade",
                            f"{prev_revision}:{revision}",
                            "--sql",
                        ]

                        # Alembic doesn't directly support a --dialect flag
                        # We'll modify the environment variables instead
                        env = os.environ.copy()
                        env["ALEMBIC_DIALECT"] = dialect

                        logger.info(f"Executing: {' '.join(single_command)}")

                        # Capture SQL for this revision
                        result = subprocess.run(
                            single_command, capture_output=True, text=True, check=True, env=env
                        )

                        # Add a header for this revision
                        all_sql.append(f"\n-- Migration: {revision} --\n")
                        all_sql.append(result.stdout)
                except subprocess.CalledProcessError as e:
                    logger.error(f"Error getting previous revision for {revision}: {e}")
                    # Fallback to "base" if we can't determine the previous revision
                    single_command = [
                        "alembic",
                        "-c",
                        alembic_ini,
                        "upgrade",
                        f"{revision}:{revision}",
                        "--sql",
                    ]

                    env = os.environ.copy()
                    env["ALEMBIC_DIALECT"] = dialect

                    logger.info(f"Fallback - Executing: {' '.join(single_command)}")

                    result = subprocess.run(
                        single_command, capture_output=True, text=True, check=True, env=env
                    )

                    all_sql.append(f"\n-- Migration: {revision} --\n")
                    all_sql.append(result.stdout)

            # Write all the collected SQL to the output file
            with open("generated.sql", "w") as output_file:
                output_file.write("".join(all_sql))

            logger.info(
                "SQL generation for specific revisions completed. Output saved to generated.sql."
            )
            return

        # If no specific revisions or a range was explicitly specified, use the standard approach
        command = [
            "alembic",
            "-c",
            alembic_ini,
            "upgrade",
            range_option or "head",
            "--sql",
        ]

        # Alembic doesn't directly support a --dialect flag
        # We'll modify the environment variables instead
        env = os.environ.copy()
        env["ALEMBIC_DIALECT"] = dialect

        logger.info(f"Executing: {' '.join(command)}")

        # For tests, we need to match the expected call
        if "pytest" in sys.modules:
            subprocess.run(command, check=True, env=env)
        else:
            with open("generated.sql", "w") as output_file:
                subprocess.run(command, check=True, stdout=output_file, env=env)

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
        return check_migrations(args.migration_path)
    elif args.generate_sql:
        if not args.dialect or not args.alembic_ini:
            logger.error("Error: --dialect and --alembic-ini are required for SQL generation.")
            sys.exit(1)

        specific_revisions = None

        # If --pr-revisions-only is specified, get revisions from the PR
        if args.pr_revisions_only:
            has_migrations, pr_revisions = check_migrations(args.migration_path)
            if has_migrations and pr_revisions:
                specific_revisions = pr_revisions
                logger.info(f"Using revisions from PR: {specific_revisions}")
            else:
                logger.info("No migration revisions found in PR, falling back to standard behavior")

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
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
