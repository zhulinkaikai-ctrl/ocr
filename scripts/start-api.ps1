param(
    [string]$BindHost = "0.0.0.0",
    [int]$Port = 8000,
    [string]$EnvFile = ".env"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (Test-Path $EnvFile) {
    Get-Content $EnvFile | ForEach-Object {
        $Line = $_.Trim()
        if ($Line -eq "" -or $Line.StartsWith("#") -or $Line -notmatch "=") {
            return
        }

        $Name, $Value = $Line.Split("=", 2)
        [Environment]::SetEnvironmentVariable($Name.Trim(), $Value.Trim(), "Process")
    }
}

$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Python)) {
    throw "未找到 Python 虚拟环境：$Python"
}

& $Python -m uvicorn api_app:app --host $BindHost --port $Port
