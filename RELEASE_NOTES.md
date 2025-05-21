# Release Notes

## Permissions

If users encounter permission errors like:
```
Error: Unhandled error: HttpError: Resource not accessible by integration
```

Make sure they set the appropriate permissions in their workflow file. The alembic-review action requires:

```yaml
permissions:
  contents: read
  pull-requests: write
```

See [PERMISSIONS.md](./PERMISSIONS.md) for more details.

## First Release Preparation

Before users can reference the actions as shown in the documentation:

```yaml
uses: OpenMindUA/alembic-actions/actions/alembic-review@v1
```

You need to create a version tag and release:

1. Create a GitHub release and tag named `v1` for the first stable version.

   ```bash
   # After all changes are committed and pushed:
   git tag v1
   git push origin v1
   ```

2. On GitHub, go to the repository's "Releases" section and create a new release based on the `v1` tag.

Until this is done, users will see the error:
```
Error: Missing download info for OpenMindUA/alembic-actions@v1
```

## Using Actions Locally During Development

While developing, contributors can reference the local actions directly in their workflows:

```yaml
- name: Check Alembic Migrations
  uses: ./actions/alembic-review
```

This allows testing without requiring a published release.