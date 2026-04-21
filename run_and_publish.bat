@echo off
setlocal

if not exist "run_dashboard.bat" (
  echo [ERROR] run_dashboard.bat が見つかりません。
  exit /b 1
)

if not exist ".git" (
  echo [ERROR] .git フォルダが見つかりません。
  exit /b 1
)

echo [1/3] run_dashboard.bat を実行します...
call run_dashboard.bat %*
if errorlevel 1 (
  echo [ERROR] run_dashboard.bat が失敗しました。
  exit /b 1
)

echo [2/3] docs/ の差分を確認します...
git add docs/

git diff --cached --quiet
if %errorlevel%==0 (
  echo [OK] docs/ に変更がないため、commit/push はスキップします。
  exit /b 0
)

for /f "tokens=1-4 delims=/ " %%a in ("%date%") do set d=%%a%%b%%c%%d
for /f "tokens=1-3 delims=:." %%a in ("%time%") do set t=%%a%%b%%c

set msg=update: %date% %time%

echo [3/3] GitHub へ push します...
git commit -m "%msg%"
if errorlevel 1 (
  echo [ERROR] git commit に失敗しました。
  exit /b 1
)

git push
if errorlevel 1 (
  echo [ERROR] git push に失敗しました。
  exit /b 1
)

echo [OK] 完了しました。
exit /b 0