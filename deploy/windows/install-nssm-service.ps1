param(
    [string]$ServiceName = "OCRApi",
    [string]$ProjectRoot = "F:\pythonProject\tesrtOCR",
    [string]$NssmPath = "nssm.exe",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"

$StartScript = Join-Path $ProjectRoot "scripts\start-api.ps1"
if (-not (Test-Path $StartScript)) {
    throw "Start script not found: $StartScript"
}

$LogDir = Join-Path $ProjectRoot "logs"
New-Item -ItemType Directory -Force $LogDir | Out-Null

& $NssmPath install $ServiceName "powershell.exe" "-ExecutionPolicy Bypass -File `"$StartScript`" -Port $Port"
& $NssmPath set $ServiceName AppDirectory $ProjectRoot
& $NssmPath set $ServiceName AppStdout (Join-Path $LogDir "ocr-api.out.log")
& $NssmPath set $ServiceName AppStderr (Join-Path $LogDir "ocr-api.err.log")
& $NssmPath set $ServiceName Start SERVICE_AUTO_START

Write-Host "Installed service $ServiceName. Start it with: nssm start $ServiceName"
