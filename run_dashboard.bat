@echo off
chcp 65001 >nul
cd /d C:\Users\talia\OneDrive\Desktop\sedori-search

echo [1/4] ツール実行中...
call .venv\Scripts\python.exe app.py %*
if errorlevel 1 (
    echo ツール実行でエラーが発生しました
    pause
    exit /b 1
)

echo.
echo [2/4] JSON出力中...
call .venv\Scripts\python.exe export_json.py

echo.
echo [3/4] GitHub Pages に push 中...
git add docs/
git commit -m "update: %date% %time%"
git push

echo.
echo [4/4] ブラウザを開いています...
start "" "https://arisbluenight-ui.github.io/sedori-search/"

echo.
echo 完了！夫さんにこのURLを送ってください：
echo https://arisbluenight-ui.github.io/sedori-search/
