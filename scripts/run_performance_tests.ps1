param(
    [string]$ApiHost = "http://127.0.0.1:8000",
    [string]$LocustFile = "tests/performance/locustfile.py",
    [string]$OutputDir = "artifacts/performance",
    [switch]$StartLocalApi,
    [ValidateSet("standard", "smoke")][string]$ScenarioProfile = "standard",
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
$apiProcess = $null

try {
    if (-not $AppendResults) {
        $patterns = @("*_stats.csv", "*_failures.csv", "*_history.csv", "*.html", "summary.md")
        foreach ($pattern in $patterns) {
            Get-ChildItem -Path $resolvedOutputDir -Filter $pattern -File -ErrorAction SilentlyContinue |
                Remove-Item -Force
        }
    }

    if ($StartLocalApi) {
        if ($ApiHost -ne "http://127.0.0.1:8000" -and $ApiHost -ne "http://localhost:8000") {
            throw "StartLocalApi supports only http://127.0.0.1:8000 or http://localhost:8000."
        }

        Write-Host "Starting local API server for performance tests..."
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

    $scenarios = if ($ScenarioProfile -eq "smoke") {
        @(
            [PSCustomObject]@{ Name = "smoke-5-users"; Users = 5; SpawnRate = 5; RunTime = "30s" }
        )
    }
    else {
        @(
            [PSCustomObject]@{ Name = "load-50-users"; Users = 50; SpawnRate = 10; RunTime = "3m" },
            [PSCustomObject]@{ Name = "load-100-users"; Users = 100; SpawnRate = 20; RunTime = "3m" },
            [PSCustomObject]@{ Name = "sustained-10m"; Users = 100; SpawnRate = 20; RunTime = "10m" }
        )
    }

    foreach ($scenario in $scenarios) {
        $prefix = Join-Path $resolvedOutputDir $scenario.Name
        Write-Host "Running scenario '$($scenario.Name)' (users=$($scenario.Users), run_time=$($scenario.RunTime))"

        & uv run locust `
            -f $resolvedLocustFile `
            --host $ApiHost `
            --headless `
            --users $scenario.Users `
            --spawn-rate $scenario.SpawnRate `
            --run-time $scenario.RunTime `
            --stop-timeout 30 `
            --exit-code-on-error 0 `
            --only-summary `
            --csv $prefix `
            --html "$prefix.html"

        if ($LASTEXITCODE -ne 0) {
            throw "Locust scenario '$($scenario.Name)' failed with exit code $LASTEXITCODE"
        }
    }

    $summaryArgs = @(
        "run",
        "python",
        "scripts/summarize_performance_results.py",
        "--input-dir",
        $resolvedOutputDir,
        "--output",
        $summaryPath,
        "--p95-threshold-ms",
        "500"
    )
    if ($StrictSummary) {
        $summaryArgs += "--strict"
    }
    & uv @summaryArgs

    if ($LASTEXITCODE -ne 0) {
        throw "Failed to generate performance summary."
    }

    Write-Host "Performance report generated: $summaryPath"
}
finally {
    if ($null -ne $apiProcess -and -not $apiProcess.HasExited) {
        Write-Host "Stopping local API server..."
        Stop-Process -Id $apiProcess.Id -Force
    }
}
