"""
mstr/connection.py - MicroStrategy connection factory.

Provides a reusable context manager that opens and cleanly closes
a MicroStrategy connection. Used by all workflow steps.
"""

import logging
import traceback
from contextlib import contextmanager
from typing import Optional

from mstrio.connection import Connection
from config import MstrConfig

logger = logging.getLogger("sgb2_maende")


@contextmanager
def mstr_connection(cfg: MstrConfig, project_name: Optional[str] = None):
    """
    Context manager that opens a MicroStrategy connection and closes it on exit.

    Logs connection open/close at DEBUG level (visible in log file, not console).
    Any error during close is logged as a warning rather than raised, so it
    does not mask the original workflow error.

    Args:
        cfg:          MstrConfig (from deployment.env Section 1)
        project_name: Optional project context. Leave None for server-level
                      operations (load/unload, duplication, security roles).
    """
    conn = None
    try:
        logger.debug(
            f"Opening connection -> {cfg.base_url} "
            f"(user: {cfg.username}, "
            f"project: {project_name or 'server-level'})"
        )
        conn = Connection(
            base_url=cfg.base_url,
            username=cfg.username,
            password=cfg.password,
            login_mode=cfg.login_mode,
            **({"project_name": project_name} if project_name else {}),
        )
        logger.debug("Connection established")
        yield conn

    except Exception as exc:
        logger.error(f"Failed to connect to {cfg.base_url}: {exc}")
        logger.debug(traceback.format_exc())
        raise  # re-raise so the workflow step catches it and fails cleanly

    finally:
        if conn:
            try:
                conn.close()
                logger.debug("Connection closed")
            except Exception as exc:
                # Don't let a close error hide the real error
                logger.warning(f"Error while closing connection (non-critical): {exc}")
