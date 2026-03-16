"""
config.py - Reads deployment.env and makes all settings available to the app.

YOU DO NOT NEED TO EDIT THIS FILE.
All configuration is done in deployment.env.
"""

import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dotenv import dotenv_values


# ── Data classes (internal representation of deployment.env) ─────────────────
# These are filled automatically from deployment.env — do not edit here.

@dataclass
class MstrConfig:
    """Holds the MicroStrategy server connection details (Section 1)."""
    base_url: str
    username: str
    password: str
    login_mode: int = 1


@dataclass
class ProjectConfig:
    """Holds the project, DB connection, and security role settings (Sections 2-5)."""
    project_name: str
    project_id: Optional[str]
    backup_base_name: str
    db_connection_name: str
    db_catalog_name: str
    # List of (role_name, group_name) tuples built from REVOKE_ROLE_GROUP_PAIRS
    revoke_role_group_pairs: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class LogConfig:
    """Holds the logging settings (Section 6)."""
    log_file_name: str
    log_dir: Path


@dataclass
class AppConfig:
    """Top-level container — passed into every workflow."""
    mstr: MstrConfig
    project: ProjectConfig
    log: LogConfig


# ── Internal helpers ──────────────────────────────────────────────────────────

def _require(key: str, value: Optional[str], env_file: str) -> str:
    """Exit early with a clear message if a required key is missing."""
    if not value:
        print(f"[ERROR] Missing required value '{key}' in {env_file}")
        print(f"        Open {env_file} and fill in this value.")
        sys.exit(1)
    return value


def _parse_revoke_pairs(raw: str) -> list[tuple[str, str]]:
    """
    Parse REVOKE_ROLE_GROUP_PAIRS from deployment.env into a list of tuples.

    Input:  "Normale Benutzer|Everyone,Normale Benutzer|SGB II Projektzugriff"
    Output: [("Normale Benutzer", "Everyone"), ("Normale Benutzer", "SGB II Projektzugriff")]
    """
    pairs = []
    if not raw:
        return pairs
    for entry in raw.split(","):
        entry = entry.strip()
        if "|" not in entry:
            continue  # skip malformed entries
        role, group = entry.split("|", 1)
        pairs.append((role.strip(), group.strip()))
    return pairs


# ── Public loader ─────────────────────────────────────────────────────────────

def load_config(env_file: str = "deployment.env") -> AppConfig:
    """
    Read the given deployment.env file and return a fully validated AppConfig.

    Called automatically by main.py — you do not need to call this yourself.

    Args:
        env_file: Path to the credentials file.
                  If a relative path is given, it is resolved relative to the
                  directory where config.py lives (i.e. the project folder),
                  not wherever Python was launched from.
    """
    # Resolve relative paths against the project folder, not the shell cwd
    path = Path(env_file)
    if not path.is_absolute():
        path = Path(__file__).parent / env_file
    if not path.exists():
        print(f"[ERROR] Configuration file not found: {path.absolute()}")
        print(f"        Make sure '{env_file}' exists in the same folder as main.py")
        sys.exit(1)

    # Read the file into a plain dict WITHOUT touching os.environ.
    # This means multiple configs can be loaded in the same process without
    # values from one file leaking into another.
    v = dotenv_values(str(path))

    # ── Section 1: Server connection ──────────────────────────────────
    mstr = MstrConfig(
        base_url=_require("MSTR_BASE_URL", v.get("MSTR_BASE_URL"), env_file),
        username=_require("MSTR_USERNAME", v.get("MSTR_USERNAME"), env_file),
        password=_require("MSTR_PASSWORD", v.get("MSTR_PASSWORD"), env_file),
        login_mode=int(v.get("MSTR_LOGIN_MODE", "1")),
    )

    # ── Sections 2-5: Project, backup, DB connection, security roles ──
    project_name = _require("MSTR_PROJECT_NAME", v.get("MSTR_PROJECT_NAME"), env_file)

    project = ProjectConfig(
        project_name=project_name,
        project_id=v.get("MSTR_PROJECT_ID") or None,
        backup_base_name=v.get("BACKUP_PROJECT_BASE_NAME", project_name),
        db_connection_name=_require("DB_CONNECTION_NAME", v.get("DB_CONNECTION_NAME"), env_file),
        db_catalog_name=_require("DB_CATALOG_NAME", v.get("DB_CATALOG_NAME"), env_file),
        revoke_role_group_pairs=_parse_revoke_pairs(v.get("REVOKE_ROLE_GROUP_PAIRS", "")),
    )

    # ── Section 6: Logging ────────────────────────────────────────────
    log = LogConfig(
        log_file_name=v.get("LOG_FILE_NAME", f"LOG_{project_name}.txt"),
        log_dir=Path(v.get("LOG_DIR", ".")),
    )

    return AppConfig(mstr=mstr, project=project, log=log)