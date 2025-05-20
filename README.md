# Alembic Actions Collection

A collection of GitHub Actions for managing Alembic database migrations in your CI/CD workflow. These actions help automate the review, testing, and deployment of database migrations.

## Available Actions

This repository contains the following actions:

### 1. Alembic Review

Checks for Alembic migrations in a pull request, generates SQL for the specified database dialect, and adds the SQL as a comment to the pull request. This helps reviewers understand the database changes that will be applied when the migrations are run.

### 2. Alembic Test

Runs tests for Alembic migrations to ensure they work correctly. This action creates a test database, applies migrations, and verifies that they can be both applied and reversed successfully.

### 3. Alembic Deploy

Safely applies Alembic migrations to a production or staging database with optional backup creation.

## Features

- Automatically detects Alembic migrations in pull requests
- Generates SQL statements for the specified database dialect
- Tests migrations by applying them to a test database
- Deploys migrations safely with backup options
- Posts the SQL as a formatted comment on the pull request
- Supports customizable migration paths and revision ranges
- Works with all databases supported by Alembic/SQLAlchemy

## Inputs

| Name | Description | Required | Default |
|------|-------------|----------|---------|
| `dialect` | The SQL dialect to use for Alembic (e.g., `postgresql`, `mysql`, `sqlite`) | Yes | `postgresql` |
| `alembic_ini` | The path to the `alembic.ini` file | Yes | `alembic.ini` |
| `migration_path` | The path to the Alembic migrations directory | Yes | `migrations` |
| `revision_range` | Optional revision range for SQL generation (e.g., 'head:base') | No | `head` |

## Example Usage

### Basic Usage

```yaml
name: Check Alembic Migrations

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  check-migrations:
    runs-on: ubuntu-latest
    # These permissions are needed for PR comments
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0  # Important for detecting changes

      - name: Check Alembic Migrations and Generate SQL
        uses: OpenMindUA/alembic-actions/actions/alembic-review@v1
        with:
          dialect: "postgresql"
          alembic_ini: "alembic.ini"
          migration_path: "migrations"
```

### Advanced Usage

```yaml
name: Check Alembic Migrations

on:
  pull_request:
    types: [opened, synchronize, reopened]
    paths:
      - 'migrations/**'  # Only run when migration files change

jobs:
  check-migrations:
    runs-on: ubuntu-latest
    # These permissions are needed for PR comments
    permissions:
      contents: read
      pull-requests: write
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: "3.x"

      - name: Install project dependencies
        run: |
          python -m pip install -e .

      - name: Check Alembic Migrations and Generate SQL
        uses: OpenMindUA/alembic-actions/actions/alembic-review@v1
        with:
          dialect: "mysql"
          alembic_ini: "./config/alembic.ini"
          migration_path: "./db/migrations"
          revision_range: "head:base"  # Generate SQL for all changes in the PR
```

## How It Works

1. The action checks for files that match the migration path pattern in the pull request
2. If migrations are found, it uses Alembic to generate SQL for those migrations
3. The generated SQL is posted as a comment on the pull request
4. If no migrations are found or no SQL is generated, it adds a note to the PR

## Development

### Local Testing

To test locally:

```bash
# Install uv (optional but recommended)
pip install uv

# Install development dependencies
uv pip install -e ".[dev]"
# or use pip
# pip install -e ".[dev]"

# Run tests
uv run pytest
# or use pytest directly
# pytest

# Format code
uv run black .
uv run isort .

# Type check
uv run mypy shared/scripts
```

### GitHub Actions

This repository includes GitHub Actions workflows for testing and linting:

1. **Test Workflow** - Runs tests, linting, and type checking on multiple Python versions
   - Triggered on push to main, pull requests to main, or manual trigger
   - Tests on Python 3.8, 3.9, 3.10, and 3.11

2. **Action Test Workflow** - Tests the GitHub Actions themselves
   - Triggered on push to main, pull requests to main, or manual trigger
   - Sets up test databases and runs each action in test mode

## License

MIT License - See LICENSE file for details.
