param([string]$Mode)

if ($Mode -eq 'save') {
    $config = @{}
    $keys = @('DISCORD_WEBHOOK', 'DISCORD_USERNAME', 'DASHBOARD_PASSWORD', 'TELEGRAM_BOT_TOKEN', 'TELEGRAM_CHAT_ID', 'UPDATE_URL')
    foreach ($key in $keys) {
        $val = [System.Environment]::GetEnvironmentVariable($key)
        if ($null -eq $val) { $val = '' }
        $config[$key] = $val
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
