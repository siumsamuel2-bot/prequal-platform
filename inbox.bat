@echo off
setlocal

set API_KEY=%PAPERCLIP_API_KEY%
set API_URL=http://127.0.0.1:3100

curl.exe -s -H "Authorization: Bearer %API_KEY%" %API_URL%/api/agents/me/inbox-lite
