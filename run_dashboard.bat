@echo off
chcp 65001 >nul
cd /d C:\Users\talia\OneDrive\Desktop\sedori-search

echo [1/3] ツールを実行中...
call .venv\Scripts\python.exe app.py %*

echo.
echo [2/3] ダッシュボードサーバーを起動中...
start /b .venv\Scripts\python.exe -m http.server 8080

echo [3/3] ブラウザを開いています...
timeout /t 2 /nobreak >nul
start "" "http://localhost:8080/sedori_dashboard.html"

echo.
echo 完了！ブラウザでダッシュボードを確認してください。
echo サーバーを止めるには このウィンドウを閉じてください。
pause
