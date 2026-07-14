# Release Checklist

Use this checklist before publishing a new tag or GitHub Release.

## Before Tagging

- [ ] Confirm all milestone issues are closed or intentionally deferred.
- [ ] Run `python -m pytest`.
- [ ] Run `python -m ruff check .`.
- [ ] Run one local MCP wrapper smoke test for the feature area being released.
- [ ] Update `CHANGELOG.md` with the release summary.
- [ ] Update `pyproject.toml` version with `python tools/bump_version.py X.Y.Z`.
- [ ] Commit and push all release changes.
- [ ] Confirm `git status` reports a clean working tree.

## Tagging

```powershell
git tag vX.Y.Z
git push origin vX.Y.Z
```

The `Version check` GitHub Action verifies that the pushed tag matches the package version.

## GitHub Release Notes

Include:

- Short release title, such as `v0.5.1 Maintenance`.
- A concise summary of user-facing changes.
- Testing status, such as `pytest` and `ruff check .`.
- Any known limitations or follow-up issues.
