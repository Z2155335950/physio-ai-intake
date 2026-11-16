$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath ".env")) {
    throw "缺少 .env。请先复制 .env.example 并设置强员工密码。"
}

$envText = Get-Content -LiteralPath ".env" -Raw -Encoding utf8
if ($envText -match "(?m)^STAFF_ACCESS_PASSWORD=\s*$") {
    throw "STAFF_ACCESS_PASSWORD 不能为空。"
}
if ($envText -match "(?m)^STAFF_ACCESS_PASSWORD=.{0,11}$") {
    throw "STAFF_ACCESS_PASSWORD 太短，试点前请改为至少 12 位的随机密码。"
}

$env:PORTAL_COOKIE_SECURE = "true"

Write-Host "正在启动公网试点模式..." -ForegroundColor Cyan
Write-Host "网站只在 127.0.0.1:8000 监听，必须通过 HTTPS 隧道访问。" -ForegroundColor Yellow
Write-Host "浏览器中的登录 Cookie 已启用 Secure，不能再用本机 HTTP 登录。" -ForegroundColor Yellow
Write-Host "按 Ctrl+C 可停止网站。" -ForegroundColor DarkGray

python -m uvicorn app.main:app `
    --host 127.0.0.1 `
    --port 8000 `
    --proxy-headers `
    --forwarded-allow-ips "127.0.0.1"
