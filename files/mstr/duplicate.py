"""
mstr/duplicate.py - Duplicate a MicroStrategy project (backup step).

Replaces ProjectDuplicate.exe / D_SGB_II_MaEnde_D2D.xml.

Uses mstrio-py:
    Project.duplicate(config=DuplicationConfig(...))
    ProjectDuplication  - job object with status polling
    ProjectDuplicationStatus - terminal state enum
"""

import logging
import time
from datetime import datetime

from mstrio.connection import Connection
from mstrio.server.project import (
    DuplicationConfig,
    Project,
    ProjectDuplication,
    ProjectDuplicationStatus,
    list_projects,
)

logger = logging.getLogger("sgb2_maende")

POLL_INTERVAL_S = 20
POLL_TIMEOUT_MIN = 60


def _resolve_target_name(conn: Connection, desired_name: str) -> str:
    """
    Return a unique target project name.
    If `desired_name` already exists, append a timestamp suffix.
    """
    existing = {p["name"].lower() for p in list_projects(conn, to_dictionary=True)}

    if desired_name.lower() not in existing:
        return desired_name

    # Name taken - append timestamp
    candidate = f"{desired_name} {datetime.now().strftime('%Y%m%d_%H%M%S')}"
    counter = 1
    base = candidate
    while candidate.lower() in existing:
        candidate = f"{base}_{counter}"
        counter += 1

    logger.warning(
        f"  [WARN] '{desired_name}' already exists. "
        f"Using auto-generated name: '{candidate}'"
    )
    return candidate


def _poll_duplication(job: ProjectDuplication) -> bool:
    """
    Poll a ProjectDuplication job until it reaches a terminal state.
    Returns True on success, False on failure or timeout.
    """
    timeout_s = POLL_TIMEOUT_MIN * 60
    start = time.time()

    logger.info(f"  Polling job {job.id} (timeout: {POLL_TIMEOUT_MIN} min)...")

    while time.time() - start < timeout_s:
        try:
            job.fetch()
        except Exception as exc:
            logger.warning(f"    [WARN] Status fetch failed, will retry: {exc}")
            time.sleep(POLL_INTERVAL_S)
            continue

        elapsed = int(time.time() - start)
        status_str = str(job.status).upper()
        progress = getattr(job, "progress", None)
        progress_s = f" | {progress}%" if progress is not None else ""
        logger.info(f"    [{elapsed:>4}s] {job.status}{progress_s}")

        if "COMPLETE" in status_str:
            logger.info(f"  [OK] Duplication completed after {elapsed}s")
            return True
        if "FAILED" in status_str or "CANCEL" in status_str:
            msg = getattr(job, "message", "")
            logger.error(f"  [ERROR] Duplication ended: {job.status}" + (f" | {msg}" if msg else ""))
            return False

        time.sleep(POLL_INTERVAL_S)

    logger.error(f"  [ERROR] Timeout after {POLL_TIMEOUT_MIN} minutes")
    return False


def duplicate_project(
    conn: Connection,
    source_project_name: str,
    target_project_name: str,
    description: str = "",
) -> bool:
    """
    Duplicate a MicroStrategy project (backup step).

    Replaces: ProjectDuplicate.exe -f D_SGB_II_MaEnde_D2D.xml ...

    Args:
        conn:                Active server-level MicroStrategy connection
        source_project_name: Name of the project to duplicate
        target_project_name: Desired name for the backup project
        description:         Optional description for the backup project

    Returns True on success.
    """
    logger.info(
        f"Duplicating project '{source_project_name}' -> '{target_project_name}'..."
    )
    try:
        # Resolve name conflicts
        final_name = _resolve_target_name(conn, target_project_name)

        # Get source project
        source = Project(connection=conn, name=source_project_name)
        logger.info(f"  Source: '{source.name}' (ID: {source.id})")
        logger.info(f"  Target: '{final_name}'")

        # Build config and start job
        config = DuplicationConfig(
            import_description=description or f"Backup of '{source_project_name}'",
        )

        logger.info("  Starting duplication job (this may take several minutes)...")
        job = source.duplicate(target_name=final_name, duplication_config=config)
        logger.info(f"  Job ID: {job.id} | Initial status: {job.status}")

        # Poll to completion
        success = _poll_duplication(job)

        if success:
            logger.info(f"  [OK] Backup project '{final_name}' created successfully")
        else:
            logger.error(f"  [ERROR] Duplication of '{source_project_name}' failed")

        return success

    except Exception as exc:
        logger.error(f"  [ERROR] Unexpected error during duplication: {exc}")
        return False
