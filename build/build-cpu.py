#!/usr/bin/env python3
"""PicSimProcess CPU Build Script — PySide6 Desktop Edition."""

import os
import shutil
import subprocess
import sys


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BUILD_DIR = os.path.join(PROJECT_ROOT, 'build')
DIST_DIR = os.path.join(PROJECT_ROOT, 'dist-cpu')
SPEC_FILE = os.path.join(BUILD_DIR, 'PicSimProcess-CPU.spec')


def clean():
    """Remove ALL old build artifacts to prevent stale Flask/web UI cache."""
    dirs_to_remove = [
        os.path.join(BUILD_DIR, 'PicSimProcess-CPU'),
        os.path.join(BUILD_DIR, 'buildPicSimProcess-CPU'),
        DIST_DIR,
        os.path.join(PROJECT_ROOT, '__pycache__'),
    ]

    removed_any = False
    for d in dirs_to_remove:
        if os.path.exists(d):
            print(f"Removing: {d}")
            try:
                shutil.rmtree(d, ignore_errors=True)
                removed_any = True
            except Exception as e:
                print(f"  Warning: could not fully remove {d}: {e}")

    for fname in os.listdir(BUILD_DIR):
        fpath = os.path.join(BUILD_DIR, fname)
        if os.path.isfile(fpath) and fname.endswith(('.toc', '.pyz', '.pkg', '.zip')):
            print(f"Removing stray cache file: {fpath}")
            try:
                os.remove(fpath)
                removed_any = True
            except Exception as e:
                print(f"  Warning: could not remove {fpath}: {e}")

    if removed_any:
        print("Clean complete.")
    else:
        print("Nothing to clean.")


def build():
    entry_script = os.path.join(PROJECT_ROOT, 'desktop.py')
    if not os.path.exists(entry_script):
        print(f"\n[FAIL] Entry script not found: {entry_script}")
        sys.exit(1)

    with open(entry_script, 'r', encoding='utf-8') as f:
        content = f.read()
    if 'PySide6' not in content:
        print("\n[FAIL] desktop.py does not appear to be the PySide6 desktop entry!")
        sys.exit(1)

    cmd = [
        sys.executable, '-m', 'PyInstaller',
        SPEC_FILE,
        '--clean',
        '--noconfirm',
        '--distpath', DIST_DIR,
    ]

    print(f"Running: {' '.join(cmd)}")
    print("-" * 60)
    print("[INFO] Entry: desktop.py (PySide6 native GUI)")
    print("[INFO] CPU edition excludes PyTorch/CUDA for a smaller package")
    print("-" * 60)

    result = subprocess.run(cmd, cwd=PROJECT_ROOT)

    if result.returncode != 0:
        print("\n[FAIL] Build failed!")
        sys.exit(1)

    print("\n[OK] Build successful!")

    exe_dir = os.path.join(DIST_DIR, 'PicSimProcess')
    exe_path = os.path.join(exe_dir, 'PicSimProcess.exe')

    if os.path.exists(exe_path):
        total_size = 0
        for dirpath, dirnames, filenames in os.walk(exe_dir):
            for f in filenames:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)

        size_mb = total_size / (1024 ** 2)
        print(f"   Output directory: {exe_dir}")
        print(f"   Main executable:  {exe_path}")
        print(f"   Total size:       {size_mb:.2f} MB")

        build_analysis = os.path.join(BUILD_DIR, 'PicSimProcess-CPU', 'Analysis-00.toc')
        if os.path.exists(build_analysis):
            with open(build_analysis, 'r', encoding='utf-8') as f:
                first_line = f.readline()
            if 'app.py' in first_line:
                print("\n[ERROR] Build still references old app.py (Flask)!")
                print("         Run this script again or manually delete build/PicSimProcess-CPU")
                sys.exit(1)
            elif 'desktop.py' in first_line:
                print("   Entry script:     desktop.py (verified)")

    return exe_dir


def main():
    print("=" * 60)
    print("  PicSimProcess CPU Build (PySide6 Desktop)")
    print("=" * 60)

    try:
        import PyInstaller
        print(f"   PyInstaller: {PyInstaller.__version__}")
    except ImportError:
        print("\n[FAIL] PyInstaller not found. Installing...")
        subprocess.run([sys.executable, '-m', 'pip', 'install', 'pyinstaller'])

    clean()
    build()

    print("\n" + "=" * 60)
    print("  Build complete!")
    print("  Next step: compile installer with Inno Setup")
    print('  "C:\\Program Files\\Inno Setup 7\\ISCC.exe" build\\installer-cpu.iss')
    print("=" * 60)


if __name__ == '__main__':
    main()
