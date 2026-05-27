param(
    [Parameter(Mandatory = $true)]
    [string]$Path
)

# Load .env key-value pairs into this PowerShell process for child processes.
function Import-DotEnvFile {
    param(
        [Parameter(Mandatory = $true)]
        [string]$DotEnvPath
    )

    if (-not (Test-Path -LiteralPath $DotEnvPath)) {
        return
    }

    foreach ($line in [System.IO.File]::ReadAllLines($DotEnvPath)) {
        $trimmed = $line.Trim()
        if (-not $trimmed -or $trimmed.StartsWith("#")) {
            continue
        }

        $separatorIndex = $trimmed.IndexOf("=")
        if ($separatorIndex -le 0) {
            continue
        }

        $name = $trimmed.Substring(0, $separatorIndex).Trim()
        $value = $trimmed.Substring($separatorIndex + 1).Trim()
        if ($value.Length -ge 2) {
            $lastIndex = $value.Length - 1
            $isDoubleQuoted = $value[0] -eq [char]34 -and $value[$lastIndex] -eq [char]34
            $isSingleQuoted = $value[0] -eq [char]39 -and $value[$lastIndex] -eq [char]39
            if ($isDoubleQuoted -or $isSingleQuoted) {
                $value = $value.Substring(1, $value.Length - 2)
            }
        }

        [System.Environment]::SetEnvironmentVariable($name, $value, "Process")
    }
}

Import-DotEnvFile -DotEnvPath $Path
