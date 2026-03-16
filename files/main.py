#!/usr/bin/env python3
"""
main.py - SGB II MaEnde deployment CLI.

Replaces the two BAT scripts + cmdmgr + ProjectDuplicate.exe.

Commands
--------
ohne-backup   Deployment on a single server, no backup
mit-backup    Deployment on a single server, with project backup

Usage
-----
python main.py ohne-backup [--env FILE]
python main.py mit-backup --backup-month 202512 [--env FILE]
python main.py <command> --dry-run
"""

import argparse
import sys
import os
from datetime import datetime

# Ensure all modules (config, utils, mstr, workflows) are findable
# regardless of which directory Python is launched from.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import load_config
from utils.logger import setup_logger
from utils.logger import log_run_footer
import workflows.ohne_backup as workflow_ohne
import workflows.mit_backup as workflow_mit


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="sgb2_maende",
        description="SGB II MaEnde - MicroStrategy deployment tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py ohne-backup
  python main.py ohne-backup --env deployment.local.env
  python main.py mit-backup --backup-month 202512
  python main.py mit-backup --backup-month 202512 --env deployment.customer.env

  # Preview steps without connecting:
  python main.py ohne-backup --dry-run
  python main.py mit-backup --backup-month 202512 --dry-run
        """,
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # ── ohne-backup ──────────────────────────────────────────────────────────
    ohne = subparsers.add_parser(
        "ohne-backup",
        help="Deployment WITHOUT backup (ohne PD)",
        description="Steps: disconnect users -> unload -> alter DB connection -> load",
    )
    ohne.add_argument(
        "--env",
        metavar="FILE",
        default="deployment.env",
        help="Credentials file (default: deployment.env)",
    )
    ohne.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned steps without connecting to MicroStrategy",
    )

    # ── mit-backup ───────────────────────────────────────────────────────────
    mit = subparsers.add_parser(
        "mit-backup",
        help="Deployment WITH project backup (nach PD)",
        description=(
            "Steps: disconnect users -> unload -> duplicate (backup) -> "
            "alter DB connection -> load main -> load backup -> revoke security roles"
        ),
    )
    mit.add_argument(
        "--env",
        metavar="FILE",
        default="deployment.env",
        help="Credentials file (default: deployment.env)",
    )
    mit.add_argument(
        "--backup-month",
        required=True,
        metavar="YYYYMM",
        help="Month suffix for backup project name (e.g. 202512 -> 'SGB II MaEnde 202512')",
    )
    mit.add_argument(
        "--dry-run",
        action="store_true",
        help="Print planned steps without connecting to MicroStrategy",
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
    print(f"    3. Alter DB connection '{cfg.project.db_connection_name}'"
          f" -> catalog '{cfg.project.db_catalog_name}'")
    print(f"    4. Load '{cfg.project.project_name}'")
    print("-" * 56)


def print_dry_run_mit(cfg, backup_month: str) -> None:
    backup_project = f"{cfg.project.backup_base_name} {backup_month}"
    print("\n[DRY RUN] mit-backup workflow")
    print("-" * 56)
    print(f"  Server:         {cfg.mstr.base_url}")
    print(f"  User:           {cfg.mstr.username}")
    print(f"  Project:        {cfg.project.project_name}")
    print(f"  Backup project: {backup_project}")
    print()
    print("  Steps that would be executed:")
    print(f"    1. Disconnect users from '{cfg.project.project_name}'")
    print(f"    2. Duplicate '{cfg.project.project_name}' -> '{backup_project}'")
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

    cfg = load_config(env_file=args.env)
    logger = setup_logger(cfg.log.log_dir, cfg.log.log_file_name, command=args.command)

    logger.info("")
    logger.info("#" * 60)
    logger.info("  SGB II MaEnde - Deployment Tool")
    logger.info(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"  Command: {args.command}")
    logger.info(f"  Server:  {cfg.mstr.base_url}")
    logger.info(f"  Project: {cfg.project.project_name}")
    logger.info("#" * 60)

    if args.dry_run:
        if args.command == "ohne-backup":
            print_dry_run_ohne(cfg)
        else:
            print_dry_run_mit(cfg, args.backup_month)
        return 0

    if args.command == "ohne-backup":
        success = workflow_ohne.run(cfg)
    else:
        success = workflow_mit.run(cfg, backup_month=args.backup_month)

    log_run_footer(success)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())