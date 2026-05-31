@echo off
setlocal

:: Use the exact token from environment variable
set "API_KEY=%PAPERCLIP_API_KEY%"
set "API_URL=%PAPERCLIP_API_URL%"

curl.exe -s -H "Authorization: Bearer %API_KEY%" %API_URL%/api/agents/me
