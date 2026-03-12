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

$arguments = @("-m", "blueclaw_companion", "run", $Command) + $RemainingArgs
& python @arguments
exit $LASTEXITCODE
