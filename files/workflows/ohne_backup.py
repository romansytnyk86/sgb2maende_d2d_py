"""
workflows/ohne_backup.py - Deployment WITHOUT project backup.

Replaces: BAT_SGB_II_MaEnde_D2D_ohne_PD.BAT + CM_SGB_II_MaEnde_ohne_PD.scp

When to use:
    Use this when you only need to redeploy the project (e.g. switch the DB
    catalog for a new month) WITHOUT creating a backup copy first.

    Command: python main.py ohne-backup [--env deployment.env]

Steps:
    1. Disconnect all active users from the project
    2. Unload the project from the Intelligence Server
    3. Update the DB connection catalog (ALTER DBCONNECTION)
    4. Reload the project so users can connect again

Settings used from deployment.env:
    MSTR_PROJECT_NAME       - the project to redeploy
    DB_CONNECTION_NAME      - which datasource connection to update
    DB_CATALOG_NAME         - the new catalog name to set
"""

import logging
from datetime import datetime
from config import AppConfig
from mstr import (
    mstr_connection,
    disconnect_users,
    unload_project,
    alter_db_connection_catalog,
    load_project,
)

logger = logging.getLogger("sgb2_maende")


def run(cfg: AppConfig) -> bool:
    """
    Execute the without-backup deployment workflow.
    Returns True if all steps succeeded, False if any step failed.
    """
    project = cfg.project.project_name
    steps_ok = []
    start = datetime.now()

    logger.info("")
    logger.info("=" * 60)
    logger.info("  WORKFLOW: ohne Backup (without backup)")
    logger.info(f"  Project:  {project}")
    logger.info(f"  Server:   {cfg.mstr.base_url}")
    logger.info("=" * 60)

    with mstr_connection(cfg.mstr) as conn:

        # ── Step 1: Disconnect users ──────────────────────────────────
        # Kicks all active user sessions off the project so it can be unloaded.
        # Admin/service sessions that cannot be disconnected are expected
        # and reported as warnings — they do not cause a failure.
        logger.info("\n[Step 1/4] Disconnect user connections")
        ok = disconnect_users(conn, project)
        steps_ok.append(("Disconnect users", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return False

        # ── Step 2: Unload project ────────────────────────────────────
        # Takes the project offline on the Intelligence Server.
        # Required before the DB connection can be updated.
        logger.info("\n[Step 2/4] Unload project")
        ok = unload_project(conn, project)
        steps_ok.append(("Unload project", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return False

        # ── Step 3: Alter DB connection catalog ───────────────────────
        # Updates the CATALOG in the datasource connection string.
        # Equivalent to: ALTER DBCONNECTION "..." CATALOG "..."
        # Values come from DB_CONNECTION_NAME and DB_CATALOG_NAME in deployment.env
        logger.info("\n[Step 3/4] Alter DB connection catalog")
        ok = alter_db_connection_catalog(
            conn,
            connection_name=cfg.project.db_connection_name,
            new_catalog=cfg.project.db_catalog_name,
        )
        steps_ok.append(("Alter DB connection", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return False

        # ── Step 4: Load project ──────────────────────────────────────
        # Brings the project back online so users can connect again.
        logger.info("\n[Step 4/4] Load project")
        ok = load_project(conn, project)
        steps_ok.append(("Load project", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return False

    return _summary(steps_ok, start)


def _summary(steps_ok: list, start: datetime) -> bool:
    """Print a result table for each step, elapsed time, and return overall success."""
    duration = str(datetime.now() - start).split(".")[0]  # strip microseconds
    logger.info("")
    logger.info("=" * 60)
    logger.info("  WORKFLOW SUMMARY")
    logger.info("=" * 60)
    all_ok = True
    for step_name, result in steps_ok:
        status = "[OK]   " if result else "[FAIL]"
        logger.info(f"  {status} {step_name}")
        if not result:
            all_ok = False
    logger.info(f"\n  Duration: {duration}")
    if all_ok:
        logger.info("  [SUCCESS] Workflow completed successfully")
    else:
        logger.error("  [FAILED] Workflow completed with errors")
    logger.info("=" * 60)
    return all_ok
