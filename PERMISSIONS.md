# GitHub Action Permissions

## Required Permissions

For the actions to work correctly, you need to set the appropriate permissions in your workflow file:

### For alembic-review:

This action needs permissions to read the repository content and write to pull requests (to add comments):

```yaml
permissions:
  contents: read
  pull-requests: write
```

### For alembic-test and alembic-deploy:

These actions only need read access to repository content:

```yaml
permissions:
  contents: read
```

## Setting Permissions

Add the permissions block at the job level:

```yaml
jobs:
  review-migrations:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      pull-requests: write
    steps:
      # ...steps here...
```

## Troubleshooting

If you encounter errors like:

```
Error: Unhandled error: HttpError: Resource not accessible by integration
```

It's most likely a permissions issue. Make sure your workflow includes the necessary permissions for the actions you're using.

## Default Permissions in GitHub Actions

By default, GitHub Actions have limited permissions. Check GitHub's documentation for more details on the [default permissions](https://docs.github.com/en/actions/security-guides/automatic-token-authentication#permissions-for-the-github_token).