# Contributing to RDSAI CLI

Thank you for your interest in contributing to RDSAI CLI! This document provides guidelines and instructions for contributing.

## 🚀 Getting Started

### Prerequisites

- Python **3.13+**
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Git
- MySQL instance (for testing database features)

### Development Setup

```bash
# Clone the repository
git clone https://github.com/aliyun/rdsai-cli.git
cd rdsai-cli

# Install dependencies with uv (recommended)
uv sync --extra dev

# Or with pip (use virtual environment recommended)
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e ".[dev]"

# Run the CLI
uv run rdsai
# or if using pip with venv
python -m cli
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/loop/test_runtime.py

# Run tests with verbose output
uv run pytest -v

# Run tests matching a pattern
uv run pytest -k "test_runtime"

# Run with coverage (requires pytest-cov)
uv run pytest --cov=. --cov-report=html
```

**Note:** This project uses `pytest-asyncio` for async tests. Make sure async test functions are properly decorated.

### Code Quality

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting, and [mypy](https://mypy.readthedocs.io/) for type checking:

```bash
# Check for linting errors (without fixing)
uv run ruff check .

# Auto-fix linting errors
uv run ruff check --fix .

# Check code formatting (without reformatting)
uv run ruff format --check .

# Auto-format code
uv run ruff format .

# Type checking (strict mode enabled)
uv run mypy .

# Run all checks at once
uv run ruff check . && uv run ruff format --check . && uv run mypy . && uv run pytest
```

**CI/CD:** Our GitHub Actions workflows automatically run these checks on every push and PR:
- **Lint workflow** (`lint.yml`): Runs `ruff check` and `ruff format --check`
- **Test workflow** (`python-package.yml`): Runs `pytest` on Python 3.13

## 📝 Code Style

### General Guidelines

- Follow [PEP 8](https://pep8.org/) conventions
- Use type hints for **all** function signatures (required by mypy strict mode)
- Write docstrings for public functions and classes
- Keep line length under 120 characters
- Use meaningful variable and function names

### Code Formatting

- Ruff handles all formatting automatically
- Run `ruff format .` before committing
- The formatter enforces consistent style across the codebase


## 🔄 Pull Request Process

### Before Submitting

1. **Create an issue first** (optional but recommended) — Discuss the change you want to make
2. **Fork the repository** — Create your own copy
3. **Create a feature branch** — `git checkout -b feature/your-feature-name` or `git checkout -b fix/your-bug-name`
4. **Make your changes** — Follow the code style guidelines
5. **Write tests** — Ensure your changes are covered with appropriate tests
6. **Run all checks locally** — Ensure everything passes before submitting:
   ```bash
   # Fix linting issues
   uv run ruff check --fix .
   
   # Format code
   uv run ruff format .
   
   # Check types
   uv run mypy .
   
   # Run tests
   uv run pytest
   ```

### Submitting

1. **Commit your changes** — Write clear, descriptive commit messages
   ```bash
   git add .
   git commit -m "feat: add new feature description"
   # or
   git commit -m "fix: resolve bug description"
   ```

2. **Push your branch** to your fork
   ```bash
   git push origin feature/your-feature-name
   ```

3. **Open a Pull Request** against the `main` branch
   - Fill out the PR description template
   - Reference related issues if applicable
   - Add screenshots or examples if relevant

4. **Wait for review** — Address feedback promptly

### PR Guidelines

- **Keep PRs focused** — One feature/fix per PR
- **Write clear commit messages** — Use conventional commit format:
  - `feat:` for new features
  - `fix:` for bug fixes
  - `docs:` for documentation changes
  - `refactor:` for code refactoring
  - `test:` for test additions/changes
  - `chore:` for maintenance tasks
- **Update documentation** — If you add features or change behavior
- **Add tests** — New features should include tests
- **Ensure CI passes** — All GitHub Actions checks must pass
- **Keep PRs small** — Easier to review and merge

### Pre-commit Checklist

Before submitting your PR, ensure:

- [ ] Code follows style guidelines
- [ ] All type hints are present and correct
- [ ] Tests pass locally (`uv run pytest`)
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Formatting is correct (`uv run ruff format --check .`)
- [ ] Type checking passes (`uv run mypy .`)
- [ ] Documentation is updated if needed
- [ ] Commit messages are clear and descriptive

## 🐛 Reporting Issues

### Bug Reports

When reporting a bug, please include:

- **RDSAI CLI version** — `rdsai --version`
- **Python version** — `python --version` or `uv python list`
- **Operating system** — OS name and version
- **Steps to reproduce** — Clear, step-by-step instructions
- **Expected behavior** — What you expected to happen
- **Actual behavior** — What actually happened
- **Error messages or logs** — Full error traceback if available
- **Configuration** — Relevant config files or settings (redact sensitive info)
- **Database version** — MySQL version if relevant

### Feature Requests

When requesting a feature, please include:

- **Clear description** — What the feature should do
- **Use case** — Why is this needed? What problem does it solve?
- **Possible implementation approach** — Optional, but helpful
- **Alternatives considered** — What other solutions did you consider?

### Issue Templates

Use GitHub issue templates when available:
- Bug report template
- Feature request template


## 💬 Communication

- **GitHub Issues** — Bug reports, feature requests, questions
- **GitHub Discussions** — General discussion, ideas, Q&A
- **Pull Requests** — Code contributions with review and discussion


## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to RDSAI CLI! 🎉

Your contributions help make this project better for everyone. If you have questions or need help, don't hesitate to open an issue or start a discussion.
