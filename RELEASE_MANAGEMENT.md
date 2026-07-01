# Release Management Guide

This guide explains how to create and manage releases for A2L Generator.

## Version Scheme

The project uses semantic versioning:

- **v1.0.0** - Stable release (major.minor.patch)
- **v1.1.0-beta.1** - Beta pre-release
- **v1.0.0-alpha** - Alpha pre-release

## Creating a Release

### Step 1: Prepare Code

Ensure all changes are committed and tested:

```bash
git status
git add .
git commit -m "Your changes"
```

### Step 2: Create Release Tag

Tag the release with annotated tag (includes release notes):

```bash
# Stable release
git tag -a v1.1.0 -m "Release v1.1.0 - Your description"

# Beta release
git tag -a v1.1.0-beta.1 -m "Release v1.1.0-beta.1"

# Alpha release
git tag -a v1.1.0-alpha -m "Release v1.1.0-alpha"
```

### Step 3: Push Tag

Push the tag to GitHub - this triggers automated build and release:

```bash
git push origin --tags
```

Or push a specific tag:

```bash
git push origin v1.1.0
```

## Automated Build Process

When you push a tag, GitHub Actions automatically:

1. **Builds Executable**: Creates `A2LGenerator.exe` using PyInstaller
2. **Creates Archives**: Generates `.zip` and `.tar.gz` files
3. **Generates Release Notes**: Creates formatted release documentation
4. **Creates GitHub Release**: Uploads all artifacts and sets pre-release status

### Monitoring Build

1. Go to: https://github.com/d-coder07/A2L_Generator_nolicense/actions
2. Select the latest "Build and Release" workflow
3. Check build status and logs

## Release Artifacts

Each release includes:

| File | Description | Size |
|------|-------------|------|
| `A2LGenerator.exe` | Standalone Windows executable | ~20 MB |
| `.zip` | Portable archive with all files | ~20 MB |
| `.tar.gz` | Compressed archive for Unix/Linux users | ~20 MB |
| `RELEASE_NOTES_v*.md` | Changelog and features | Text |

## Local Build & Testing

To test the build locally before releasing:

```bash
# Install dependencies
pip install -r requirements.txt

# Build executable
python build_executable.py

# Test the executable
dist/A2LGenerator.exe
```

## Manual Build (If GitHub Actions Fails)

Build locally and upload manually:

```bash
# Build
python build_executable.py

# Create GitHub Release manually
# Go to: https://github.com/d-coder07/A2L_Generator_nolicense/releases
# Click "Draft a new release"
# Select tag: v1.1.0
# Upload files from releases/ directory
```

## Release Checklist

- [ ] All features implemented and tested
- [ ] Code reviewed
- [ ] README updated with new features
- [ ] Version bumped (if applicable)
- [ ] CHANGELOG entry added (optional)
- [ ] Local build tested: `python build_executable.py`
- [ ] Executable tested: `dist/A2LGenerator.exe`
- [ ] Commit changes: `git commit -m "..."`
- [ ] Push to main: `git push origin main`
- [ ] Create tag: `git tag -a v1.x.x -m "..."`
- [ ] Push tag: `git push origin --tags`
- [ ] GitHub Actions build completes
- [ ] GitHub Release created with artifacts
- [ ] Share on GitHub, LinkedIn, etc.

## Distribution Channels

### GitHub Releases
- **URL**: https://github.com/d-coder07/A2L_Generator_nolicense/releases
- **Users**: Direct download of .exe, .zip, .tar.gz

### LinkedIn
Share release announcement:

```
🚀 New Release: A2L Generator v1.1.0

Excited to announce the latest release featuring:
✨ [Feature 1]
✨ [Feature 2]
✨ [Feature 3]

📥 Download now (no Python needed):
👉 [GitHub Release Link]

Available as .exe, .zip, or .tar.gz
Apache 2.0 licensed - Enterprise ready!

#Automotive #EmbeddedSystems #A2L #OpenSource
```

## Previous Releases

All releases are available at:
https://github.com/d-coder07/A2L_Generator_nolicense/releases

## Troubleshooting

### Build Fails in GitHub Actions
- Check workflow logs: Actions tab → Latest run
- Verify all files are committed
- Ensure tag format is correct (v1.0.0)
- Manual build locally to debug

### Release Artifacts Not Showing
- Wait 5-10 minutes for GitHub Actions to complete
- Refresh the releases page
- Check Actions tab for build status
- Verify tag was pushed: `git tag -l`

### Download Links Not Working
- Verify tag was pushed to GitHub
- Check release page manually
- Try downloading from different browser
- Ensure GitHub Actions workflow completed successfully

## Best Practices

1. **Always use annotated tags**: `git tag -a` (not `git tag`)
2. **Include meaningful tag messages** with features/changes
3. **Test locally first**: Run `build_executable.py` before releasing
4. **Announce releases**: Share on GitHub, LinkedIn, forums
5. **Keep executables updated**: Users expect latest features
6. **Document changes**: Clear release notes help adoption
7. **Monitor feedback**: Check for issues with new releases
8. **Hotfix process**: Create v1.0.1 if critical bugs found

## References

- [Semantic Versioning](https://semver.org/)
- [GitHub Releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [PyInstaller](https://pyinstaller.org/)
- [GitHub Actions](https://docs.github.com/en/actions)
