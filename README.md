# SGB II MaEnde - MicroStrategy Deployment Tool

Replaces the original BAT + CommandManager + ProjectDuplicate.exe workflow with pure Python.

## What it replaces

| Original file | Replaced by |
|---|---|
| `BAT_SGB_II_MaEnde_D2D_ohne_PD.BAT` | `python main.py ohne-backup` |
| `BAT_SGB_II_MaEnde_D2D.BAT` | `python main.py mit-backup --backup-month YYYYMM` |
| `CM_SGB_II_MaEnde_ohne_PD.scp` | `workflows/ohne_backup.py` |
| `CM_SGB_II_MaEnde_nach_PD.scp` | `workflows/mit_backup.py` |
| `ProjectDuplicate.exe` + `D_SGB_II_MaEnde_D2D.xml` | `mstr/duplicate.py` |

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Edit `files/deployment.env`:

```env
MSTR_BASE_URL=http://your-server:8080/MicroStrategyLibrary
MSTR_USERNAME=Administrator
MSTR_PASSWORD=your_password
MSTR_LOGIN_MODE=1

MSTR_PROJECT_NAME=SGB II MaEnde
DB_CONNECTION_NAME=SGB II - MaEnde - MaEnde - MSAS@DST_BICOMSTRSQLSVC
DB_CATALOG_NAME=SGB2_MaEnde

# Role|Group pairs to revoke from backup project (comma-separated)
REVOKE_ROLE_GROUP_PAIRS=Normale Benutzer|Everyone,Normale Benutzer|SGB II Projektzugriff,Normale Benutzer|SGB II Projektzugriff IT
```

## Usage

### Without backup (replaces `BAT_SGB_II_MaEnde_D2D_ohne_PD.BAT`)
```bash
python main.py ohne-backup
```

### With backup (replaces `BAT_SGB_II_MaEnde_D2D.BAT`)
```bash
python main.py mit-backup --backup-month 202512
```

### Cross-environment duplication
```bash
python main.py mit-backup --backup-month 202512 \
  --target-base-url http://10.146.13.45:8080/MicroStrategyLibrary/ \
  --target-username USER --target-password PASS
```

### Target environment via deployment.env
You can also configure the target environment directly in `deployment.env` using:
- `TARGET_MSTR_BASE_URL`
- `TARGET_MSTR_USERNAME`
- `TARGET_MSTR_PASSWORD`
- `TARGET_MSTR_LOGIN_MODE`

If those variables are set, the tool will use the target environment automatically for cross-environment duplication.

### Preview steps without executing
```bash
python main.py ohne-backup --dry-run
python main.py mit-backup --backup-month 202512 --dry-run
```

### Custom credentials file
```bash
python main.py ohne-backup --env /absolute/path/to/credentials.env
```

Relative paths are resolved against the `files/` directory, so `--env deployment.env` will load `files/deployment.env`.

## Workflow Flags

You can control which steps are executed by setting flags in `deployment.env`:

- `ENABLE_DB_CATALOG_CHANGE=true`  # Set to `false` to skip altering the DB connection catalog
- `ENABLE_SCHEMA_UPDATE=false`     # Set to `true` to run schema updates after loading projects
- `ENABLE_SECURITY_ROLE_REVOCATION=true`  # Set to `false` to skip revoking roles from backup projects

This allows you to customize the deployment process based on your needs.

## Concurrent Deployments

The tool uses a lock file (`.deployment_lock`) to prevent concurrent deployments on the same server. If you run multiple deployments in parallel (e.g., for different projects), the second one will fail with an error message. Wait for the first deployment to complete before starting the next one.

If a deployment crashes and leaves a stale lock file, you can safely remove `.deployment_lock` manually.

**Note on shared DB connections:** If multiple projects share the same `DB_CONNECTION_NAME`, altering the catalog during deployment may temporarily affect other loaded projects using that connection. To avoid issues, ensure other projects are unloaded or use project-specific DB connections.

## Project structure

```
sgb2_maende/
├── main.py                  # CLI entry point
├── config.py                # Credentials/config loader
├── credentials.env          # Connection settings (edit this)
├── requirements.txt
│
├── mstr/
│   ├── connection.py        # Connection context manager
│   ├── project.py           # load / unload / disconnect users
│   ├── dbconnection.py      # ALTER DBCONNECTION catalog
│   ├── security.py          # GRANT / REVOKE SECURITY ROLE
│   └── duplicate.py         # Project duplication (replaces ProjectDuplicate.exe)
│
├── workflows/
│   ├── ohne_backup.py       # "ohne PD" - 4 steps
│   └── mit_backup.py        # "nach PD" - 7 steps
│
└── utils/
    └── logger.py            # Console + file logging
```

## Logging

Every run writes to both the **console** (clean output, INFO level) and a **log file** (detailed, DEBUG level).

The log file location is set by `LOG_DIR` and `LOG_FILE_NAME` in `credentials.env`. Default: `LOG_SGB II MaEnde.txt` in the same folder.

Each run is clearly separated in the file:
```
============================================================
RUN STARTED: 2025-12-01 09:14:32  |  command: mit-backup
============================================================
2025-12-01 09:14:33 | INFO     | [Step 1/7] Disconnect user connections
2025-12-01 09:14:35 | INFO     |   [OK] All users disconnected
2025-12-01 09:14:35 | DEBUG    | Opening connection -> http://localhost:8080/...
...
2025-12-01 09:18:02 | INFO     |   Duration: 0:03:29
2025-12-01 09:18:02 | INFO     |   [SUCCESS] Workflow completed successfully
============================================================
RUN FINISHED: 2025-12-01 09:18:02  |  SUCCESS  |  Duration: 0:03:29
============================================================
```

- **Full exception tracebacks** go to the log file only (not shown on console)
- **Log rotation**: max 5 MB per file, 5 backups kept automatically (`LOG_....txt`, `.1` → `.5`)
- **DB connection strings** (before/after) are logged at DEBUG level for audit trail

## Workflow steps

### `ohne-backup` (4 steps)
1. Disconnect user connections from project
2. Unload project
3. Alter DB connection catalog
4. Load project

### `mit-backup` (7 steps)
1. Disconnect user connections from project
2. Unload project
3. **Duplicate project** → backup (e.g. `SGB II MaEnde 202512`)
4. Alter DB connection catalog
5. Load main project
6. Load backup project
7. Revoke security roles from backup project
