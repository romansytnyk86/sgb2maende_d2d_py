"""
mstr/project.py - Project-level operations: disconnect users, load, unload.

Replaces these Command Manager commands:
    DISCONNECT USER CONNECTIONS FROM PROJECT "..."
    UNLOAD PROJECT "..."
    LOAD PROJECT "..."
"""

import logging
import traceback

from mstrio.connection import Connection
from mstrio.server import Environment
from mstrio.server.project import Project
from mstrio.users_and_groups.user_connections import UserConnections

logger = logging.getLogger("sgb2_maende")


def disconnect_users(conn: Connection, project_name: str) -> bool:
    """
    Disconnect all active user sessions from a project.
    CM equivalent: DISCONNECT USER CONNECTIONS FROM PROJECT "..."

    Admin/service sessions that cannot be disconnected are expected and
    reported as warnings — they do not cause a failure.
    Returns True if the step should be considered successful.
    """
    logger.info(f"  Disconnecting users from '{project_name}'...")
    try:
        uc = UserConnections(conn)
        uc.disconnect_all_users(force=True)

        remaining = uc.list_connections()
        if remaining:
            logger.warning(f"  {len(remaining)} session(s) could not be disconnected "
                           "(likely admin/service sessions — safe to proceed):")
            for s in remaining:
                logger.warning(
                    f"    User: {s.get('user_full_name', '?')} "
                    f"| App: {s.get('application_type', '?')} "
                    f"| Admin: {'Yes' if s.get('config_level') else 'No'}"
                )
        else:
            logger.info(f"  [OK] All users disconnected from '{project_name}'")

        return True

    except Exception as exc:
        msg = str(exc).lower()
        if "no session" in msg or "no active" in msg:
            logger.info(f"  [OK] No active users on '{project_name}'")
            return True
        logger.error(f"  [ERROR] Failed to disconnect users from '{project_name}': {exc}")
        logger.debug(traceback.format_exc())  # full traceback in log file only
        return False


def unload_project(conn: Connection, project_name: str) -> bool:
    """
    Unload a project from the Intelligence Server.
    CM equivalent: UNLOAD PROJECT "..."
    Returns True on success.
    """
    logger.info(f"  Unloading '{project_name}'...")
    try:
        project = Project(connection=conn, name=project_name)
        project.unload()
        logger.info(f"  [OK] Project '{project_name}' unloaded")
        return True
    except Exception as exc:
        logger.error(f"  [ERROR] Failed to unload '{project_name}': {exc}")
        logger.debug(traceback.format_exc())
        return False


def load_project(conn: Connection, project_name: str) -> bool:
    """
    Load a project on the Intelligence Server.
    CM equivalent: LOAD PROJECT "..."
    Returns True on success.
    """
    logger.info(f"  Loading '{project_name}'...")
    try:
        env = Environment(connection=conn)
        projects = env.list_projects()

        for project in projects:
            if hasattr(project, "name") and project.name == project_name:
                project.load()
                logger.info(f"  [OK] Project '{project_name}' loaded")
                return True

        logger.error(f"  [ERROR] Project '{project_name}' not found on server")
        return False

    except Exception as exc:
        logger.error(f"  [ERROR] Failed to load '{project_name}': {exc}")
        logger.debug(traceback.format_exc())
        return False
