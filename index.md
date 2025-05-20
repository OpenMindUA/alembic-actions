# Alembic Actions

Welcome to the Alembic Actions collection! This repository provides a set of GitHub Actions to help you manage Alembic database migrations in your CI/CD workflow.

## Quick Navigation

- [Installation](#installation)
- [Available Actions](#available-actions)
  - [Alembic Review](#alembic-review)
  - [Alembic Test](#alembic-test)
  - [Alembic Deploy](#alembic-deploy)
- [Examples](#examples)
- [Common Scenarios](#common-scenarios)
- [Contributing](#contributing)

## Installation

Each action can be used independently in your GitHub workflow files. Simply reference the action with the path to its location in this repository:

```yaml
- name: Check Alembic Migrations
  uses: OpenMindUA/alembic-actions/actions/alembic-review@v1
```

## Available Actions

### Alembic Review

The `alembic-review` action checks for Alembic migrations in a pull request, generates SQL for the specified dialect, and adds the SQL as a comment to the pull request.

[View Action Documentation](./actions/alembic-review/README.md)

### Alembic Test

The `alembic-test` action runs tests for Alembic migrations to ensure they work correctly. It creates a test database, applies migrations, and verifies that they can be both applied and reversed.

[View Action Documentation](./actions/alembic-test/README.md)

### Alembic Deploy

The `alembic-deploy` action safely applies Alembic migrations to a production or staging database with optional backup creation.

[View Action Documentation](./actions/alembic-deploy/README.md)

## Examples

### Complete Workflow Example

```yaml
name: Database Migration Workflow

on:
  pull_request:
    paths:
      - 'migrations/**'

jobs:
  review-migrations:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout code
        uses: actions/checkout@v3
        with:
          fetch-depth: 0

      - name: Generate SQL for Review
        uses: OpenMindUA/alembic-actions/actions/alembic-review@v1
        with:
          dialect: "postgresql"
          alembic_ini: "alembic.ini"
          migration_path: "migrations"

  test-migrations:
    runs-on: ubuntu-latest
    needs: review-migrations
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Setup Test Database
        run: docker-compose up -d db-test

      - name: Test Migrations
        uses: OpenMindUA/alembic-actions/actions/alembic-test@v1
        with:
          dialect: "postgresql"
          alembic_ini: "alembic.ini"
          migration_path: "migrations"
          database_url: ${{ secrets.TEST_DB_URL }}

  deploy-migrations:
    runs-on: ubuntu-latest
    needs: test-migrations
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - name: Checkout code
        uses: actions/checkout@v3

      - name: Deploy Migrations
        uses: OpenMindUA/alembic-actions/actions/alembic-deploy@v1
        with:
          dialect: "postgresql"
          alembic_ini: "alembic.ini"
          migration_path: "migrations"
          database_url: ${{ secrets.PROD_DB_URL }}
          backup: "true"
```

## Common Scenarios

### 1. Reviewing Database Changes in PRs

For teams working on database changes, it's important to review the actual SQL that will be executed. The `alembic-review` action generates this SQL and adds it as a comment to the PR, making it easy for reviewers to see exactly what database changes are being made.

### 2. Testing Migrations Before Deployment

Before deploying migrations to production, it's crucial to test them in a controlled environment. The `alembic-test` action automates this process by applying migrations to a test database and verifying they work correctly.

### 3. Safe Production Deployments

When deploying to production, you want to ensure database migrations are applied safely. The `alembic-deploy` action provides backup options and detailed logging to make production deployments more reliable.

## Contributing

Contributions are welcome! Please feel free to submit a pull request or open an issue on our [GitHub repository](https://github.com/OpenMindUA/alembic-actions).