$ErrorActionPreference = "Stop"

$RootDir = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$HelperDir = Join-Path $RootDir "runtime\service-helper"
$CommandsDir = Join-Path $HelperDir "commands"
$ResponsesDir = Join-Path $HelperDir "responses"
$LogsDir = Join-Path $HelperDir "logs"
$ServicesDir = Join-Path $HelperDir "services"
$WorkDir = Join-Path $HelperDir "work"
$PidFile = Join-Path $HelperDir "helper.pid"

New-Item -ItemType Directory -Force -Path $CommandsDir, $ResponsesDir, $LogsDir, $ServicesDir, $WorkDir | Out-Null

if (Test-Path $PidFile) {
  $existingPid = Get-Content $PidFile -ErrorAction SilentlyContinue | Select-Object -First 1
  if ($existingPid) {
    $existingProcess = Get-Process -Id $existingPid -ErrorAction SilentlyContinue
    if ($existingProcess) {
      exit 0
    }
  }
}

Set-Content -Path $PidFile -Value $PID

function Get-RepoDir([string]$serviceKey) {
  switch ($serviceKey) {
    "weather" { return (Join-Path $RootDir "OpenAgri-WeatherService") }
    "irrigation" { return (Join-Path $RootDir "OpenAgri-IrrigationManagement") }
    "pdm" { return (Join-Path $RootDir "OpenAgri-PestAndDiseaseManagement") }
    default { throw "Unknown service key: $serviceKey" }
  }
}

function Get-ComposeFile([string]$serviceKey, [string]$repoDir) {
  $candidates = @()
  switch ($serviceKey) {
    "weather" { $candidates = @("docker-compose-x86_64.yml", "docker-compose-arm64.yml", "docker-compose.yml", "docker-compose.yaml") }
    default { $candidates = @("compose.yaml", "compose.yml", "docker-compose.yml", "docker-compose.yaml") }
  }
  foreach ($candidate in $candidates) {
    $path = Join-Path $repoDir $candidate
    if (Test-Path $path) {
      return $path
    }
  }
  throw "No compose file found for $serviceKey in $repoDir"
}

function Write-ServiceState([string]$serviceKey) {
  $repoDir = Get-RepoDir $serviceKey
  $stateFile = Join-Path $ServicesDir "$serviceKey.env"
  $installed = "0"
  $composeFile = ""
  if (Test-Path $repoDir) {
    $installed = "1"
    try {
      $composeFile = Get-ComposeFile $serviceKey $repoDir
    } catch {
      $composeFile = ""
    }
  }
  @(
    "INSTALLED=$installed"
    "REPO_DIR=$repoDir"
    "COMPOSE_FILE=$composeFile"
  ) | Set-Content -Path $stateFile
}

function Write-HelperStatus() {
  @(
    "TIMESTAMP_EPOCH=$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
    "MODE=host-launcher"
  ) | Set-Content -Path (Join-Path $HelperDir "helper.env")
}

function Invoke-Prepare([string]$serviceKey) {
  docker run --rm `
    -v "${RootDir}:/workspace" `
    -w /workspace `
    -e AGRIVISION_PROJECT_ROOT=/workspace `
    -e AGRIVISION_CONFIG_PATH=/workspace/config.yaml `
    -e AGRIVISION_RUNTIME_SETTINGS_PATH=/workspace/runtime/settings.json `
    agrivision-pipeline:phase5 `
    python run.py --service-control --service-key $serviceKey --service-action prepare
}

function Invoke-ComposeUp([string]$serviceKey, [switch]$Restart) {
  Invoke-Prepare $serviceKey
  $repoDir = Get-RepoDir $serviceKey
  $composeFile = Get-ComposeFile $serviceKey $repoDir
  $args = @("compose", "-f", $composeFile, "up", "-d")
  if ($serviceKey -eq "irrigation") {
    $args += "--build"
  }
  if ($Restart) {
    $args += "--force-recreate"
  }
  Push-Location $repoDir
  try {
    & docker @args
    if ($LASTEXITCODE -ne 0) {
      throw "docker compose up failed for $serviceKey"
    }
  } finally {
    Pop-Location
  }
}

function Invoke-ComposeStop([string]$serviceKey) {
  $repoDir = Get-RepoDir $serviceKey
  $composeFile = Get-ComposeFile $serviceKey $repoDir
  Push-Location $repoDir
  try {
    & docker compose -f $composeFile stop
    if ($LASTEXITCODE -ne 0) {
      throw "docker compose stop failed for $serviceKey"
    }
  } finally {
    Pop-Location
  }
}

function Invoke-InstallMissing() {
  foreach ($serviceKey in @("weather", "irrigation", "pdm")) {
    Write-ServiceState $serviceKey
    $stateFile = Join-Path $ServicesDir "$serviceKey.env"
    $installed = (Get-Content $stateFile | Where-Object { $_ -like "INSTALLED=*" }) -replace "^INSTALLED=", ""
    if ($installed -ne "1") {
      Invoke-ComposeUp $serviceKey
    }
  }
}

function Process-Command([string]$commandPath) {
  $values = @{}
  foreach ($line in Get-Content $commandPath) {
    if ($line -notmatch "=") { continue }
    $parts = $line.Split("=", 2)
    $values[$parts[0]] = $parts[1]
  }

  $requestId = $values["REQUEST_ID"]
  $action = $values["ACTION"]
  $serviceKey = $values["SERVICE_KEY"]
  $logPath = Join-Path $LogsDir "$requestId.log"
  $responsePath = Join-Path $ResponsesDir "$requestId.env"
  $ok = "1"
  $message = "Completed."

  try {
    switch ($action) {
      "install_missing" { Invoke-InstallMissing *>&1 | Tee-Object -FilePath $logPath }
      "ensure" { Invoke-ComposeUp $serviceKey *>&1 | Tee-Object -FilePath $logPath }
      "restart" { Invoke-ComposeUp $serviceKey -Restart *>&1 | Tee-Object -FilePath $logPath }
      "stop" { Invoke-ComposeStop $serviceKey *>&1 | Tee-Object -FilePath $logPath }
      default { throw "Unknown action: $action" }
    }
  } catch {
    $ok = "0"
    $message = "Host helper failed while running $action $serviceKey."
    $_ | Out-String | Set-Content -Path $logPath
  }

  foreach ($name in @("weather", "irrigation", "pdm")) {
    Write-ServiceState $name
  }

  @(
    "REQUEST_ID=$requestId"
    "OK=$ok"
    "MESSAGE=$message"
    "LOG_PATH=$logPath"
  ) | Set-Content -Path $responsePath
}

foreach ($serviceKey in @("weather", "irrigation", "pdm")) {
  Write-ServiceState $serviceKey
}

while ($true) {
  Write-HelperStatus
  foreach ($serviceKey in @("weather", "irrigation", "pdm")) {
    Write-ServiceState $serviceKey
  }

  Get-ChildItem -Path $CommandsDir -Filter *.env -ErrorAction SilentlyContinue | Sort-Object Name | ForEach-Object {
    $workingPath = Join-Path $WorkDir $_.Name
    Move-Item -Force $_.FullName $workingPath
    Process-Command $workingPath
    Remove-Item -Force $workingPath
  }

  Start-Sleep -Seconds 2
}
