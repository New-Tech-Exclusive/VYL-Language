# Git Tagging Guide for VPM Package Versioning

## Overview

VPM supports version-specific package installation using Git tags. When users install `package@1.0.0`, VPM fetches from the `v1.0.0` tag instead of `master`.

## Creating Version Tags

### 1. Basic Tagging

```bash
# After committing your package changes
git tag v1.0.0
git push origin v1.0.0
```

### 2. Annotated Tags (Recommended)

```bash
# Create annotated tag with message
git tag -a v1.0.0 -m "Release version 1.0.0"
git push origin v1.0.0
```

### 3. Tag Specific Commit

```bash
# Tag a previous commit
git tag v1.0.0 <commit-hash>
git push origin v1.0.0
```

## Version Naming Convention

Follow semantic versioning: `vMAJOR.MINOR.PATCH`

- `v1.0.0` - Initial stable release
- `v1.0.1` - Bug fix
- `v1.1.0` - New feature (backward compatible)
- `v2.0.0` - Breaking changes

**Important:** Always prefix with `v`

## Example Workflow

### Release stdlib v1.0.0

```bash
cd /path/to/VYL-Language

# 1. Update mod.vinfo
echo "name=stdlib
version=1.0.0
author=VYL Team
description=VYL Standard Library - All modules bundled
dependencies=" > mods/stdlib/mod.vinfo

# 2. Commit changes
git add mods/stdlib/
git commit -m "stdlib: Release v1.0.0"

# 3. Create tag
git tag -a v1.0.0 -m "stdlib v1.0.0: Initial stable release"

# 4. Push both commit and tag
git push origin master
git push origin v1.0.0

# 5. Users can now install
vpm install stdlib@1.0.0
```

## Managing Multiple Package Versions

### Scenario: Different versions of different packages

```bash
# stdlib v1.0.0
git tag v1.0.0-stdlib -m "stdlib v1.0.0"
git push origin v1.0.0-stdlib

# http v2.0.0  
git tag v2.0.0-http -m "http v2.0.0"
git push origin v2.0.0-http
```

**Note:** Current VPM implementation uses simple tags (e.g., `v1.0.0`). Package-specific tags require VPM enhancement.

## URL Resolution

VPM transforms versions as follows:

| User Command | Git Branch/Tag | URL |
|--------------|----------------|-----|
| `vpm install stdlib` | `master` | `.../master/mods/stdlib/mod.vyl` |
| `vpm install stdlib@1.0.0` | `v1.0.0` | `.../v1.0.0/mods/stdlib/mod.vyl` |
| `vpm install http@2.1.3` | `v2.1.3` | `.../v2.1.3/mods/http/mod.vyl` |

## Listing Tags

```bash
# List all tags
git tag

# List tags matching pattern
git tag -l "v1.*"

# Show tag details
git show v1.0.0
```

## Deleting Tags

```bash
# Delete local tag
git tag -d v1.0.0

# Delete remote tag
git push origin --delete v1.0.0
```

## Best Practices

1. **Always test before tagging**
   ```bash
   vpm install package  # Test master first
   # If works, then tag
   git tag v1.0.0
   ```

2. **Match mod.vinfo version to tag**
   - If tag is `v1.0.0`, mod.vinfo should say `version=1.0.0`

3. **Never move tags**
   - Tags should be immutable
   - If you need to fix, create a new tag (e.g., `v1.0.1`)

4. **Use annotated tags for releases**
   ```bash
   git tag -a v1.0.0 -m "Release notes here"
   ```

5. **Document breaking changes**
   ```bash
   git tag -a v2.0.0 -m "BREAKING: Changed API signatures"
   ```

## Troubleshooting

### "Failed to download mod.vinfo"

- Check if tag exists: `git tag -l`
- Verify tag is pushed: `git ls-remote --tags origin`
- Ensure GitHub Actions/workflows aren't blocking raw access

### Version mismatch

```bash
# Verify tag contents
git show v1.0.0:mods/stdlib/mod.vinfo
```

### Rollback a package

Users can downgrade by specifying older version:

```bash
vpm remove stdlib
vpm install stdlib@0.9.0
```

## CI/CD Integration

### Automatic tagging on release

```yaml
# .github/workflows/release.yml
name: Release
on:
  push:
    tags:
      - 'v*'
jobs:
  release:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - name: Validate package versions
        run: |
          # Check all mod.vinfo versions match tag
          TAG_VERSION=${GITHUB_REF#refs/tags/v}
          echo "Tag version: $TAG_VERSION"
```

## Package Maintainer Checklist

- [ ] Updated mod.vinfo version
- [ ] Tested package with `vpm install <package>`
- [ ] Committed all changes
- [ ] Created annotated tag: `git tag -a vX.Y.Z -m "message"`
- [ ] Pushed commit: `git push origin master`
- [ ] Pushed tag: `git push origin vX.Y.Z`
- [ ] Verified installation: `vpm install package@X.Y.Z`
- [ ] Updated index.txt if new package
