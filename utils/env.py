import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Explicit override so secrets can live anywhere on the host machine.
ENV_FILE_OVERRIDE_VAR = "INVESTMENT_REPORT_ENV_FILE"

# How many parent directories above the project root to search for a .env file.
_MAX_PARENTS_TO_SEARCH = 4


def _candidate_dotenv_paths():
    """Yield possible .env locations in priority order."""
    override = os.environ.get(ENV_FILE_OVERRIDE_VAR, "").strip()
    if override:
        yield Path(override).expanduser()

    # Project-local .env first, then walk upward toward the drive root.
    yield PROJECT_ROOT / ".env"
    for parent in list(PROJECT_ROOT.parents)[:_MAX_PARENTS_TO_SEARCH]:
        yield parent / ".env"


def resolve_dotenv_path() -> Path:
    """Return the first existing .env path, or the project-local default."""
    for candidate in _candidate_dotenv_paths():
        if candidate and candidate.exists():
            return candidate
    return PROJECT_ROOT / ".env"


def load_project_env(override: bool = True) -> Path:
    """Load environment variables from a portable, auto-discovered .env file.

    Resolution order:
    1. Path in the ``INVESTMENT_REPORT_ENV_FILE`` environment variable, if set.
    2. ``<project-root>/.env``.
    3. ``.env`` in up to four parent directories above the project root.

    This keeps the project runnable on any machine: drop a ``.env`` next to the
    project (or anywhere above it) without editing any source paths.
    """
    dotenv_path = resolve_dotenv_path()
    load_dotenv(dotenv_path=dotenv_path, override=override)
    return dotenv_path
