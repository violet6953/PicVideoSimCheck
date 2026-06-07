# PicSimProcess 打包与发布指南

本文档说明如何将 PicSimProcess 打包为独立的 Windows 桌面 exe，以及如何使用 Inno Setup 生成安装包。

---

## 目录

1. [环境准备](#环境准备)
2. [项目结构说明](#项目结构说明)
3. [构建 exe](#构建-exe)
   - [CPU 版](#cpu-版推荐)
   - [GPU 版](#gpu-版)
   - [一键构建脚本](#一键构建脚本)
4. [生成安装包](#生成安装包)
   - [Inno Setup 编译](#innosetup-编译)
5. [发布文件](#发布文件)
6. [常见问题](#常见问题)

---

## 环境准备

1. **Windows 10/11 64 位系统**
2. **Python 3.11**（项目使用 Python 3.11）
3. **虚拟环境已配置**
   ```cmd
   python -m venv venv
   venv\Scripts\activate.bat
   ```
4. **依赖已安装**
   - GPU 版需先安装 PyTorch CUDA 版本：
     ```cmd
     pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
     ```
   - 再安装其他依赖：
     ```cmd
     pip install -r requirements.txt
     ```
5. **PyInstaller**
   ```cmd
   pip install pyinstaller
   ```
6. **Inno Setup 7**
   - 下载地址：https://jrsoftware.org/isdl.php
   - 安装后 `ISCC.exe` 默认路径：`C:\Program Files\Inno Setup 7\ISCC.exe`

---

## 项目结构说明

```
PicSimProcess/
├── desktop.py                  # 桌面应用入口
├── requirements.txt            # Python 依赖
├── data/                       # 用户数据目录
│   ├── blocklist.json          # 误报记录（安装包会保留用户数据）
│   ├── input/                  # 输入目录占位
│   └── output/                 # 输出目录占位
├── build/                      # 打包配置目录
│   ├── icon.ico                # 应用程序图标
│   ├── build-cpu.py            # CPU 构建脚本
│   ├── build-gpu.py            # GPU 构建脚本
│   ├── build-all.bat           # 一键构建批处理
│   ├── PicSimProcess-CPU.spec  # PyInstaller CPU 配置
│   ├── PicSimProcess-GPU.spec  # PyInstaller GPU 配置
│   ├── installer-cpu.iss       # Inno Setup CPU 安装包脚本
│   └── installer-gpu.iss       # Inno Setup GPU 安装包脚本
├── src/                        # 核心算法
├── services/                   # 业务服务（含误报排除）
├── workers/                    # 扫描工作线程
├── gui/                        # PySide6 界面
├── dist-cpu/                   # CPU 构建输出（构建后生成）
├── dist-gpu/                   # GPU 构建输出（构建后生成）
└── Output/                     # 安装包输出（Inno Setup 生成）
```

---

## 构建 exe

### CPU 版（推荐）

体积小、无需 NVIDIA 显卡、适合大多数用户。

```cmd
python build\build-cpu.py
```

- 输出目录：`dist-cpu/PicSimProcess/`
- 主程序：`dist-cpu/PicSimProcess/PicSimProcess.exe`
- 典型大小：**约 200–400 MB**

### GPU 版

包含 PyTorch + CUDA runtime，支持 GPU 深度学习算法，体积很大。

```cmd
python build\build-gpu.py
```

- 输出目录：`dist-gpu/PicSimProcess/`
- 主程序：`dist-gpu/PicSimProcess/PicSimProcess.exe`
- 典型大小：**约 2–4 GB**
- 构建时间：**10–30 分钟**

### 一键构建脚本

也可以运行图形化选择脚本：

```cmd
build\build-all.bat
```

按提示选择 `1`（CPU）、`2`（GPU）或 `3`（两者都构建）。

---

## 生成安装包

### Inno Setup 编译

构建完 exe 后，使用 Inno Setup 编译对应的 `.iss` 脚本：

**CPU 安装包：**
```cmd
"C:\Program Files\Inno Setup 7\ISCC.exe" build\installer-cpu.iss
```

**GPU 安装包：**
```cmd
"C:\Program Files\Inno Setup 7\ISCC.exe" build\installer-gpu.iss
```

输出文件：
- `Output/PicSimProcess_CPU_Setup_v1.0.1.exe`
- `Output/PicSimProcess_GPU_Setup_v1.0.1.exe`

### 安装包特性

- **桌面快捷图标**：用户可选创建
- **开始菜单组**：自动创建
- **用户数据保护**：`blocklist.json` 等用户误报记录在升级/重装时不会被覆盖
- **卸载清理**：可选清理 `data/input` 和 `data/output` 目录
- **安装互斥**：安装时会检测程序是否正在运行

---

## 发布文件

发布时建议提供以下文件：

```
发布/
├── PicSimProcess_CPU_Setup_v1.0.1.exe   # 普通用户推荐
├── PicSimProcess_GPU_Setup_v1.0.1.exe   # 有 NVIDIA 显卡的用户
└── README.txt                           # 说明文件
```

`README.txt` 示例内容：

```
PicSimProcess 图片/视频相似度检测工具 v1.0.1

系统要求：
- Windows 10/11 64 位
- CPU 版：任意 64 位 Windows 电脑
- GPU 版：需要 NVIDIA 显卡并安装 CUDA 12.x 驱动

安装：
直接运行对应版本的 Setup 安装程序即可。

注意：
- GPU 版体积较大（约 3GB），但检测速度快，推荐有 NVIDIA 显卡的用户使用。
- CPU 版体积较小（约 300MB），适合大多数用户。
```

---

## 常见问题

### Q1: 构建 GPU 版时提示 `torch` 相关错误？

确保已安装 PyTorch GPU 版本：
```cmd
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

### Q2: 用户升级安装后，之前的误报记录丢失了？

已在 `installer-*.iss` 中配置 `blocklist.json` 使用 `onlyifdoesntexist` 标志，且代码会在打包后使用 `{app}\data\blocklist.json` 作为用户数据路径，因此升级时不会被覆盖。

### Q3: 安装包太大？

推荐普通用户发布 **CPU 版**。GPU 版由于包含 PyTorch 和 CUDA runtime，体积较大。

### Q4: 如何修改版本号？

编辑以下两个文件中的 `AppVersion` 宏：
- `build/installer-cpu.iss`
- `build/installer-gpu.iss`

```pascal
#define AppVersion "1.0.1"
```

---

## 配置文件清单

| 文件 | 用途 |
|---|---|
| `build/PicSimProcess-CPU.spec` | PyInstaller CPU 版 spec |
| `build/PicSimProcess-GPU.spec` | PyInstaller GPU 版 spec |
| `build/build-cpu.py` | CPU 构建脚本 |
| `build/build-gpu.py` | GPU 构建脚本 |
| `build/build-all.bat` | 一键构建批处理 |
| `build/installer-cpu.iss` | Inno Setup CPU 安装包 |
| `build/installer-gpu.iss` | Inno Setup GPU 安装包 |
| `build/icon.ico` | 程序图标 |
| `desktop.py` | 桌面应用入口 |
