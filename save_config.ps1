param([string]$Mode)

if ($Mode -eq 'save') {
    if (Test-Path '_save_args.txt') {
        $config = @{}
        Get-Content '_save_args.txt' | ForEach-Object {
            $parts = $_ -split '=', 2
            if ($parts.Length -eq 2) {
                $config[$parts[0]] = $parts[1]
            }
        }
        Remove-Item '_save_args.txt' -Force
    } else {
        $config = @{}
        foreach ($arg in $args) {
            if ($arg -match '^([^=]+)=(.*)$') {
                $config[$Matches[1]] = $Matches[2]
            } elseif ($arg -match '^([^=]+)=$') {
                $config[$Matches[1]] = ''
            } elseif ($arg -match '^([^=]+)!$') {
                $config[$Matches[1]] = ''
            }
        }
    }
    $config.GetEnumerator() | ForEach-Object { $_.Key + '=' + $_.Value } | Set-Content -Path config.txt -Encoding UTF8
}
elseif ($Mode -eq 'load') {
    if (Test-Path config.txt) {
        $lines = @()
        Get-Content config.txt | ForEach-Object {
            $parts = $_ -split '=', 2
            if ($parts.Length -eq 2) {
                $lines += ('set "' + $parts[0] + '=' + $parts[1] + '"')
            }
        }
        $lines | Set-Content -Path _load_config.bat -Encoding ASCII
    }
}
elseif ($Mode -eq 'show') {
    if (Test-Path config.txt) {
        Get-Content config.txt | ForEach-Object {
            $parts = $_ -split '=', 2
            if ($parts.Length -eq 2) {
                Write-Host "     $($parts[0]): $($parts[1])"
            }
        }
    }
}
