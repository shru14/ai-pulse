# Serves the local AI Pulse app (port 8080) at a public https://*.trycloudflare.com link.
# Run by the "AI Pulse tunnel" scheduled task at logon. A quick tunnel gets a new random link each
# time it starts; the current link is written to tunnel-url.txt.
$dir = Split-Path -Parent $MyInvocation.MyCommand.Path
$log = Join-Path $dir "tunnel.log"
$urlFile = Join-Path $dir "tunnel-url.txt"
Remove-Item $log, $urlFile -ErrorAction SilentlyContinue

$exe = "${env:ProgramFiles(x86)}\cloudflared\cloudflared.exe"
if (-not (Test-Path $exe)) { $exe = "$env:ProgramFiles\cloudflared\cloudflared.exe" }
$proc = Start-Process $exe -ArgumentList "tunnel", "--no-autoupdate", "--url", "http://localhost:8080", "--logfile", "`"$log`"" `
    -WindowStyle Hidden -PassThru

for ($i = 0; $i -lt 60 -and -not (Test-Path $urlFile); $i++) {
    Start-Sleep 2
    if (Test-Path $log) {
        $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" | Select-Object -Last 1
        if ($m) { $m.Matches[0].Value | Set-Content $urlFile -Encoding utf8 }
    }
}
$proc.WaitForExit()
