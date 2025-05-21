# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Overview

Alembic Actions is a collection of GitHub Actions that automate the review, testing, and deployment of Alembic database migrations in CI/CD workflows. The actions include:

1. **Alembic Review**: Generates SQL for migrations in a PR and adds it as a comment
2. **Alembic Test**: Tests migrations by applying them to a test database
3. **Alembic Deploy**: Safely applies migrations to production/staging databases

## Commands

### Building and Installing

```bash
# Install the package in development mode with dev dependencies
uv pip install -e ".[dev]"

# Create a virtual environment and install dependencies
uv venv
uv pip sync
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest shared/tests/test_alembic_utils.py

# Run specific test function
uv run pytest shared/tests/test_alembic_utils.py::test_get_current_revision

# Run tests with verbose output
uv run pytest -v
```

### Code Formatting and Linting

```bash
# Format code with Black
uv run black .

# Sort imports
uv run isort .

# Type checking
uv run mypy shared/scripts

# Install and run all dev tools
uv pip install -e ".[dev]"
uv run black .
uv run isort .
uv run mypy shared/scripts
```

## Architecture

The repository is organized with the following structure:

- **Root level action**: The main GitHub Action that users include in their workflows
- **Individual actions/**: Specific actions for review, testing, and deployment
- **shared/scripts/**: Core utilities shared across actions
  - `alembic_utils.py`: Helper functions for working with Alembic
  - `generate_sql.py`: Utilities for generating SQL from migrations

The architecture follows these design principles:

1. **Modularity**: Each action is independent but can work together in a pipeline
2. **Shared Core**: Common utilities are centralized in the shared/ directory
3. **Standardized Inputs**: All actions use consistent input parameters where possible

## Development Workflow

When creating or modifying actions:

1. Create or activate the virtual environment using `uv venv`
2. Update the action's `action.yaml` file with appropriate inputs and steps
3. Update shared utilities in the `shared/scripts/` directory as needed
4. Write tests for all new functionality
5. Run code formatting and type checking: `uv run black . && uv run isort . && uv run mypy shared/scripts`
6. Ensure all tests pass before submitting a PR: `uv run pytest`

The Python code uses type hints and follows consistent patterns for error handling and logging.

### Managing Dependencies

```bash
# Add a new dependency
uv pip install package-name

# Add a new development dependency
uv pip install --dev package-name

# Update dependencies
uv pip sync

# Generate requirements.txt
uv pip freeze > requirements.txt
```