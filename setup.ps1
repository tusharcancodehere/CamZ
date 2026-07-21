# Legacy setup script delegating to the unified CLI wrapper

$BaseDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $BaseDir

& .\camz.ps1 setup
