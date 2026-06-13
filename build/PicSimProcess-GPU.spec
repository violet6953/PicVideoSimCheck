# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PicSimProcess with full GPU support."""

import os
import sys
from PyInstaller.utils.hooks import collect_all, collect_dynamic_libs, collect_submodules

project_root = os.environ.get('PROJECT_ROOT', os.getcwd())
icon_path = os.path.join(project_root, 'build', 'icon.ico')
has_icon = os.path.exists(icon_path)

# ── Version info ──────────────────────────────────────────────────────────
APP_VERSION = "1.0.4"
APP_NAME = "PicSimProcess"
APP_COMPANY = "PicSimProcess"
APP_DESCRIPTION = "Image and Video Similarity Detection Tool (GPU Edition)"

# Windows VERSIONINFO resource
version_file = os.path.join(project_root, 'build', 'version_info.txt')
with open(version_file, 'w', encoding='utf-8') as vf:
    vf.write(f'''VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=({APP_VERSION.replace(".", ",")},0),
    prodvers=({APP_VERSION.replace(".", ",")},0),
    mask=0x3f,
    flags=0x0,
    OS=0x40004,
    fileType=0x1,
    subtype=0x0,
    date=(0, 0)
  ),
  kids=[
    StringFileInfo(
      [
      StringTable(
        '040904B0',
        [StringStruct('CompanyName', '{APP_COMPANY}'),
        StringStruct('FileDescription', '{APP_DESCRIPTION}'),
        StringStruct('FileVersion', '{APP_VERSION}'),
        StringStruct('InternalName', '{APP_NAME}'),
        StringStruct('LegalCopyright', 'Copyright (C) 2024'),
        StringStruct('OriginalFilename', '{APP_NAME}.exe'),
        StringStruct('ProductName', '{APP_NAME}'),
        StringStruct('ProductVersion', '{APP_VERSION}')])
      ]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)''')

# Collect PyTorch + torchvision
torch_binaries, torch_datas, torch_hiddenimports = collect_all('torch')
tv_binaries, tv_datas, tv_hiddenimports = collect_all('torchvision')
torch_dynamic_libs = collect_dynamic_libs('torch')
tv_dynamic_libs = collect_dynamic_libs('torchvision')

# Collect numpy.testing and scipy._lib submodules
numpy_testing_submodules = collect_submodules('numpy.testing')
scipy_submodules = collect_submodules('scipy._lib')

# Standard library modules that are dynamically imported
import_stdlib_dir = os.path.dirname(os.__file__)
stdlib_modules_to_include = [
    'pdb.py', 'bdb.py', 'cmd.py', 'codeop.py',
    'pstats.py', 'profile.py', 'trace.py',
]
stdlib_datas = []
for mod in stdlib_modules_to_include:
    src = os.path.join(import_stdlib_dir, mod)
    if os.path.exists(src):
        stdlib_datas.append((src, '.'))

a = Analysis(
    [os.path.join(project_root, 'desktop.py')],
    pathex=[project_root],
    binaries=[
        *torch_binaries,
        *tv_binaries,
        *torch_dynamic_libs,
        *tv_dynamic_libs,
    ],
    datas=[
        (os.path.join(project_root, 'data', 'blocklist.json'), 'data'),
        (os.path.join(project_root, 'data', 'test_gpu'), os.path.join('data', 'test_gpu')),
        (os.path.join(project_root, 'src'), 'src'),
        (os.path.join(project_root, 'services'), 'services'),
        (os.path.join(project_root, 'workers'), 'workers'),
        (os.path.join(project_root, 'gui'), 'gui'),
        *torch_datas,
        *tv_datas,
        *stdlib_datas,
    ],
    hiddenimports=[
        'PIL', 'PIL._imagingtk', 'PIL._tkinter_finder',
        'numpy', 'numpy.core._dtype_ctypes',
        'cv2', 'cv2.cv2',
        'imagehash', 'pywt', 'scipy.fftpack',
        'skimage', 'skimage.feature', 'skimage.metrics',
        'sklearn', 'sklearn.utils._cython_blas', 'sklearn.utils._heap',
        'sklearn.utils._sorting', 'sklearn.neighbors._partition_nodes', 'sklearn.tree._utils',
        'tqdm',
        'json', 're', 'threading', 'time', 'pathlib', 'os', 'io',
        'concurrent.futures', 'multiprocessing',
        'src.similarity', 'src.gpu_similarity', 'src.processor',
        'src.video_similarity', 'src.utils', 'src.memory_utils',
        'services.blocklist_service',
        'workers.scan_worker',
        'gui.main_window', 'gui.styles',
        'gui.settings_panel', 'gui.progress_panel', 'gui.results_panel',
        'gui.blocklist_panel', 'gui.group_card', 'gui.result_item',
        'gui.preview_dialog', 'gui.flow_layout', 'gui.thumbnail_loader',
        'gui.animated_tabs', 'gui.animated_button', 'gui.explorer_utils',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
        'torch', 'torch._C', 'torch._C._cuda', 'torch._C._nn',
        'torch.cuda', 'torch.cuda.amp', 'torch.cuda.amp.autocast_mode',
        'torch.cuda._utils', 'torch.cuda.graphs', 'torch.cuda.memory',
        'torch.backends', 'torch.backends.cuda', 'torch.backends.cudnn', 'torch.backends.mps',
        'torch.nn', 'torch.nn.functional', 'torch.nn.modules', 'torch.nn.parallel',
        'torch.utils', 'torch.utils.data', 'torch.utils.hooks',
        'torch.serialization', 'torch.jit', 'torch.fx', 'torch.package',
        'torch.distributed', 'torch.autograd', 'torch.autograd.function',
        'torchvision', 'torchvision.models', 'torchvision.models.resnet',
        'torchvision.transforms', 'torchvision.transforms.functional',
        'torchvision.ops', 'torchvision.utils',
        *torch_hiddenimports,
        *tv_hiddenimports,
        *numpy_testing_submodules,
        *scipy_submodules,
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'matplotlib',
        'pandas',
        'pytest',
        'tkinter.test',
        'IPython',
        'jupyter',
        'flask',
        'jinja2',
        'werkzeug',
        'markupsafe',
        'itsdangerous',
        'click',
        'blinker',
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='PicSimProcess',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_path if has_icon else None,
    version=version_file if os.path.exists(version_file) else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='PicSimProcess',
)
