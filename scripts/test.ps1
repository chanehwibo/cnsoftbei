$ErrorActionPreference = "Stop"
$repo = Split-Path -Parent $PSScriptRoot
Set-Location $repo
$env:PYTHONPATH = "src"
$env:SAFEOPS_LLM_DISABLED = "1"
python -m coverage erase
python -W error::ResourceWarning -m coverage run -m unittest discover -s tests
python -m coverage report
python -m coverage xml
