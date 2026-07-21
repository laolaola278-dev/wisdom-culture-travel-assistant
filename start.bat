@echo off
chcp 65001 >nul
echo ============================================
echo   白云文化智能问答助手 - 启动脚本
echo   基于知识图谱的智慧文旅平台 (Production v2.0)
echo ============================================
echo.

cd /d "%~dp0backend"

echo [1/4] 检查依赖...
pip install -r requirements.txt -q

echo [2/4] 初始化数据库...
python init_db.py

echo [3/4] 构建前端...
cd /d "%~dp0frontend"
if not exist "dist" (
    echo   首次构建前端...
    call npm install --silent 2>nul
    call npx vite build --silent
)
cd /d "%~dp0backend"

echo [4/4] 启动服务...
echo   访问地址: http://localhost:5000
echo   API文档:  http://localhost:5000/api/docs/
echo   健康检查: http://localhost:5000/api/health
echo   按 Ctrl+C 停止
echo.
python app.py

pause
