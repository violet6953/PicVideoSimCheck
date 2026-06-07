@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo ========================================
echo   PicSimProcess 一键打包脚本
echo ========================================
echo.
echo 请选择要构建的版本：
echo   1. CPU 版（体积小，无需 NVIDIA 显卡）
echo   2. GPU 版（包含 PyTorch + CUDA，体积大）
echo   3. 同时构建 CPU + GPU 两个版本
echo.
set /p choice="请输入选项 (1/2/3): "

if "%choice%"=="1" goto cpu
if "%choice%"=="2" goto gpu
if "%choice%"=="3" goto both
goto end

:cpu
call "..\venv\Scripts\activate.bat"
python "%~dp0build-cpu.py"
echo.
echo 构建完成。生成安装包请运行：
echo   "C:\Program Files\Inno Setup 7\ISCC.exe" "%~dp0installer-cpu.iss"
goto end

:gpu
call "..\venv\Scripts\activate.bat"
python "%~dp0build-gpu.py"
echo.
echo 构建完成。生成安装包请运行：
echo   "C:\Program Files\Inno Setup 7\ISCC.exe" "%~dp0installer-gpu.iss"
goto end

:both
call "..\venv\Scripts\activate.bat"
python "%~dp0build-cpu.py"
if errorlevel 1 goto error
python "%~dp0build-gpu.py"
if errorlevel 1 goto error
echo.
echo 构建完成。生成安装包请运行：
echo   "C:\Program Files\Inno Setup 7\ISCC.exe" "%~dp0installer-cpu.iss"
echo   "C:\Program Files\Inno Setup 7\ISCC.exe" "%~dp0installer-gpu.iss"
goto end

:error
echo.
echo [错误] 构建过程中出现错误，请查看上方日志。
pause
goto end

:end
echo.
pause
endlocal
