$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

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
    "weather" {
      if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") {
        $candidates = @("docker-compose-arm64.yml", "docker-compose-x86_64.yml", "docker-compose.yml", "docker-compose.yaml")
      } else {
        $candidates = @("docker-compose-x86_64.yml", "docker-compose-arm64.yml", "docker-compose.yml", "docker-compose.yaml")
      }
    }
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

function Invoke-Docker([string[]]$ArgumentList, [string]$LogPath) {
  $quotedArgs = $ArgumentList | ForEach-Object {
    if ($_ -eq "") {
      '""'
    } elseif ($_ -notmatch '[\s"]') {
      $_
    } else {
      '"' + (($_ -replace '(\\*)"', '$1$1\"') -replace '(\\+)$', '$1$1') + '"'
    }
  }

  $psi = New-Object System.Diagnostics.ProcessStartInfo
  $psi.FileName = "docker"
  $psi.Arguments = ($quotedArgs -join " ")
  $psi.UseShellExecute = $false
  $psi.RedirectStandardOutput = $true
  $psi.RedirectStandardError = $true
  $psi.CreateNoWindow = $true

  $process = New-Object System.Diagnostics.Process
  $process.StartInfo = $psi
  $null = $process.Start()
  $stdout = $process.StandardOutput.ReadToEnd()
  $stderr = $process.StandardError.ReadToEnd()
  $process.WaitForExit()

  if ($stdout) {
    $stdout | Out-File -FilePath $LogPath -Append -Encoding utf8
  }
  if ($stderr) {
    $stderr | Out-File -FilePath $LogPath -Append -Encoding utf8
  }
  return $process.ExitCode
}

function Get-DashboardImage() {
  # Reuse whatever image docker compose started, so the tag lives only in
  # docker-compose.yml.
  try {
    $image = (& docker inspect --format "{{.Config.Image}}" agrivision-pipeline 2>$null | Out-String).Trim()
  } catch {
    $image = ""
  }
  if ($LASTEXITCODE -ne 0 -or -not $image) {
    throw "The agrivision-pipeline container is not available; start AgriVision with the launcher first."
  }
  return $image
}

function Invoke-Prepare([string]$serviceKey, [string]$LogPath) {
  $image = Get-DashboardImage
  $dockerArgs = @(
    "run", "--rm",
    "-v", "${RootDir}:/workspace",
    "-w", "/workspace",
    "-e", "AGRIVISION_PROJECT_ROOT=/workspace",
    "-e", "AGRIVISION_CONFIG_PATH=/workspace/config.yaml",
    "-e", "AGRIVISION_RUNTIME_SETTINGS_PATH=/workspace/runtime/settings.json",
    $image,
    "python", "run.py", "--service-control", "--service-key", $serviceKey, "--service-action", "prepare"
  )
  $exitCode = Invoke-Docker -ArgumentList $dockerArgs -LogPath $LogPath
  if ($exitCode -ne 0) {
    throw "docker run prepare failed for $serviceKey"
  }
}

function Invoke-ComposeUp([string]$serviceKey, [string]$LogPath, [switch]$Restart) {
  Invoke-Prepare $serviceKey $LogPath
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
    $exitCode = Invoke-Docker -ArgumentList $args -LogPath $LogPath
    if ($exitCode -ne 0) {
      throw "docker compose up failed for $serviceKey"
    }
  } finally {
    Pop-Location
  }
}

function Invoke-ComposeStop([string]$serviceKey, [string]$LogPath) {
  $repoDir = Get-RepoDir $serviceKey
  $composeFile = Get-ComposeFile $serviceKey $repoDir
  Push-Location $repoDir
  try {
    $exitCode = Invoke-Docker -ArgumentList @("compose", "-f", $composeFile, "stop") -LogPath $LogPath
    if ($exitCode -ne 0) {
      throw "docker compose stop failed for $serviceKey"
    }
  } finally {
    Pop-Location
  }
}

function Invoke-InstallMissing() {
  $bootstrapLog = Join-Path $LogsDir "install-missing.log"
  foreach ($serviceKey in @("weather", "irrigation", "pdm")) {
    Write-ServiceState $serviceKey
    $stateFile = Join-Path $ServicesDir "$serviceKey.env"
    $installed = (Get-Content $stateFile | Where-Object { $_ -like "INSTALLED=*" }) -replace "^INSTALLED=", ""
    if ($installed -ne "1") {
      Invoke-ComposeUp $serviceKey $bootstrapLog
    }
  }
}

function Prepare-AllServices() {
  $bootstrapLog = Join-Path $LogsDir "startup-prepare.log"
  foreach ($serviceKey in @("weather", "irrigation", "pdm")) {
    try {
      "Preparing $serviceKey" | Out-File -FilePath $bootstrapLog -Append -Encoding utf8
      Invoke-Prepare $serviceKey $bootstrapLog
    } catch {
      "Prepare failed for $serviceKey`n$_" | Out-File -FilePath $bootstrapLog -Append -Encoding utf8
    } finally {
      Write-ServiceState $serviceKey
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
      "install_missing" { Invoke-InstallMissing }
      "ensure" { Invoke-ComposeUp $serviceKey $logPath }
      "restart" { Invoke-ComposeUp $serviceKey $logPath -Restart }
      "stop" { Invoke-ComposeStop $serviceKey $logPath }
      default { throw "Unknown action: $action" }
    }
  } catch {
    $ok = "0"
    $message = "Host helper failed while running $action $serviceKey."
    $_ | Out-String | Out-File -FilePath $logPath -Append -Encoding utf8
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

# Keep the heartbeat fresh while long first-time clones and image builds run;
# the dashboard treats a heartbeat older than 15 seconds as a missing helper.
Write-HelperStatus
$null = Start-Job -ArgumentList (Join-Path $HelperDir "helper.env"), $PID -ScriptBlock {
  param([string]$StatusPath, [int]$ParentPid)
  while (Get-Process -Id $ParentPid -ErrorAction SilentlyContinue) {
    try {
      @(
        "TIMESTAMP_EPOCH=$([DateTimeOffset]::UtcNow.ToUnixTimeSeconds())"
        "MODE=host-launcher"
      ) | Set-Content -Path $StatusPath
    } catch {
    }
    Start-Sleep -Seconds 2
  }
}

Prepare-AllServices

while ($true) {
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
