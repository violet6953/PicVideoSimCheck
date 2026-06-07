# Inno Setup 7 打包指南

本文档说明如何使用 Inno Setup 7.x 将 PyInstaller 构建的目录打包成 Windows 安装程序（.exe）。

---

## 第一步：安装 Inno Setup 7

### 下载

官方下载地址：https://jrsoftware.org/isdl.php

或搜索："Inno Setup 7.0.1 beta x64"

### 安装步骤

1. 下载 `innosetup-7.0.1-beta-x64.exe`
2. 双击运行安装程序
3. 选择安装语言（建议选 English，安装后支持多语言）
4. 接受许可协议
5. 选择安装路径（默认 `C:\Program Files\Inno Setup 7`）
6. 勾选「Create Start Menu shortcuts」和「Add to PATH」（可选但推荐）
7. 点击 Install 完成安装

---

## 第二步：确认 PyInstaller 构建已完成

确保以下目录存在且完整：

```
F:\PyCharm Project\PicSimProcess\dist-gpu\PicSimProcess\
├── PicSimProcess.exe          ← 主程序（约 40MB）
└── _internal\                  ← 依赖目录（约 4.5GB）
    ├── static\                 ← 前端资源
    ├── templates\              ← HTML 模板
    ├── torch\                  ← PyTorch
    ├── ...                     ← 其他依赖
```

如果目录不存在或不完整，先运行：
```powershell
cd "F:\PyCharm Project\PicSimProcess"
python build\build-gpu.py
```

---

## 第三步：编译安装程序

### 方法一：使用 Inno Setup GUI（推荐新手）

1. 打开 Inno Setup Compiler（开始菜单 → Inno Setup 7 → Inno Setup Compiler）
2. 点击菜单 **File → Open**
3. 选择文件：`F:\PyCharm Project\PicSimProcess\build\installer-gpu.iss`
4. 点击工具栏上的 **Build → Compile**（或按 F9）
5. 等待编译完成（约 5-10 分钟，取决于磁盘速度）
6. 生成的安装程序在：`F:\PyCharm Project\PicSimProcess\Output\PicSimProcess_GPU_Setup_v1.0.0.exe`

### 方法二：使用命令行（高级用户）

打开 PowerShell 或 CMD，运行：

```powershell
# 如果 Inno Setup 在默认路径
& "C:\Program Files\Inno Setup 7\ISCC.exe" "F:\PyCharm Project\PicSimProcess\build\installer-gpu.iss"

# 如果 Inno Setup 在其他路径，请替换为实际路径
```

### 方法三：创建一键打包脚本

创建 `build_installer.bat`：

```batch
@echo off
echo ========================================
echo  PicSimProcess Installer Build
echo ========================================
echo.

set ISCC="C:\Program Files\Inno Setup 7\ISCC.exe"
set ISS="F:\PyCharm Project\PicSimProcess\build\installer-gpu.iss"

if not exist %ISCC% (
    echo [ERROR] Inno Setup not found at %ISCC%
    echo Please install Inno Setup 7 first.
    pause
    exit /b 1
)

if not exist %ISS% (
    echo [ERROR] ISS file not found: %ISS%
    pause
    exit /b 1
)

echo Building installer...
%ISCC% %ISS%

if %ERRORLEVEL% neq 0 (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [OK] Build successful!
echo Output: F:\PyCharm Project\PicSimProcess\Output\
pause
```

---

## 第四步：验证安装程序

1. 打开 `Output` 目录
2. 双击 `PicSimProcess_GPU_Setup_v1.0.0.exe`
3. 按向导完成安装
4. 安装完成后，从开始菜单或桌面快捷方式启动
5. 确认应用正常运行

---

## 常见问题

### Q: 编译时报错 "Source file does not exist"

**原因**：PyInstaller 构建不完整或路径错误。

**解决**：
```powershell
# 检查文件是否存在
ls "F:\PyCharm Project\PicSimProcess\dist-gpu\PicSimProcess\PicSimProcess.exe"

# 如果不存在，重新构建
python build\build-gpu.py
```

### Q: 编译时报错 "No files found matching ..."

**原因**：`_internal` 目录为空或路径错误。

**解决**：
```powershell
# 检查 _internal 目录
ls "F:\PyCharm Project\PicSimProcess\dist-gpu\PicSimProcess\_internal\" | measure

# 如果文件数为 0，重新构建
```

### Q: 安装程序太大（>4GB）

**原因**：PyTorch + CUDA 本身就很大。

**解决**：
- 这是正常的，GPU 版包含 CUDA 运行时库
- LZMA2 压缩率已经很高了
- 如果需要更小的安装包，考虑制作「轻量版」（不含 PyTorch）

### Q: 安装后启动报错 "找不到 python311.dll"

**原因**：安装不完整或 VC++ 运行时缺失。

**解决**：
- 确保安装时勾选了所有组件
- 安装 [Visual C++ Redistributable](https://aka.ms/vs/17/release/vc_redist.x64.exe)

### Q: 安装后前端样式消失

**原因**：`_internal` 目录没有正确安装。

**解决**：
- 这是已修复的问题，确保使用的是最新构建
- 检查安装目录下是否有 `_internal/static/css/style.css`

---

## 文件清单

| 文件 | 说明 |
|------|------|
| `build\installer-gpu.iss` | Inno Setup 脚本 |
| `build\INNO_SETUP_GUIDE.md` | 本指南 |
| `dist-gpu\PicSimProcess\` | PyInstaller 构建输出 |
| `Output\PicSimProcess_GPU_Setup_v1.0.0.exe` | 生成的安装程序 |

---

## 自定义安装程序

### 修改版本号

编辑 `build\installer-gpu.iss`，修改第 14 行：
```pascal
#define AppVersion "1.0.0"
```

### 修改安装程序名称

编辑 `build\installer-gpu.iss`，修改第 30 行：
```pascal
OutputBaseFilename=PicSimProcess_GPU_Setup_v{#AppVersion}
```

### 添加图标

将 `.ico` 文件放入 `build\icon.ico`，或在 ISS 中修改：
```pascal
SetupIconFile=icon.ico
```

### 修改默认安装路径

编辑 `build\installer-gpu.iss`，修改第 24 行：
```pascal
DefaultDirName={autopf}\PicSimProcess
```
