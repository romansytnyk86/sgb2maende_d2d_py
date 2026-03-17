# Test script for multi-project deployment loop
# Run this to test deploying to multiple projects sequentially

Write-Host "Starting multi-project deployment test..." -ForegroundColor Green
Write-Host ""

$envFiles = @("deployment.projectA.env", "deployment.projectB.env", "deployment.projectC.env")

foreach ($envFile in $envFiles) {
    Write-Host "========================================" -ForegroundColor Yellow
    Write-Host "Deploying project with config: $envFile" -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Yellow

    # Wait for any existing deployment to finish (lock file cleared)
    $maxRetries = 60
    $retry = 0
    while (Test-Path ".deployment_lock") {
        if ($retry -ge $maxRetries) {
            Write-Host "ERROR: Lock file still exists after waiting. Aborting." -ForegroundColor Red
            exit 1
        }
        Write-Host "Lock file exists; waiting 5s..." -ForegroundColor Yellow
        Start-Sleep -Seconds 5
        $retry++
    }

    # Run the deployment (dry-run for testing)
    & python main.py mit-backup --backup-month 202512 --env $envFile --dry-run

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Deployment failed for $envFile" -ForegroundColor Red
        exit 1
    }

    Write-Host "Deployment completed for $envFile" -ForegroundColor Green
    Write-Host ""
}

Write-Host "All projects deployed successfully!" -ForegroundColor Green