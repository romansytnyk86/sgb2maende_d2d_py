#!/usr/bin/env python3
"""
Minimal standalone test for cross-environment project duplication.

This script is intentionally self-contained:
- No import from project-specific config files
- No dependency on deployment.env
- All required settings are defined below in CONFIG

How to use:
1. Edit CONFIG values in this file.
2. Run: python duplicate_project_test.py
"""

from __future__ import annotations

import sys

import time

from mstrio.connection import Connection
from mstrio.server.project import CrossDuplicationConfig, Project
from mstrio.server.environment import Environment


# ---------------------------------------------------------------------------
# SELF-CONTAINED SETTINGS
# ---------------------------------------------------------------------------
CONFIG = {
    # Source environment
    "source_base_url": "http://10.146.13.58:8080/MicroStrategyLibrary/",
    "source_username": "adminbiss",
    "source_password": "M$tr2026",
    "source_login_mode": 1,

    # Target environment
    "target_base_url": "http://10.146.13.45:8080/MicroStrategyLibrary",
    "target_username": "tempadmin",
    "target_password": "M$tr2026",
    "target_login_mode": 1,

    # Duplication settings
    "source_project": "Betriebsnummernservice",
    "target_project": "Betriebsnummernservice Backup Test",
    "match_users_by_login": False,
    "sync_with_target_env": True,
    "timeout_minutes": 60,
}


def open_connection(base_url: str, username: str, password: str, login_mode: int) -> Connection:
    return Connection(
        base_url=base_url,
        username=username,
        password=password,
        login_mode=login_mode,
    )


def run_duplication() -> int:
    source_conn = None
    target_conn = None
    try:
        print(f"[INFO] Connecting to source: {CONFIG['source_base_url']} as {CONFIG['source_username']}")
        source_conn = open_connection(
            base_url=CONFIG["source_base_url"],
            username=CONFIG["source_username"],
            password=CONFIG["source_password"],
            login_mode=CONFIG["source_login_mode"],
        )
        print("[OK] Source connection established")

        print(f"[INFO] Connecting to target: {CONFIG['target_base_url']} as {CONFIG['target_username']}")
        target_conn = open_connection(
            base_url=CONFIG["target_base_url"],
            username=CONFIG["target_username"],
            password=CONFIG["target_password"],
            login_mode=CONFIG["target_login_mode"],
        )
        print("[OK] Target connection established")

        print(f"[INFO] Resolving source project: {CONFIG['source_project']}")
        source_project = Project(source_conn, name=CONFIG["source_project"])
        print(f"[OK] Source project found: {source_project.name} (ID: {source_project.id})")

        duplication_config = CrossDuplicationConfig(
            match_users_by_login=CONFIG["match_users_by_login"]
        )

        print("[INFO] Starting duplication job")
        print(f"[INFO] Target project name: {CONFIG['target_project']}")
        print(f"[INFO] match_users_by_login={CONFIG['match_users_by_login']}")
        print(f"[INFO] sync_with_target_env={CONFIG['sync_with_target_env']}")

        job = source_project.duplicate_to_other_environment(
            target_name=CONFIG["target_project"],
            target_env=target_conn,
            cross_duplication_config=duplication_config,
            sync_with_target_env=CONFIG["sync_with_target_env"],
        )

        print(f"[INFO] Job created: id={job.id} initial_status={job.status}")
        print("[SUCCESS] Duplication job initiated successfully.")
        print(f"[INFO] Check the target environment for project: '{CONFIG['target_project']}'")
        print(f"[INFO] Target: {CONFIG['target_base_url']}")

        print("\n[INFO] Waiting 10 seconds before listing projects on target...")
        time.sleep(10)

        print("\n[INFO] Projects on target environment:")
        env = Environment(target_conn)
        for p in env.list_projects():
            marker = " <-- NEW" if p.name == CONFIG["target_project"] else ""
            print(f"  - {p.name} (ID: {p.id}){marker}")

        return 0

    except Exception as exc:
        error_str = str(exc)
        print(f"[ERROR] Duplication test failed: {exc}")
        if "ERR001" in error_str and "duplication status" in error_str.lower():
            print()
            print("[DIAGNOSTIC] This error typically means StorageService is not configured")
            print("             between the two environments.")
            print("             To fix this:")
            print("             1. On the SOURCE environment, go to:")
            print("                Administration > Storage Service > Settings")
            print("                and configure a shared storage location.")
            print("             2. On the TARGET environment, configure the same")
            print("                shared storage location.")
            print("             3. Ensure both environments can reach the storage.")
            print("             4. Re-run this script once StorageService is set up.")
        return 1

    finally:
        if target_conn is not None:
            try:
                target_conn.close()
                print("[INFO] Target connection closed")
            except Exception as exc:
                print(f"[WARN] Could not close target connection cleanly: {exc}")

        if source_conn is not None:
            try:
                source_conn.close()
                print("[INFO] Source connection closed")
            except Exception as exc:
                print(f"[WARN] Could not close source connection cleanly: {exc}")


def main() -> int:
    return run_duplication()


if __name__ == "__main__":
    sys.exit(main())
