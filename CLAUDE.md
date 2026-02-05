# Claude Code Project Instructions

## Setup Commands

Run these commands at the start of each session:

```bash
uv sync --dev && uv run pre-commit install
```

## Project Overview

This is a Discord bot game where players guess which channel a message came from.

## Development

- Use `uv run` to run Python commands
- Run tests with `uv run pytest`
- Type check with `uv run pyright`
- Lint with `uv run ruff check`
- Format with `uv run ruff format`
