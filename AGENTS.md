# Repository Guidelines

## Project Structure & Module Organization

RDSAI CLI is a Python 3.13 command-line application. Entry points live in `cli.py` and `app.py`, with the installed console script exposed as `rdsai`. Core agent orchestration is in `loop/`, LLM integrations in `llm/`, database clients and schema helpers in `database/`, user interface code in `ui/`, and reusable commands/tools in `tools/`. Configuration lives under `config/`; prompt templates are in `prompts/`; contributor and user documentation is in `docs/`. Tests mirror the source areas under `tests/`, for example `tests/loop/`, `tests/database/`, `tests/ui/`, and `tests/skills/`.

## Build, Test, and Development Commands

- `uv sync --extra dev`: install runtime and development dependencies.
- `uv run rdsai`: run the CLI through the project script.
- `python -m cli`: alternate local entry point when using an activated virtualenv.
- `./dev/pytest.sh`: run the full test suite with verbose pytest output.
- `uv run pytest tests/loop/test_runtime.py`: run one test file.
- `./dev/code-style.sh`: auto-fix Ruff lint issues and format code.
- `./dev/code-style.sh --check`: verify linting and formatting without modifying files.

## Coding Style & Naming Conventions

Use Python type hints for all function signatures; `mypy` is configured with `disallow_untyped_defs = true`. Ruff targets Python 3.13 with a 120-character line length, spaces for indentation, sorted imports, and double-quoted strings. Use `snake_case` for modules, functions, variables, and test names; use `PascalCase` for classes. Keep public functions and classes documented when their behavior is not obvious.

## Testing Guidelines

The test framework is pytest with pytest-asyncio for async coverage. Place tests in the matching `tests/<area>/` package and name files `test_*.py`. Prefer focused unit tests near the changed module, and add integration coverage when touching database connections, REPL behavior, or agent/tool orchestration. Run `./dev/pytest.sh` before submitting changes.

## Commit & Pull Request Guidelines

Recent history and `CONTRIBUTING.md` use conventional commit prefixes such as `feat(core):`, `fix:`, `docs(readme):`, `test:`, `refactor:`, and `chore:`. Keep commits descriptive and scoped. Pull requests should target `main`, explain the change, link related issues when available, include screenshots or terminal examples for UI/CLI behavior changes, update docs for user-visible behavior, and pass `./dev/code-style.sh --check` plus `./dev/pytest.sh`.

## Security & Configuration Tips

Do not commit API keys, database credentials, or local config. Runtime LLM configuration is stored in `~/.rdsai-cli/config.json`; treat it as private. Database write operations are confirmation-gated by design, so preserve explicit review prompts when changing SQL execution paths.
