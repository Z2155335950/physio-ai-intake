$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath ".env")) {
    Copy-Item -LiteralPath ".env.example" -Destination ".env"
}

python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload

