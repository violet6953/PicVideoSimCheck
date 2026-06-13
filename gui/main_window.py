"""Main application window for PicSimProcess desktop GUI."""

from __future__ import annotations

import threading

from PySide6.QtCore import QSettings, Qt
from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QScrollArea,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from services.blocklist_service import (
    add_blocklist_batch,
    filter_blocklist_for_folders,
    load_blocklist,
)
from workers.scan_worker import ScanWorker

from .animated_tabs import AnimatedTabs
from .blocklist_panel import BlocklistPanel
from .preview_dialog import PreviewDialog
from .progress_panel import ProgressPanel
from .results_panel import ResultsPanel
from .settings_panel import SettingsPanel


class MainWindow(QMainWindow):
    """Primary window containing all UI panels."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PicSimProcess - 图片/视频相似度检测")
        self.resize(1400, 900)

        self._settings = QSettings("PicSimProcess", "PicSimProcess")
        self._cancel_event = threading.Event()
        self._worker: ScanWorker | None = None
        self._preview_dialog: PreviewDialog | None = None
        self._current_results: list[dict] = []
        self._current_folders: list[str] = []

        self._init_ui()
        self._load_app_settings()

    def _init_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(12)

        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left column
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(12)

        self.settings_panel = SettingsPanel()
        self.settings_panel.start_scan.connect(self._start_scan)
        self.settings_panel.stop_scan.connect(self._stop_scan)
        self.settings_panel.check_gpu.connect(self._check_gpu)

        # Wrap settings in scroll area so it scrolls when too tall
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        settings_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        settings_scroll.setWidget(self.settings_panel)
        left_layout.addWidget(settings_scroll, 1)

        self.progress_panel = ProgressPanel()
        left_layout.addWidget(self.progress_panel)

        splitter.addWidget(left_widget)

        # Right column (tabs)
        self.tabs = AnimatedTabs()
        self.results_panel = ResultsPanel()
        self.results_panel.mark_all_false_positive.connect(self._mark_all_false_positive)
        self.results_panel.delete_selected.connect(self._delete_selected)
        self.results_panel.preview_requested.connect(self._open_preview)
        self.results_panel.selection_changed.connect(self._update_delete_button)
        self.tabs.addTab(self.results_panel, "输出结果")

        self.blocklist_panel = BlocklistPanel()
        self.blocklist_panel.blocklist_changed.connect(self._on_blocklist_changed)
        self.blocklist_panel.preview_requested.connect(self._open_preview)
        self.tabs.addTab(self.blocklist_panel, "误报记录")
        self.tabs.currentChanged.connect(self._on_tab_changed)

        splitter.addWidget(self.tabs)
        splitter.setSizes([420, 980])
        layout.addWidget(splitter)

        self._init_version_label()

    def _init_version_label(self) -> None:
        """Add a version info label to the bottom-right status bar."""
        self._version_label = QLabel(self._get_version_text())
        self._version_label.setObjectName("versionLabel")
        self.statusBar().addPermanentWidget(self._version_label)

    @staticmethod
    def _get_version_text() -> str:
        """Read build info; fallback to dev placeholder if not available."""
        try:
            from src.build_info import CRT_TIME, DEV_BY, VERSION
            return f"ver：{VERSION} DevBy：{DEV_BY} CsrtTime：{CRT_TIME}"
        except Exception:
            return "ver：dev DevBy：RyuguShiori CsrtTime：--"

    def _load_app_settings(self) -> None:
        try:
            folders = self._settings.value("folders", [])
            if isinstance(folders, str):
                folders = [folders]
            elif not isinstance(folders, list):
                folders = []
            saved = {
                "folders": folders,
                "method": self._settings.value("method", "gpu"),
                "threshold": float(self._settings.value("threshold", 0.95)),
                "video_enabled": self._settings.value("video_enabled", "false").lower() == "true",
                "video_threshold": float(self._settings.value("video_threshold", 0.90)),
                "video_fps": float(self._settings.value("video_fps", 1.0)),
                "video_max_frames": int(self._settings.value("video_max_frames", 32)),
            }
            self.settings_panel.load_settings(saved)
        except Exception:
            pass

        geometry = self._settings.value("geometry")
        if geometry:
            self.restoreGeometry(geometry)

    def _save_app_settings(self) -> None:
        s = self.settings_panel.get_settings()
        self._settings.setValue("folders", s["folders"])
        self._settings.setValue("method", s["method"])
        self._settings.setValue("threshold", s["threshold"])
        self._settings.setValue("video_enabled", "true" if s["video_enabled"] else "false")
        self._settings.setValue("video_threshold", s["video_threshold"])
        self._settings.setValue("video_fps", s["video_fps"])
        self._settings.setValue("video_max_frames", s["video_max_frames"])
        self._settings.setValue("geometry", self.saveGeometry())

    def closeEvent(self, event) -> None:
        self._save_app_settings()
        if self._worker and self._worker.isRunning():
            self._cancel_event.set()
            self._worker.wait(2000)
        event.accept()

    def _check_gpu(self) -> None:
        try:
            import torch
            available = torch.cuda.is_available()
            gpu_name = torch.cuda.get_device_name(0) if available else None
            message = f"GPU detected: {gpu_name}" if available else "CUDA not available, will use CPU mode"
            self.settings_panel.set_gpu_status(available, message)
        except ImportError:
            self.settings_panel.set_gpu_status(False, "PyTorch not installed")
        except Exception as e:
            self.settings_panel.set_gpu_status(False, str(e))

    def _start_scan(self) -> None:
        s = self.settings_panel.get_settings()
        folders = s["folders"]
        if not folders:
            QMessageBox.information(self, "提示", "请至少添加一个图片文件夹")
            return

        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "提示", "已有扫描任务在进行中")
            return

        self._cancel_event.clear()
        self._current_folders = folders
        self.settings_panel.set_running(True)
        self.progress_panel.reset()
        self.results_panel.clear_results()

        self._worker = ScanWorker(
            folders=folders,
            method=s["method"],
            threshold=s["threshold"],
            video_enabled=s["video_enabled"],
            video_method=s["video_method"],
            video_threshold=s["video_threshold"],
            video_fps=s["video_fps"],
            video_max_frames=s["video_max_frames"],
            cancel_event=self._cancel_event,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_with_results.connect(self._on_scan_complete)
        self._worker.error_occurred.connect(self._on_scan_error)
        self._worker.stopped.connect(self._on_scan_stopped)
        self._worker.start()

    def _stop_scan(self) -> None:
        self._cancel_event.set()
        self.progress_panel.update_progress("已停止", 0, 0, "正在停止扫描...")

    def _on_progress(self, state: dict) -> None:
        self.progress_panel.update_progress(
            stage=state.get("stage", ""),
            current=state.get("stage_current", 0),
            total=state.get("stage_total", 0),
            message=state.get("message", ""),
            detail_current=state.get("detail_current"),
            detail_total=state.get("detail_total"),
        )

    def _on_scan_complete(self, groups: list[dict]) -> None:
        self._current_results = groups
        self.settings_panel.set_running(False)
        blocklist = load_blocklist()
        filtered_count = len(filter_blocklist_for_folders(blocklist, self._current_folders))
        self.results_panel.set_results(groups, blocklist_count=filtered_count)
        self._save_app_settings()

    def _on_scan_error(self, message: str) -> None:
        self.settings_panel.set_running(False)
        self.progress_panel.update_progress("出错", 0, 0, f"扫描出错: {message}")
        QMessageBox.critical(self, "扫描错误", f"扫描过程中发生错误：\n{message}")

    def _on_scan_stopped(self) -> None:
        self.settings_panel.set_running(False)
        self.progress_panel.update_progress("已停止", 0, 0, "扫描已停止")

    def _delete_selected(self) -> None:
        paths = self.results_panel.get_selected_paths()
        if paths:
            self.results_panel.delete_items(paths)
            self._update_delete_button()

    def _mark_all_false_positive(self) -> None:
        groups = self.results_panel.get_all_groups_paths()
        if not groups:
            QMessageBox.information(self, "提示", "当前没有扫描结果需要标记")
            return

        reply = QMessageBox.question(
            self,
            "确认标记",
            f"确定要将当前 {len(groups)} 组相似文件全部标记为误报吗？\n\n"
            "此操作会将所有相似分组加入误报排除列表，下次扫描时将不再显示。",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        try:
            result = add_blocklist_batch(groups)
            self.results_panel.clear_results()
            self.blocklist_panel.refresh(self._current_folders)
            QMessageBox.information(
                self,
                "标记完成",
                f"已将 {len(groups)} 组相似文件标记为误报\n"
                f"（新增 {result['added']} 组，覆盖 {result['covered']} 组，替换 {result['replaced']} 组）",
            )
        except Exception as e:
            QMessageBox.critical(self, "错误", f"批量标记失败：{e}")

    def _open_preview(self, path: str, paths: list[str]) -> None:
        if self._preview_dialog is None:
            self._preview_dialog = PreviewDialog(self)
        self._preview_dialog.open_group(path, paths)

    def _on_tab_changed(self, index: int) -> None:
        if index == 1:
            self.blocklist_panel.refresh(self._current_folders)

    def _on_blocklist_changed(self) -> None:
        blocklist = load_blocklist()
        filtered_count = len(filter_blocklist_for_folders(blocklist, self._current_folders))
        self.results_panel.set_blocklist_info(filtered_count)

    def _update_delete_button(self) -> None:
        # No-op; individual card buttons handle themselves
        pass
