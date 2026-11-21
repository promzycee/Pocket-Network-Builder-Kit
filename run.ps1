$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
if (Test-Path .env) {
  Get-Content .env | ForEach-Object {
    $line = $_.Trim()
    if ($line -eq "" -or $line.StartsWith("#")) { return }
    $eq = $line.IndexOf("=")
    if ($eq -lt 1) { return }
    $name = $line.Substring(0, $eq).Trim()
    $value = $line.Substring($eq + 1).Trim()
    if (($value.StartsWith('"') -and $value.EndsWith('"')) -or ($value.StartsWith("'") -and $value.EndsWith("'"))) {
      $value = $value.Substring(1, $value.Length - 2)
    }
    Set-Item -Path "Env:$name" -Value $value
  }
}
$python = $null
foreach ($cmd in @("python", "python3")) {
  if (Get-Command $cmd -ErrorAction SilentlyContinue) {
    $python = $cmd
    break
  }
}
if (-not $python) {
  throw "Python 3.11 or newer is required."
}
& $python -u server.py
exit $LASTEXITCODE
