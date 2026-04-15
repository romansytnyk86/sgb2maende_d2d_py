#!/usr/bin/env python3
"""
main.py - SGB II MaEnde deployment CLI.

Replaces the two BAT scripts + cmdmgr + ProjectDuplicate.exe.

Workflow is controlled by CREATE_BACKUP flag in deployment.env:
- CREATE_BACKUP=false: ohne-backup (no backup)
- CREATE_BACKUP=true:  mit-backup (with backup)

Usage
-----
python main.py [--env FILE] [--backup-month YYYYMM] [--dry-run]
"""

import argparse
import sys
import os
from datetime import datetime
from typing import Optional

# Ensure all modules (config, utils, mstr, workflows) are findable
# regardless of which directory Python is launched from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config, MstrConfig
from utils.logger import setup_logger
from utils.logger import log_run_footer
import workflows.deployment_without_backup_none as workflow_ohne
import workflows.deployment_with_backup_duplication as workflow_mit
import workflows.deployment_with_backup_merge as workflow_merge


LOCK_FILE = ".deployment_lock"


def acquire_lock() -> bool:
    """
    Create a lock file to prevent concurrent deployments.
    Returns True if lock acquired, False if already locked.
    """
    if os.path.exists(LOCK_FILE):
        print(f"ERROR: Deployment already in progress (lock file {LOCK_FILE} exists).")
        print("Wait for the current deployment to complete or remove the lock file if it's stale.")
        return False
    try:
        with open(LOCK_FILE, 'w') as f:
            f.write(f"Locked at {datetime.now()}\n")
        return True
    except Exception as e:
        print(f"ERROR: Failed to create lock file: {e}")
        return False


def release_lock():
    """Remove the lock file."""
    try:
        if os.path.exists(LOCK_FILE):
            os.remove(LOCK_FILE)
    except Exception as e:
        print(f"WARNING: Failed to remove lock file: {e}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sgb2_maende",
        description="SGB II MaEnde - MicroStrategy deployment tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py
  python main.py --env deployment.local.env
  python main.py --backup-month 202512
  python main.py --backup-month 202512 --env deployment.customer.env
  python main.py --backup-month 202512 --target-base-url http://10.146.13.45:8080/MicroStrategyLibrary/ --target-username admin --target-password secret

  # Preview steps without connecting:
  python main.py --dry-run
  python main.py --backup-month 202512 --dry-run
        """,
    )

    parser.add_argument(
        "--env",
        metavar="FILE",
        default="deployment.env",
        help="Credentials file (default: deployment.env)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned steps without connecting to MicroStrategy",
    )
    parser.add_argument(
        "--backup-month",
        metavar="YYYYMM",
        help="Month suffix for backup project name (overrides BACKUP_MONTH in config)",
    )
    parser.add_argument(
        "--target-base-url",
        metavar="URL",
        help="Target environment base URL for cross-environment duplication",
    )
    parser.add_argument(
        "--target-username",
        metavar="USER",
        help="Target environment username for cross-environment duplication",
    )
    parser.add_argument(
        "--target-password",
        metavar="PASS",
        help="Target environment password for cross-environment duplication",
    )
    parser.add_argument(
        "--target-login-mode",
        metavar="MODE",
        type=int,
        default=1,
        help="Target environment login mode (default: 1)",
    )

    return parser


def print_dry_run_ohne(cfg) -> None:
    print("\n[DRY RUN] ohne-backup workflow")
    print("-" * 56)
    print(f"  Server:  {cfg.mstr.base_url}")
    print(f"  User:    {cfg.mstr.username}")
    print(f"  Project: {cfg.project.project_name}")
    print()
    print("  Steps that would be executed:")
    print(f"    1. Disconnect users from '{cfg.project.project_name}'")
    print(f"    2. Unload '{cfg.project.project_name}'")
    if cfg.enable_db_catalog_change:
        print(f"    3. Alter DB connection '{cfg.project.db_connection_name}'"
              f" -> catalog '{cfg.project.db_catalog_name}'")
        print(f"    4. Load '{cfg.project.project_name}'")
    else:
        print("    3. Skip altering DB connection catalog (disabled in config)")
        print(f"    4. Load '{cfg.project.project_name}'")
    if cfg.enable_schema_update:
        print(f"    5. Update schema for '{cfg.project.project_name}'")
    else:
        print("    5. Skip schema update (disabled in config)")
    print("-" * 56)


def print_dry_run_mit(cfg, backup_month: str, target_mstr: Optional[MstrConfig] = None) -> None:
    backup_project = f"{cfg.project.backup_base_name} {backup_month}"
    if target_mstr:
        print("\n[DRY RUN] mit-backup workflow (cross-environment)")
    else:
        print("\n[DRY RUN] mit-backup workflow")
    print("-" * 56)
    print(f"  Source server:         {cfg.mstr.base_url}")
    print(f"  Source user:           {cfg.mstr.username}")
    if target_mstr:
        print(f"  Target server:         {target_mstr.base_url}")
        print(f"  Target user:           {target_mstr.username}")
    print(f"  Project:               {cfg.project.project_name}")
    print(f"  Backup project:        {backup_project}")
    print()
    print("  Steps that would be executed:")
    print(f"    1. Disconnect users from '{cfg.project.project_name}' on source environment")
    if target_mstr:
        method_desc = {
            "duplicate": f"Duplicate '{cfg.project.project_name}' to target environment as '{backup_project}'",
            "merge": f"Merge '{cfg.project.project_name}' to target environment as '{backup_project}' (NOT YET IMPLEMENTED)",
            "package": f"Create package from '{cfg.project.project_name}' and migrate to target environment as '{backup_project}'"
        }.get(cfg.project.backup_method, f"Unknown method '{cfg.project.backup_method}' for '{cfg.project.project_name}' to target environment")
        print(f"    2. {method_desc}")
        print(f"    3. Load '{backup_project}' on target environment")
        if cfg.project.revoke_role_group_pairs:
            for i, (role, group) in enumerate(cfg.project.revoke_role_group_pairs, 4):
                print(f"    {i}. Revoke '{role}' from '{group}' in '{backup_project}' on target environment")
    else:
        if cfg.project.backup_method == "package":
            print("    2. BACKUP_METHOD='package' is not supported for same-environment mit-backup.")
            print("    3. Provide a target environment or set BACKUP_METHOD='duplicate'.")
        else:
            print(f"    2. Duplicate '{cfg.project.project_name}' -> '{backup_project}'")
            print(f"    3. Unload '{cfg.project.project_name}'")
        if cfg.enable_db_catalog_change:
            print(f"    4. Alter DB connection '{cfg.project.db_connection_name}' -> catalog '{cfg.project.db_catalog_name}'")
            print(f"    5. Load '{cfg.project.project_name}'")
            print(f"    6. Load '{backup_project}'")
            if cfg.enable_schema_update:
                print(f"    7. Update schemas for '{cfg.project.project_name}' and '{backup_project}'")
                if cfg.enable_security_role_revocation and cfg.project.revoke_role_group_pairs:
                    for i, (role, group) in enumerate(cfg.project.revoke_role_group_pairs, 8):
                        print(f"    {i}. Revoke '{role}' from '{group}' in '{backup_project}'")
                else:
                    print("    8. Skip revoking security roles (disabled in config)")
            else:
                print("    7. Skip schema updates (disabled in config)")
                if cfg.enable_security_role_revocation and cfg.project.revoke_role_group_pairs:
                    for i, (role, group) in enumerate(cfg.project.revoke_role_group_pairs, 8):
                        print(f"    {i}. Revoke '{role}' from '{group}' in '{backup_project}'")
                else:
                    print("    8. Skip revoking security roles (disabled in config)")
        else:
            print("    4. Skip altering DB connection catalog (disabled in config)")
            print(f"    5. Load '{cfg.project.project_name}'")
            print(f"    6. Load '{backup_project}'")
            if cfg.enable_schema_update:
                print(f"    7. Update schemas for '{cfg.project.project_name}' and '{backup_project}'")
                if cfg.enable_security_role_revocation and cfg.project.revoke_role_group_pairs:
                    for i, (role, group) in enumerate(cfg.project.revoke_role_group_pairs, 8):
                        print(f"    {i}. Revoke '{role}' from '{group}' in '{backup_project}'")
                else:
                    print("    8. Skip revoking security roles (disabled in config)")
            else:
                print("    7. Skip schema updates (disabled in config)")
                if cfg.enable_security_role_revocation and cfg.project.revoke_role_group_pairs:
                    for i, (role, group) in enumerate(cfg.project.revoke_role_group_pairs, 8):
                        print(f"    {i}. Revoke '{role}' from '{group}' in '{backup_project}'")
                else:
                    print("    8. Skip revoking security roles (disabled in config)")
    print("-" * 56)


def print_dry_run_merge(cfg, backup_month: str) -> None:
    backup_project = f"{cfg.project.backup_base_name} {backup_month}"
    print("\n[DRY RUN] mit-backup-merge workflow")
    print("-" * 56)
    print(f"  Server:         {cfg.mstr.base_url}")
    print(f"  User:           {cfg.mstr.username}")
    print(f"  Project:        {cfg.project.project_name}")
    print(f"  Backup project: {backup_project}")
    print()
    print("  Steps that would be executed:")
    print(f"    1. Disconnect users from '{cfg.project.project_name}'")
    print(f"    2. Merge '{cfg.project.project_name}' -> '{backup_project}' (NOT YET IMPLEMENTED)")
    print(f"    3. Unload '{cfg.project.project_name}'")
    print(f"    4. Alter DB connection '{cfg.project.db_connection_name}'"
          f" -> catalog '{cfg.project.db_catalog_name}'")
    print(f"    5. Load '{cfg.project.project_name}'")
    print(f"    6. Load '{backup_project}'")
    for i, (role, group) in enumerate(cfg.project.revoke_role_group_pairs, 7):
        print(f"    {i}. Revoke '{role}' from '{group}' in '{backup_project}'")
    print("-" * 56)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    # Acquire lock to prevent concurrent deployments
    if not acquire_lock():
        return 1

    try:
        cfg = load_config(env_file=args.env)
        if (
            args.target_base_url or args.target_username or args.target_password
        ):
            missing_target = [
                name
                for name, value in [
                    ("--target-base-url", args.target_base_url),
                    ("--target-username", args.target_username),
                    ("--target-password", args.target_password),
                ]
                if not value
            ]
            if missing_target:
                parser.error(
                    "When using target environment options, all of "
                    "--target-base-url, --target-username and "
                    "--target-password must be provided."
                )

            cfg.target_mstr = MstrConfig(
                base_url=args.target_base_url,
                username=args.target_username,
                password=args.target_password,
                login_mode=args.target_login_mode,
            )

        # Determine workflow and backup month
        create_backup = cfg.create_backup
        backup_month = args.backup_month or cfg.backup_month
        if create_backup and not backup_month:
            parser.error("BACKUP_MONTH must be set in config or provided via --backup-month when CREATE_BACKUP=true")
        if create_backup and cfg.project.backup_method == "package" and cfg.target_mstr is None:
            parser.error(
                "BACKUP_METHOD=package requires a target environment. "
                "Set TARGET_MSTR_BASE_URL, TARGET_MSTR_USERNAME, TARGET_MSTR_PASSWORD "
                "in the config file or provide --target-* options."
            )

        command = "mit-backup" if create_backup else "ohne-backup"

        logger = setup_logger(cfg.log.log_dir, cfg.log.log_file_name, command=command)

        logger.info("")
        logger.info("#" * 60)
        logger.info("  SGB II MaEnde - Deployment Tool")
        logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"  Workflow: {command}")
        logger.info(f"  Server:   {cfg.mstr.base_url}")
        logger.info(f"  Project:  {cfg.project.project_name}")
        if create_backup:
            logger.info(f"  Backup:   {cfg.project.backup_base_name} {backup_month}")
        logger.info("#" * 60)

        if args.dry_run:
            if create_backup:
                print_dry_run_mit(
                    cfg,
                    backup_month,
                    target_mstr=cfg.target_mstr,
                )
            else:
                print_dry_run_ohne(cfg)
            return 0

        if create_backup:
            success = workflow_mit.run(
                cfg,
                backup_month=backup_month,
                target_mstr=cfg.target_mstr,
            )
        else:
            success = workflow_ohne.run(cfg)

        log_run_footer(success)
        return 0 if success else 1
    finally:
        release_lock()


if __name__ == "__main__":
    sys.exit(main())