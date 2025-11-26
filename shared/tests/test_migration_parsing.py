import os
import tempfile
from unittest.mock import patch

import pytest

from shared.scripts.alembic_utils import (
    MigrationInfo,
    build_migration_dependency_graph,
    get_migration_order,
    get_migrations_from_pr,
    parse_migration_file,
)


def test_migration_info_basic():
    """Test basic MigrationInfo functionality."""
    # Single parent migration
    migration = MigrationInfo("abc123", "/path/to/file.py", "def456")
    assert migration.revision == "abc123"
    assert migration.file_path == "/path/to/file.py"
    assert migration.down_revision == "def456"
    assert not migration.is_merge
    assert not migration.is_initial
    assert migration.get_down_revisions() == ["def456"]

    # First migration (no parent)
    first_migration = MigrationInfo("abc123", "/path/to/file.py", None)
    assert first_migration.get_down_revisions() == []
    assert not first_migration.is_merge
    assert first_migration.is_initial

    # Merge migration
    merge_migration = MigrationInfo("abc123", "/path/to/file.py", ["def456", "ghi789"])
    assert merge_migration.is_merge
    assert not merge_migration.is_initial
    assert merge_migration.get_down_revisions() == ["def456", "ghi789"]

    # Test string representation
    assert "abc123" in str(merge_migration)
    assert "is_merge=True" in str(merge_migration)


def test_parse_migration_file_standard():
    """Test parsing a standard migration file with variable assignments."""
    content = '''"""Test migration

Revision ID: abc123def
Revises: fed321abc
Create Date: 2023-01-01 00:00:00.000000

"""

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "abc123def"
down_revision = "fed321abc"
branch_labels = None
depends_on = None

def upgrade():
    pass

def downgrade():
    pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        try:
            migration = parse_migration_file(f.name)
            assert migration is not None
            assert migration.revision == "abc123def"
            assert migration.down_revision == "fed321abc"
            assert not migration.is_merge
        finally:
            os.unlink(f.name)


def test_parse_migration_file_first_migration():
    """Test parsing the first migration file with None down_revision."""
    content = '''"""Initial migration

Revision ID: abc123def
Revises:
Create Date: 2023-01-01 00:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = "abc123def"
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        try:
            migration = parse_migration_file(f.name)
            assert migration is not None
            assert migration.revision == "abc123def"
            assert migration.down_revision is None
            assert not migration.is_merge
            assert migration.get_down_revisions() == []
        finally:
            os.unlink(f.name)


def test_parse_migration_file_merge():
    """Test parsing a merge migration file with multiple down_revision."""
    content = '''"""Merge migrations

Revision ID: abc123def
Revises: ('fed321abc', 'ghi789jkl')
Create Date: 2023-01-01 00:00:00.000000

"""

# revision identifiers, used by Alembic.
revision = "abc123def"
down_revision = ('fed321abc', 'ghi789jkl')
branch_labels = None
depends_on = None

def upgrade():
    pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        try:
            migration = parse_migration_file(f.name)
            assert migration is not None
            assert migration.revision == "abc123def"
            assert migration.down_revision == ["fed321abc", "ghi789jkl"]
            assert migration.is_merge
            assert set(migration.get_down_revisions()) == {"fed321abc", "ghi789jkl"}
        finally:
            os.unlink(f.name)


def test_parse_migration_file_comment_format():
    """Test parsing migration file using comment format only."""
    content = '''"""Test migration

Revision ID: abc123def
Revises: fed321abc
Create Date: 2023-01-01 00:00:00.000000

"""

# This file doesn't have variable assignments
def upgrade():
    pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        try:
            migration = parse_migration_file(f.name)
            assert migration is not None
            assert migration.revision == "abc123def"
            assert migration.down_revision == "fed321abc"
        finally:
            os.unlink(f.name)


def test_parse_migration_file_comment_merge():
    """Test parsing merge migration using comment format."""
    content = '''"""Merge migrations

Revision ID: abc123def456
Revises: ('fed321abc789', 'def789abc123')
Create Date: 2023-01-01 00:00:00.000000

"""

def upgrade():
    pass
'''

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        try:
            migration = parse_migration_file(f.name)
            assert migration is not None
            assert migration.revision == "abc123def456"
            assert migration.down_revision == ["fed321abc789", "def789abc123"]
            assert migration.is_merge
        finally:
            os.unlink(f.name)


def test_parse_migration_file_invalid():
    """Test parsing invalid migration file."""
    content = """# Not a valid migration file
def some_function():
    pass
"""

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(content)
        f.flush()

        try:
            migration = parse_migration_file(f.name)
            assert migration is None
        finally:
            os.unlink(f.name)


def test_build_migration_dependency_graph():
    """Test building migration dependency graph."""
    migrations = {
        "rev1": MigrationInfo("rev1", "file1.py", None),
        "rev2": MigrationInfo("rev2", "file2.py", "rev1"),
        "rev3": MigrationInfo("rev3", "file3.py", "rev2"),
        "rev4": MigrationInfo("rev4", "file4.py", ["rev2", "rev3"]),  # merge
    }

    graph = build_migration_dependency_graph(migrations)

    assert "rev1" in graph
    assert "rev2" in graph["rev1"]
    assert "rev3" in graph["rev2"]
    assert "rev4" in graph["rev2"]
    assert "rev4" in graph["rev3"]


def test_get_migration_order():
    """Test getting correct migration order."""
    migrations = {
        "rev1": MigrationInfo("rev1", "file1.py", None),
        "rev2": MigrationInfo("rev2", "file2.py", "rev1"),
        "rev3": MigrationInfo("rev3", "file3.py", "rev2"),
        "rev4": MigrationInfo("rev4", "file4.py", ["rev2", "rev3"]),  # merge
    }

    order = get_migration_order(migrations)

    # rev1 should come first (no dependencies)
    assert order.index("rev1") < order.index("rev2")
    assert order.index("rev2") < order.index("rev3")
    # rev4 should come after both rev2 and rev3
    assert order.index("rev2") < order.index("rev4")
    assert order.index("rev3") < order.index("rev4")


def test_get_migrations_from_pr():
    """Test getting migrations from PR."""
    mock_git_output = (
        "migrations/versions/001_initial.py\nmigrations/versions/002_add_users.py\nother_file.txt\n"
    )

    with (
        patch("subprocess.run") as mock_run,
        patch("os.path.exists", return_value=True),
        patch("builtins.open") as mock_open,
    ):

        mock_run.return_value.stdout = mock_git_output
        mock_run.return_value.returncode = 0

        # Mock file content for migrations
        mock_file_contents = {
            "migrations/versions/001_initial.py": """
revision = "001abc"
down_revision = None
""",
            "migrations/versions/002_add_users.py": """
revision = "002def"
down_revision = "001abc"
""",
        }

        def mock_open_side_effect(filename, *args, **kwargs):
            if filename in mock_file_contents:
                from io import StringIO

                return StringIO(mock_file_contents[filename])
            raise FileNotFoundError(f"No mock content for {filename}")

        mock_open.side_effect = mock_open_side_effect

        migrations = get_migrations_from_pr()

        assert len(migrations) == 2
        assert "001abc" in migrations
        assert "002def" in migrations
        assert migrations["001abc"].down_revision is None
        assert migrations["002def"].down_revision == "001abc"


def test_get_migrations_from_pr_git_error():
    """Test handling git command error in get_migrations_from_pr."""
    with patch("subprocess.run", side_effect=Exception("Git error")):
        migrations = get_migrations_from_pr()
        assert migrations == {}
