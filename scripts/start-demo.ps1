param(
    [string]$EnvFile = ".env.local"
)

$ErrorActionPreference = "Stop"

$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
Set-Location $ProjectRoot

if (Test-Path $EnvFile) {
    [Environment]::SetEnvironmentVariable("ENV_FILE", $EnvFile, "Process")
}

$Streamlit = Join-Path $ProjectRoot ".venv\Scripts\streamlit.exe"
if (-not (Test-Path $Streamlit)) {
    throw "Streamlit executable not found: $Streamlit"
}

& $Streamlit run app.py
