# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for PicSimProcess CPU-only edition."""

import os
import sys
from PyInstaller.utils.hooks import collect_submodules

project_root = os.environ.get('PROJECT_ROOT', os.getcwd())
icon_path = os.path.join(project_root, 'build', 'icon.ico')
has_icon = os.path.exists(icon_path)

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
    binaries=[],
    datas=[
        (os.path.join(project_root, 'data', 'blocklist.json'), 'data'),
        (os.path.join(project_root, 'data', 'test_gpu'), os.path.join('data', 'test_gpu')),
        (os.path.join(project_root, 'src'), 'src'),
        (os.path.join(project_root, 'services'), 'services'),
        (os.path.join(project_root, 'workers'), 'workers'),
        (os.path.join(project_root, 'gui'), 'gui'),
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
        'src.video_similarity', 'src.utils',
        'services.blocklist_service',
        'workers.scan_worker',
        'gui.main_window', 'gui.styles',
        'gui.settings_panel', 'gui.progress_panel', 'gui.results_panel',
        'gui.blocklist_panel', 'gui.group_card', 'gui.result_item',
        'gui.preview_dialog', 'gui.flow_layout', 'gui.thumbnail_loader',
        'gui.animated_tabs', 'gui.animated_button', 'gui.explorer_utils',
        'PySide6.QtMultimedia', 'PySide6.QtMultimediaWidgets',
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
        'torch',
        'torchvision',
        'torchaudio',
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
