@echo off
REM Test script for multi-project deployment loop
REM Run this to test deploying to multiple projects sequentially

echo Starting multi-project deployment test...
echo.

set PROJECTS=deployment.projectA.env deployment.projectB.env deployment.projectC.env

for %%e in (%PROJECTS%) do (
    echo ========================================
    echo Deploying project with config: %%e
    echo ========================================

    rem Wait for any existing deployment lock to clear (up to 5 minutes)
    set /a WAIT_COUNT=0
    :WAIT_LOCK
    if exist .deployment_lock (
        if %WAIT_COUNT% geq 60 (
            echo ERROR: Lock file still exists after waiting. Aborting.
            exit /b 1
        )
        echo Lock file detected, waiting 5s...
        timeout /t 5 /nobreak >nul
        set /a WAIT_COUNT+=1
        goto WAIT_LOCK
    )

    python main.py mit-backup --backup-month 202512 --env %%e --dry-run

    if errorlevel 1 (
        echo ERROR: Deployment failed for %%e
        exit /b 1
    )

    echo Deployment completed for %%e
    echo.
)

echo All projects deployed successfully!
pause