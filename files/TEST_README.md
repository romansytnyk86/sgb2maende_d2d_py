# Multi-Project Deployment Test

This folder contains test files to verify that the deployment tool works correctly with multiple projects in a loop.

## Test Files Created

### Environment Files
- `deployment.projectA.env` - Configuration for Test Scenario A
- `deployment.projectB.env` - Configuration for Test Scenario B
- `deployment.projectC.env` - Configuration for Test Scenario C

All files use the same real project "SGB II Falke Rechtsbehelfe (BA)" but with different:
- Backup project names (to avoid conflicts)
- Database catalogs (con_project_a_test, con_project_b_test, con_project_c_test)

This simulates deploying the same project multiple times with different backup and DB configurations.

### Test Scripts
- `test_multi_project.bat` - Windows batch script
- `test_multi_project.ps1` - PowerShell script

## How to Run the Test

### Option 1: Batch Script (Windows)
```cmd
test_multi_project.bat
```

### Option 2: PowerShell Script
```powershell
.\test_multi_project.ps1
```

### Option 3: Manual Loop
```cmd
for %e in (deployment.projectA.env deployment.projectB.env deployment.projectC.env) do (
    python main.py mit-backup --backup-month 202512 --env %e --dry-run
)
```

## What the Test Does

1. Runs deployment for Project A (dry-run)
2. Runs deployment for Project B (dry-run)
3. Runs deployment for Project C (dry-run)
4. Verifies no lock conflicts between sequential runs
5. Confirms each project uses its own configuration

## Expected Output

You should see:
- Each project deploys successfully
- Different project names in the logs
- No "deployment already in progress" errors
- Sequential execution without conflicts

## For Real Deployments

Replace `--dry-run` with actual deployment commands:
```bash
python main.py mit-backup --backup-month 202512 --env deployment.projectA.env
```

The lock mechanism ensures safe sequential execution across multiple projects.