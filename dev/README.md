# Development Scripts

This directory contains helper scripts for development workflow.

## Scripts

### `pytest.sh` - Run Unit Tests

Run all unit tests:

```bash
./dev/pytest.sh
```

Run tests for a specific file or directory:

```bash
./dev/pytest.sh tests/utils/test_upgrade.py
./dev/pytest.sh tests/utils/
```

Pass additional pytest options:

```bash
./dev/pytest.sh -k test_upgrade
./dev/pytest.sh --cov
```

### `code-style.sh` - Auto-fix Linting and Formatting

Auto-fix linting issues and format code (default behavior):

```bash
./dev/code-style.sh
```

This will:
- `ruff check --fix` - Auto-fix linting issues
- `ruff format` - Format code

Check code style and formatting without making changes:

```bash
./dev/code-style.sh --check
```

This script runs:
- `ruff check` - Linting checks
- `ruff format --check` - Formatting checks

## Before Submitting a PR

Before submitting a pull request, make sure to:

1. Run `./dev/code-style.sh` to auto-fix linting and formatting issues
2. Run `./dev/code-style.sh --check` to verify all checks pass
3. Run `./dev/pytest.sh` and ensure all tests pass

