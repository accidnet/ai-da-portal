$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$python = Join-Path $root ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    throw "Virtual environment not found at $python. Run 'uv sync' first."
}

Push-Location $root
try {
    & $python -m pytest @Args
}
finally {
    Pop-Location
}
