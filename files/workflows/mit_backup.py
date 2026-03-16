"""
workflows/mit_backup.py - Deployment WITH project backup (nach PD).

Replaces: BAT_SGB_II_MaEnde_D2D.BAT + CM_SGB_II_MaEnde_nach_PD.scp
          + ProjectDuplicate.exe + D_SGB_II_MaEnde_D2D.xml

When to use:
    Use this at the start of a new deployment cycle when you want to keep
    a snapshot of the current project before redeploying (e.g. month-end).
    The backup project gets all user access removed so end users cannot
    accidentally open it.

    Command: python main.py mit-backup --backup-month 202512 [--env deployment.env]
    The --backup-month value is appended to BACKUP_PROJECT_BASE_NAME, e.g.:
        "SGB II MaEnde" + "202512" -> "SGB II MaEnde 202512"

Steps:
    1. Disconnect all active users from the main project
    2. Unload the main project
    3. Duplicate the main project -> creates the backup project
    4. Update the DB connection catalog on the main project
    5. Reload the main project
    6. Load the backup project
    7. Revoke all user access from the backup project

Settings used from deployment.env:
    MSTR_PROJECT_NAME           - the main project to redeploy
    BACKUP_PROJECT_BASE_NAME    - base name for the backup project
    DB_CONNECTION_NAME          - which datasource connection to update
    DB_CATALOG_NAME             - the new catalog name to set
    REVOKE_ROLE_GROUP_PAIRS     - which role/group access to remove from backup
"""

import logging
from datetime import datetime
from config import AppConfig
from mstr import (
    mstr_connection,
    disconnect_users,
    unload_project,
    duplicate_project,
    alter_db_connection_catalog,
    load_project,
    revoke_security_role,
)

logger = logging.getLogger("sgb2_maende")


def run(cfg: AppConfig, backup_month: str) -> bool:
    """
    Execute the with-backup deployment workflow.

    Args:
        cfg:          All settings loaded from deployment.env
        backup_month: The month suffix passed via --backup-month (e.g. "202512")

    Returns True if all steps succeeded, False if any step failed.
    """
    project = cfg.project.project_name
    backup_project = f"{cfg.project.backup_base_name} {backup_month}"
    steps_ok = []
    start = datetime.now()

    logger.info("")
    logger.info("=" * 60)
    logger.info("  WORKFLOW: mit Backup (with backup / nach PD)")
    logger.info(f"  Project:        {project}")
    logger.info(f"  Backup project: {backup_project}")
    logger.info(f"  Server:         {cfg.mstr.base_url}")
    logger.info("=" * 60)

    with mstr_connection(cfg.mstr) as conn:

        # ── Step 1: Disconnect users ──────────────────────────────────
        # Kicks all active user sessions off the project so it can be unloaded.
        # Admin/service sessions that cannot be disconnected are expected
        # and reported as warnings — they do not cause a failure.
        logger.info("\n[Step 1/7] Disconnect user connections")
        ok = disconnect_users(conn, project)
        steps_ok.append(("Disconnect users", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return _summary(steps_ok, start)

        # ── Step 2: Duplicate project (create backup) ─────────────────
        # Creates a full copy of the main project named e.g. "SGB II MaEnde 202512".
        # This is an async server-side operation that is polled until complete.
        # Replaces: ProjectDuplicate.exe + D_SGB_II_MaEnde_D2D.xml
        logger.info("\n[Step 2/7] Duplicate project (create backup)")
        ok = duplicate_project(
            conn,
            source_project_name=project,
            target_project_name=backup_project,
            description=f"Backup of '{project}' ({backup_month})",
        )
        steps_ok.append(("Duplicate project (backup)", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return _summary(steps_ok, start)

        # ── Step 3: Unload main project ───────────────────────────────
        # Takes the project offline. Required before updating the DB connection.
        logger.info("\n[Step 3/7] Unload main project")
        ok = unload_project(conn, project)
        steps_ok.append(("Unload project", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return _summary(steps_ok, start)

        # ── Step 4: Alter DB connection catalog ───────────────────────
        # Updates the CATALOG in the datasource connection string on the main project.
        # Equivalent to: ALTER DBCONNECTION "..." CATALOG "..."
        # Values come from DB_CONNECTION_NAME and DB_CATALOG_NAME in deployment.env
        logger.info("\n[Step 4/7] Alter DB connection catalog")
        ok = alter_db_connection_catalog(
            conn,
            connection_name=cfg.project.db_connection_name,
            new_catalog=cfg.project.db_catalog_name,
        )
        steps_ok.append(("Alter DB connection", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return _summary(steps_ok, start)

        # ── Step 5: Load main project ─────────────────────────────────
        # Brings the main project back online for end users.
        logger.info("\n[Step 5/7] Load main project")
        ok = load_project(conn, project)
        steps_ok.append(("Load main project", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return _summary(steps_ok, start)

        # ── Step 6: Load backup project ───────────────────────────────
        # Loads the newly created backup project so security roles can be revoked.
        # After Step 7 it will be inaccessible to regular users.
        logger.info("\n[Step 6/7] Load backup project")
        ok = load_project(conn, backup_project)
        steps_ok.append(("Load backup project", ok))
        if not ok:
            logger.error("  Aborting workflow due to step failure.")
            return _summary(steps_ok, start)

        # ── Step 7: Revoke security roles from backup project ─────────
        # Removes all user group access from the backup project so end users
        # cannot accidentally connect to it.
        # Pairs to revoke come from REVOKE_ROLE_GROUP_PAIRS in deployment.env.
        # Equivalent to: REVOKE SECURITY ROLE "..." FROM GROUP "..." FROM PROJECT "..."
        logger.info("\n[Step 7/7] Revoke security roles from backup project")
        if not cfg.project.revoke_role_group_pairs:
            logger.warning("  [WARN] REVOKE_ROLE_GROUP_PAIRS is empty in deployment.env — skipping")
            steps_ok.append(("Revoke security roles", True))
        else:
            all_revoked = True
            for role_name, group_name in cfg.project.revoke_role_group_pairs:
                ok = revoke_security_role(conn, role_name, group_name, backup_project)
                if not ok:
                    all_revoked = False
            steps_ok.append(("Revoke security roles", all_revoked))

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
