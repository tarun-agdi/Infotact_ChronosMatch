@echo off
cd /d "%~dp0"

echo Enter your commit message:
set /p message=

if "%message%"=="" set message=Project update

git add .
git commit -m "%message%"
git push

pause
