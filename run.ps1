# run.ps1 — Windows equivalent of the Makefile
# Usage: .\run.ps1 <target>
# Example: .\run.ps1 dev

param([string]$Target = "help")

switch ($Target) {
    "help" {
        Write-Host ""
        Write-Host "Usage: .\run.ps1 <target>"
        Write-Host ""
        Write-Host "  install    Install dependencies via uv"
        Write-Host "  run        Start the server (http://0.0.0.0:8000)"
        Write-Host "  dev        Start the server with auto-reload"
        Write-Host "  test       Run test suite"
        Write-Host "  lint       Check linting (ruff)"
        Write-Host "  format     Check formatting (ruff format)"
        Write-Host "  typecheck  Run type checker (mypy)"
        Write-Host "  fix        Auto-fix lint and format issues"
        Write-Host "  check      Run all CI checks (lint + format + typecheck + tests)"
        Write-Host ""
    }
    "install" {
        uv sync --all-extras
    }
    "run" {
        uv run uvicorn manyboard.main:app --host 0.0.0.0 --port 8000
    }
    "dev" {
        uv run uvicorn manyboard.main:app --host 0.0.0.0 --port 8000 --reload
    }
    "test" {
        uv run pytest --tb=short -v
    }
    "lint" {
        uv run ruff check .
    }
    "format" {
        uv run ruff format --check .
    }
    "typecheck" {
        uv run mypy src/
    }
    "fix" {
        uv run ruff check --fix .
        uv run ruff format .
    }
    "check" {
        uv run ruff check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run ruff format --check .
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run mypy src/
        if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
        uv run pytest --tb=short -v
    }
    default {
        Write-Host "Unknown target: $Target"
        Write-Host "Run .\run.ps1 help for available targets."
        exit 1
    }
}
