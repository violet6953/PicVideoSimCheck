# PicSimProcess

**启动入口（桌面版）**：`python desktop.py`  
**命令行入口**：`python main.py --help`

图片相似度检测与去重工具，支持 GPU 加速和原生桌面界面操作，可用于查找重复图片、相似图片分组、批量去重等场景。

---

## 环境配置

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11，macOS，Linux |
| Python | 3.10 或更高版本 |
| GPU (可选) | NVIDIA RTX 2080 Ti 或支持 CUDA 的显卡 |
| CUDA (可选) | 11.8 或 12.x 版本（如需 GPU 加速） |

### 1. 创建 Python 虚拟环境

```bash
cd PicSimProcess
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 2. 安装 PyTorch GPU 版本

**必须先单独安装 PyTorch GPU 版本**，`requirements.txt` 中已将其排除，防止 `pip` 误装 CPU 版本。

```bash
# CUDA 12.x 版本（cu121 向后兼容 CUDA 12.0）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

> **说明**：PyTorch 官方未提供 CUDA 12.0 专用 wheel 包，cu121（CUDA 12.1）向后兼容已安装的 CUDA 12.0。只要 NVIDIA 驱动支持 CUDA 12.0，cu121 版本的 PyTorch 即可正常调用 GPU。

### 3. 安装项目其余依赖

```bash
pip install -r requirements.txt
```

### 4. 验证 GPU 是否可用

```bash
python -c "import torch; print('CUDA available:', torch.cuda.is_available()); print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'None')"
```

若输出 `CUDA available: True` 并显示显卡名称（如 `NVIDIA GeForce RTX 2080 Ti`），则 GPU 环境配置成功。

---

## 功能说明

- **GPU 深度学习加速**：基于 PyTorch ResNet50 预训练模型提取图片特征，利用 NVIDIA GPU 大幅加速相似度计算
- **多种 CPU 算法**：感知哈希 (pHash/dHash/aHash/wHash)、颜色直方图、SSIM 结构相似性、ORB 特征匹配
- **原生桌面界面**：基于 PySide6 的原生应用窗口，无需浏览器
- **相似图片分组扫描**：自动将相似/重复图片聚类展示，每组内按文件大小从大到小排列
- **图片信息展示**：显示文件名、文件大小、分辨率，支持缩略图预览，大文件优先展示在左侧
- **批量删除**：支持勾选多张图片一键删除
- **任务控制**：可随时开始或停止扫描任务

---

## 操作步骤

### 启动桌面应用

```bash
python desktop.py
```

程序会直接打开一个原生桌面窗口，无需浏览器。

### 重启应用

修改代码或配置后，直接关闭窗口重新运行即可：

```bash
python desktop.py
```

### 1. 选择图片文件夹

- 点击 **"+ 添加文件夹"** 按钮，在弹出的系统文件夹对话框中选择要扫描的图片文件夹
- 可以添加多个文件夹同时扫描
- 点击文件夹项右侧的 × 可移除

### 2. 配置扫描参数

| 参数 | 说明 |
|------|------|
| **检测算法** | 推荐选择 **"GPU 深度学习 (ResNet50)"** 获得最佳检测效果；无 GPU 时可选择 pHash 等 CPU 算法 |
| **相似度阈值** | 滑动条调整，值越高越严格。GPU 模式推荐 0.80~0.85，CPU 哈希模式推荐 0.85 |
| **同时检测视频** | 开启后会额外扫描视频文件的关键帧相似度 |

### 3. 开始扫描

- 点击 **"开始扫描"** 按钮
- 进度条会实时显示扫描进度
- 扫描过程中可随时点击 **"停止扫描"** 中断任务

### 4. 查看结果

扫描完成后，右侧会展示所有相似/重复图片的分组，每组包含：

- 图片缩略图（点击可放大预览）
- 文件名称
- 分辨率（如 `1920x1080`）
- 文件大小（如 `2.5 MB`）
- 每组内图片按**文件大小从大到小**排列（最大的在左边）

### 5. 删除图片

- 在每组中勾选要删除的图片（默认除第一个外全部勾选）
- 点击顶部的 **"删除选中"** 或每组的 **"删除本组选中"**
- 确认后即可批量删除
- 删除后结果会自动刷新

### 6. 误报排除

- 点击每组的 **"标记为非相似（误报）"** 可将该组加入排除列表
- 点击顶部 **"一键清除误报"** 可将当前所有结果标记为误报
- 在 **"误报记录"** 标签页中可以查看和管理已排除的分组

---

## 算法说明

| 算法 | 原理 | 适用场景 | 阈值建议 |
|------|------|---------|---------|
| **GPU 深度学习** | ResNet50 提取 2048 维特征向量，余弦相似度 | 通用，内容语义相似检测效果最佳 | 0.80~0.85 |
| `phash` | 感知哈希 | 通用，抗缩放/轻微裁剪 | 0.85 |
| `dhash` | 差值哈希 | 快速，抗微小变化 | 0.85 |
| `ahash` | 平均哈希 | 极快，对色彩敏感 | 0.85 |
| `whash` | 小波哈希 | 平衡速度与精度 | 0.85 |
| `histogram` | 颜色直方图 | 颜色分布相似 | 0.80 |
| `ssim` | 结构相似性 | 像素级结构相似 | 0.90 |
| `orb` | ORB 特征匹配 | 旋转/缩放/角度变化 | 0.20~0.30 |

---

## 命令行用法

原命令行工具仍然可用：

```bash
# 比较两张图片
python main.py compare image1.jpg image2.jpg --method gpu

# 查找目录中的相似文件
python main.py find "C:\Pictures" --recursive --method gpu --threshold 0.85

# 分组显示
python main.py group "C:\Pictures" --recursive

# 删除重复文件
python main.py dedup "C:\Pictures" --recursive --strategy keep_best
```

---

## 项目结构

```
PicSimProcess/
├── desktop.py              # 桌面应用入口（推荐）
├── main.py                 # 命令行入口
├── gui/                    # PySide6 桌面界面
│   ├── __init__.py
│   ├── main_window.py      # 主窗口
│   ├── settings_panel.py   # 左侧设置面板
│   ├── progress_panel.py   # 进度显示
│   ├── results_panel.py    # 结果面板
│   ├── blocklist_panel.py  # 误报记录面板
│   ├── group_card.py       # 相似分组卡片
│   ├── result_item.py      # 单个结果项（缩略图）
│   ├── preview_dialog.py   # 图片/视频预览弹窗
│   ├── flow_layout.py      # 自适应流式布局
│   ├── thumbnail_loader.py # 异步缩略图加载
│   └── styles.py           # 暗色主题样式
├── workers/
│   ├── __init__.py
│   └── scan_worker.py      # 后台扫描线程
├── services/
│   ├── __init__.py
│   └── blocklist_service.py # 误报记录持久化
├── src/                    # 核心算法（与桌面端复用）
│   ├── __init__.py
│   ├── similarity.py       # CPU 相似度算法
│   ├── gpu_similarity.py   # GPU 深度学习相似度
│   ├── processor.py        # 批量处理与去重
│   ├── video_similarity.py # 视频相似度
│   └── utils.py            # 工具函数
├── tests/
│   └── test_similarity.py  # 单元测试
├── data/
│   ├── input/              # 放入待检测图片
│   └── output/             # 检测结果输出
├── build/                  # PyInstaller 打包配置
├── requirements.txt
└── README.md
```

---

## 常见问题

**Q: 桌面版无法启动？**  
A: 请确认已安装 `pyside6`：`pip install pyside6>=6.6.0`

**Q: GPU 模式无法使用，提示 CUDA 不可用？**  
A: 请检查 NVIDIA 显卡驱动是否安装，并安装对应 CUDA 版本的 PyTorch。也可在算法选择中切换为 CPU 模式使用。

**Q: 扫描大量图片时界面卡顿？**  
A: 扫描在后台线程运行，缩略图也采用异步加载。如果结果过多，界面滚动可能略有延迟，建议分批扫描或提高阈值减少结果。

**Q: 误删了图片怎么办？**  
A: 删除操作会直接删除文件，不会放入回收站。请在删除前仔细确认勾选的内容。
