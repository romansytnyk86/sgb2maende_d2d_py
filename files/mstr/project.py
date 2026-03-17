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
from mstrio.server.cluster import Cluster
from mstrio.users_and_groups.user_connections import UserConnections

logger = logging.getLogger("sgb2_maende")


def disconnect_users(conn: Connection, project_name: str) -> bool:
    """
    Disconnect all active user sessions from a project (on all cluster nodes if applicable).
    CM equivalent: DISCONNECT USER CONNECTIONS FROM PROJECT "..."

    Admin/service sessions that cannot be disconnected are expected and
    reported as warnings — they do not cause a failure.
    Returns True if the step should be considered successful.
    """
    logger.info(f"  Disconnecting users from '{project_name}'...")
    try:
        cluster = Cluster(connection=conn)
        nodes = cluster.list_nodes()
        if len(nodes) > 1:
            # Cluster: disconnect on each node
            logger.info(f"  Cluster detected with {len(nodes)} nodes, disconnecting on all nodes...")
            base_url = conn.base_url
            import urllib.parse
            parsed = urllib.parse.urlparse(base_url)
            port = parsed.port or 8080
            path = parsed.path
            scheme = parsed.scheme
            for node in nodes:
                node_host = node.address if hasattr(node, 'address') else node.get('address', node.get('name'))
                node_url = f"{scheme}://{node_host}:{port}{path}"
                try:
                    node_conn = Connection(
                        base_url=node_url,
                        username=conn.username,
                        password=conn.password,
                        login_mode=conn.login_mode,
                        project_name=project_name
                    )
                    uc = UserConnections(node_conn)
                    uc.disconnect_all_users(force=True)
                    remaining = uc.list_connections()
                    if remaining:
                        logger.warning(f"  Node {node_host}: {len(remaining)} session(s) could not be disconnected")
                    node_conn.close()
                except Exception as node_exc:
                    logger.warning(f"  Failed to disconnect on node {node_host}: {node_exc}")
            logger.info(f"  [OK] Disconnection attempted on all cluster nodes for '{project_name}'")
        else:
            # Single server
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
        logger.error(f"  [ERROR] Failed to disconnect users from '{project_name}': {exc}")
        logger.debug(traceback.format_exc())
        return False
        msg = str(exc).lower()
        if "no session" in msg or "no active" in msg:
            logger.info(f"  [OK] No active users on '{project_name}'")
            return True
        logger.error(f"  [ERROR] Failed to disconnect users from '{project_name}': {exc}")
        logger.debug(traceback.format_exc())  # full traceback in log file only
        return False


def unload_project(conn: Connection, project_name: str) -> bool:
    """
    Unload a project from the Intelligence Server (or all cluster nodes).
    CM equivalent: UNLOAD PROJECT "..."
    Returns True on success.
    """
    logger.info(f"  Unloading '{project_name}'...")
    try:
        cluster = Cluster(connection=conn)
        nodes = cluster.list_nodes()
        if len(nodes) > 1:
            # Cluster environment: unload on all nodes
            logger.info(f"  Cluster detected with {len(nodes)} nodes, unloading on all nodes...")
            cluster.unload_project(project_name)
        else:
            # Single server: use project unload
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
    Load a project on the Intelligence Server (or all cluster nodes).
    CM equivalent: LOAD PROJECT "..."
    Returns True on success.
    """
    logger.info(f"  Loading '{project_name}'...")
    try:
        cluster = Cluster(connection=conn)
        nodes = cluster.list_nodes()
        if len(nodes) > 1:
            # Cluster environment: load on all nodes
            logger.info(f"  Cluster detected with {len(nodes)} nodes, loading on all nodes...")
            cluster.load_project(project_name)
        else:
            # Single server: find and load the project
            env = Environment(connection=conn)
            projects = env.list_projects()
            for project in projects:
                if hasattr(project, "name") and project.name == project_name:
                    project.load()
                    break
            else:
                logger.error(f"  [ERROR] Project '{project_name}' not found on server")
                return False
        logger.info(f"  [OK] Project '{project_name}' loaded")
        return True
    except Exception as exc:
        logger.error(f"  [ERROR] Failed to load '{project_name}': {exc}")
        logger.debug(traceback.format_exc())
        return False
