param(
    [string]$ApiHost = "http://127.0.0.1:8000",
    [string]$LocustFile = "tests/performance/locust_stressfile.py",
    [string]$OutputDir = "artifacts/stress",
    [string]$StressRunId = "",
    [switch]$StartLocalApi,
    [switch]$AppendResults,
    [switch]$StrictSummary,
    [int]$ApiStartupTimeoutSeconds = 45
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Wait-ApiReady {
    param(
        [Parameter(Mandatory = $true)][string]$HostBase,
        [Parameter(Mandatory = $true)][int]$TimeoutSeconds
    )

    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    $healthUri = "$HostBase/api/v1/health"
    while ((Get-Date) -lt $deadline) {
        try {
            $response = Invoke-WebRequest -Uri $healthUri -UseBasicParsing -TimeoutSec 2
            if ($response.StatusCode -eq 200) {
                return
            }
        }
        catch {
            Start-Sleep -Milliseconds 700
        }
    }
    throw "API was not ready after $TimeoutSeconds seconds at $healthUri"
}

$resolvedLocustFile = (Resolve-Path -Path $LocustFile).Path
$resolvedOutputDir = (New-Item -ItemType Directory -Force -Path $OutputDir).FullName
$summaryPath = Join-Path $resolvedOutputDir "summary.md"
$integrityPath = Join-Path $resolvedOutputDir "integrity.md"
$apiProcess = $null
$runId = if ($StressRunId) { $StressRunId } else { (Get-Date -Format "yyyyMMddHHmmss") }

try {
    if (-not $AppendResults) {
        $patterns = @("*_stats.csv", "*_failures.csv", "*_history.csv", "*_exceptions.csv", "*.html", "summary.md", "integrity.md")
        foreach ($pattern in $patterns) {
            Get-ChildItem -Path $resolvedOutputDir -Filter $pattern -File -ErrorAction SilentlyContinue |
                Remove-Item -Force
        }
    }

    if ($StartLocalApi) {
        if ($ApiHost -ne "http://127.0.0.1:8000" -and $ApiHost -ne "http://localhost:8000") {
            throw "StartLocalApi supports only http://127.0.0.1:8000 or http://localhost:8000."
        }

        Write-Host "Starting local API server for stress tests..."
        $env:APP_DEBUG = "false"
        $env:RATE_LIMIT_REQUESTS_PER_MINUTE = "1000000"
        $env:RATE_LIMIT_RESERVATIONS_PER_MINUTE = "1000000"
        $venvPython = Join-Path (Join-Path (Get-Location).Path ".venv") "Scripts/python.exe"
        if (-not (Test-Path -Path $venvPython)) {
            throw "Python runtime not found at $venvPython. Run 'uv sync --group dev' first."
        }

        $apiProcess = Start-Process -FilePath $venvPython -ArgumentList @(
            "-m",
            "uvicorn",
            "reservas_api.main:app",
            "--app-dir",
            "src",
            "--host",
            "127.0.0.1",
            "--port",
            "8000"
        ) -WorkingDirectory (Get-Location).Path -PassThru
        Wait-ApiReady -HostBase $ApiHost -TimeoutSeconds $ApiStartupTimeoutSeconds
    }

    $env:STRESS_RUN_ID = $runId

    $scenarios = @(
        [PSCustomObject]@{ Name = "stress-ramp-500"; Users = 500; SpawnRate = 30; RunTime = "5m" },
        [PSCustomObject]@{ Name = "stress-spike-500"; Users = 500; SpawnRate = 500; RunTime = "2m" },
        [PSCustomObject]@{ Name = "stress-recovery-50"; Users = 50; SpawnRate = 50; RunTime = "2m" },
        [PSCustomObject]@{ Name = "stress-breakpoint-1000"; Users = 1000; SpawnRate = 80; RunTime = "2m" }
    )

    foreach ($scenario in $scenarios) {
        $prefix = Join-Path $resolvedOutputDir $scenario.Name
        Write-Host "Running scenario '$($scenario.Name)' (users=$($scenario.Users), run_time=$($scenario.RunTime), run_id=$runId)"

        & uv run locust `
            -f $resolvedLocustFile `
            --host $ApiHost `
            --headless `
            --users $scenario.Users `
            --spawn-rate $scenario.SpawnRate `
            --run-time $scenario.RunTime `
            --stop-timeout 45 `
            --exit-code-on-error 0 `
            --only-summary `
            --csv $prefix `
            --html "$prefix.html"

        if ($LASTEXITCODE -ne 0) {
            throw "Locust scenario '$($scenario.Name)' failed with exit code $LASTEXITCODE"
        }
    }

    $integrityArgs = @(
        "run",
        "python",
        "scripts/validate_stress_integrity.py",
        "--run-id",
        $runId,
        "--output",
        $integrityPath
    )
    & uv @integrityArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Integrity validation script failed."
    }

    $summaryArgs = @(
        "run",
        "python",
        "scripts/summarize_stress_results.py",
        "--input-dir",
        $resolvedOutputDir,
        "--output",
        $summaryPath,
        "--integrity-report",
        $integrityPath,
        "--p95-threshold-ms",
        "500"
    )
    if ($StrictSummary) {
        $summaryArgs += "--strict"
    }
    & uv @summaryArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to generate stress summary."
    }

    Write-Host "Stress run id: $runId"
    Write-Host "Stress reports generated:"
    Write-Host " - $summaryPath"
    Write-Host " - $integrityPath"
}
finally {
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Write-Host "Stopping local API server..."
        Stop-Process -Id $apiProcess.Id -Force
    }
}
