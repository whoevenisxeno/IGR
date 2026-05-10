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
elseif ($Mode -eq 'inject') {
    $replacements = @{
        'BUILD_DISCORD_WEBHOOK' = 'DISCORD_WEBHOOK'
        'BUILD_DISCORD_USERNAME' = 'DISCORD_USERNAME'
        'BUILD_DASHBOARD_PASSWORD' = 'DASHBOARD_PASSWORD'
        'BUILD_TELEGRAM_BOT_TOKEN' = 'TELEGRAM_BOT_TOKEN'
        'BUILD_TELEGRAM_CHAT_ID' = 'TELEGRAM_CHAT_ID'
        'BUILD_UPDATE_URL' = 'UPDATE_URL'
        'BUILD_ENCRYPTION_KEY' = '_IGR_ENC_KEY'
    }
    $content = Get-Content 'main_build.py' -Raw
    foreach ($kv in $replacements.GetEnumerator()) {
        if ($kv.Value -eq '_IGR_ENC_KEY') {
            $rawVal = 'igr_enc_key_2024'
        } else {
            $rawVal = [System.Environment]::GetEnvironmentVariable($kv.Value)
            if ($null -eq $rawVal) { $rawVal = '' }
        }
        $encVal = 'ENC:' + [Convert]::ToBase64String([System.Text.Encoding]::UTF8.GetBytes($rawVal))
        $content = $content -replace [regex]::Escape($kv.Key), $encVal
    }
    $content | Set-Content 'main_build.py' -NoNewline
}
