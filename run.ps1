[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [string]$Command = "inspect",

    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$RemainingArgs
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:PYTHONPATH = Join-Path $repoRoot "python"

$runCommand = $Command
$runArgs = @($RemainingArgs)
if ($Command -eq "health") {
    $runCommand = "inspect"
    if (-not ($runArgs -contains "--mode")) { $runArgs += @("--mode", "hybrid") }
    if (-not ($runArgs -contains "--connect-adb")) { $runArgs += "--connect-adb" }
    if (-not ($runArgs -contains "--json")) { $runArgs += "--json" }
}

$arguments = @("-m", "blueclaw_companion", "run", $runCommand) + $runArgs
& python @arguments
exit $LASTEXITCODE
