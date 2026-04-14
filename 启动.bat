@chcp 65001 > nul
@echo off

:: ── 项目根目录（硬编码，与 bat 放在哪里无关）────────────────
set PROJECT=C:\git\SRTGPT

:: ── 激活 venv ────────────────────────────────────────────────
call "%PROJECT%\SRTGPT\Scripts\activate.bat"
if errorlevel 1 (
    echo [错误] 找不到 venv：%PROJECT%\SRTGPT
    pause
    exit /b 1
)

echo 启动 SRTGPT...
echo 浏览器访问: http://localhost:8502
echo.
streamlit run "%PROJECT%\src\app.py" --server.port 8502 --server.address 0.0.0.0
pause