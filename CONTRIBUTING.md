# Contributing to RDSAI CLI

Thank you for your interest in contributing to RDSAI CLI! This document provides guidelines and instructions for contributing.

## 🚀 Getting Started

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- Git

### Development Setup

```bash
# Clone the repository
git clone https://github.com/rdsai/rdsai-cli.git
cd rdsai-cli

# Install dependencies with uv (recommended)
uv sync --extra dev

# Or with pip
pip install -e ".[dev]"

# Run the CLI
uv run rdsai
# or
python -m cli
```

### Running Tests

```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=.
```

### Code Quality

We use [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Lint
uv run ruff check .

# Format
uv run ruff format .

# Type checking
uv run mypy .
```

## 📝 Code Style

- Follow [PEP 8](https://pep8.org/) conventions
- Use type hints for all function signatures
- Write docstrings for public functions and classes
- Keep line length under 120 characters
- Use meaningful variable and function names

## 🔄 Pull Request Process

### Before Submitting

1. **Create an issue first** — Discuss the change you want to make
2. **Fork the repository** — Create your own copy
3. **Create a feature branch** — `git checkout -b feature/your-feature-name`
4. **Make your changes** — Follow the code style guidelines
5. **Write tests** — Ensure your changes are covered
6. **Run checks** — `ruff check . && ruff format . && mypy . && pytest`

### Submitting

1. Push your branch to your fork
2. Open a Pull Request against the `main` branch
3. Fill out the PR template
4. Wait for review

### PR Guidelines

- Keep PRs focused — one feature/fix per PR
- Write clear commit messages
- Update documentation if needed
- Add tests for new features
- Ensure all CI checks pass

## 🐛 Reporting Issues

### Bug Reports

Please include:

- RDSAI CLI version (`rdsai --version`)
- Python version (`python --version`)
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Error messages or logs

### Feature Requests

Please include:

- Clear description of the feature
- Use case — why is this needed?
- Possible implementation approach (optional)


## 💬 Communication

- **GitHub Issues** — Bug reports, feature requests
- **GitHub Discussions** — Questions, ideas, general discussion
- **Pull Requests** — Code contributions

## 📜 License

By contributing, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing! 🎉
