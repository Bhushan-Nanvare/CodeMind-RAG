# Contributing

Thanks for your interest in improving CodeMind RAG.

## Before you start

- Read the repository root [`README.md`](README.md) for setup, architecture, and technical reference.
- Prefer small, focused pull requests with a clear description of **what** changed and **why**.

## Development checks

From the monorepo root:

```bash
pnpm run typecheck
```

For the Python API:

```bash
cd apps/api
pytest tests/ -v
```

## Style

- **TypeScript:** match existing formatting; run Prettier if configured in your editor.
- **Python:** follow PEP 8; keep logging structured where `structlog` is already used.

## Reporting issues

Include OS, Node and Python versions, commands you ran, and relevant logs or screenshots. Do not paste live API keys into issues.
