"""Left settings panel for the main window."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)


class SettingsPanel(QFrame):
    """Left panel containing all scan configuration controls."""

    start_scan = Signal()
    stop_scan = Signal()
    check_gpu = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self._folders: list[str] = []
        self._init_ui()

    def _init_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        title = QLabel("扫描设置")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        # Folder list
        layout.addWidget(QLabel("目标文件夹"))
        self.folder_list_widget = QVBoxLayout()
        self.folder_list_widget.setSpacing(8)
        folder_container = QWidget()
        folder_container.setLayout(self.folder_list_widget)
        layout.addWidget(folder_container)

        self.add_folder_btn = QPushButton("+ 添加文件夹")
        self.add_folder_btn.setObjectName("secondary")
        self.add_folder_btn.clicked.connect(self._add_folder)
        layout.addWidget(self.add_folder_btn)

        # Method
        layout.addWidget(QLabel("图片检测算法"))
        self.method_combo = QComboBox()
        for text, value in [
            ("GPU 深度学习 (ResNet50，推荐)", "gpu"),
            ("pHash 感知哈希", "phash"),
            ("dHash 差值哈希", "dhash"),
            ("aHash 平均哈希", "ahash"),
            ("wHash 小波哈希", "whash"),
            ("颜色直方图", "histogram"),
            ("SSIM 结构相似性", "ssim"),
            ("ORB 特征匹配", "orb"),
        ]:
            self.method_combo.addItem(text, value)
        self.method_combo.setCurrentIndex(0)
        layout.addWidget(self.method_combo)

        # GPU check
        gpu_layout = QHBoxLayout()
        self.check_gpu_btn = QPushButton("GPU 调用")
        self.check_gpu_btn.setObjectName("secondary")
        self.check_gpu_btn.clicked.connect(self.check_gpu.emit)
        gpu_layout.addWidget(self.check_gpu_btn)
        self.gpu_status_label = QLabel("未检测")
        self.gpu_status_label.setObjectName("labelMuted")
        gpu_layout.addWidget(self.gpu_status_label, 1)
        layout.addLayout(gpu_layout)

        # Image threshold
        layout.addWidget(QLabel("图片相似度阈值"))
        threshold_layout = QHBoxLayout()
        self.threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.threshold_slider.setRange(50, 100)
        self.threshold_slider.setValue(95)
        self.threshold_slider.setTracking(False)
        self.threshold_slider.valueChanged.connect(self._update_threshold_label)
        self.threshold_slider.sliderMoved.connect(self._update_threshold_label)
        threshold_layout.addWidget(self.threshold_slider)
        self.threshold_value_label = QLabel("0.95")
        self.threshold_value_label.setStyleSheet("color: #3b82f6; font-weight: bold; min-width: 36px;")
        threshold_layout.addWidget(self.threshold_value_label)
        layout.addLayout(threshold_layout)

        preset_layout = QHBoxLayout()
        self.threshold_presets: dict[str, QPushButton] = {}
        for val in ["0.90", "0.95", "0.99", "1.00"]:
            btn = QPushButton(val)
            btn.setObjectName("preset")
            btn.setCheckable(True)
            btn.setProperty("class", "small")
            btn.clicked.connect(lambda checked, v=val: self._set_threshold(v))
            preset_layout.addWidget(btn)
            self.threshold_presets[val] = btn
        self.threshold_presets["0.95"].setChecked(True)
        layout.addLayout(preset_layout)

        hints_layout = QHBoxLayout()
        hints_layout.addWidget(QLabel("宽松（更多结果）"))
        hints_layout.addStretch()
        hints_layout.addWidget(QLabel("严格（更少结果）"))
        layout.addLayout(hints_layout)

        # Video toggle
        self.video_toggle = QCheckBox("同时检测视频")
        self.video_toggle.stateChanged.connect(self._toggle_video_settings)
        layout.addWidget(self.video_toggle)

        # Video settings container
        self.video_settings = QFrame()
        self.video_settings.setObjectName("videoSettings")
        video_layout = QVBoxLayout(self.video_settings)
        video_layout.setContentsMargins(12, 12, 12, 12)
        video_layout.setSpacing(10)
        video_layout.addWidget(QLabel("视频检测算法"))
        self.video_method_combo = QComboBox()
        self.video_method_combo.addItem("GPU 深度学习 (ResNet50，推荐)", "gpu")
        video_layout.addWidget(self.video_method_combo)
        video_layout.addWidget(QLabel("基于关键帧提取 + ResNet50 特征比对"))

        video_layout.addWidget(QLabel("视频相似度阈值"))
        vthreshold_layout = QHBoxLayout()
        self.video_threshold_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_threshold_slider.setRange(50, 100)
        self.video_threshold_slider.setValue(90)
        self.video_threshold_slider.setTracking(False)
        self.video_threshold_slider.valueChanged.connect(self._update_video_threshold_label)
        self.video_threshold_slider.sliderMoved.connect(self._update_video_threshold_label)
        vthreshold_layout.addWidget(self.video_threshold_slider)
        self.video_threshold_value_label = QLabel("0.90")
        self.video_threshold_value_label.setStyleSheet("color: #a855f7; font-weight: bold; min-width: 36px;")
        vthreshold_layout.addWidget(self.video_threshold_value_label)
        video_layout.addLayout(vthreshold_layout)

        vpreset_layout = QHBoxLayout()
        self.video_threshold_presets: dict[str, QPushButton] = {}
        for val in ["0.85", "0.90", "0.95", "1.00"]:
            btn = QPushButton(val)
            btn.setObjectName("preset")
            btn.setCheckable(True)
            btn.setProperty("class", "small")
            btn.clicked.connect(lambda checked, v=val: self._set_video_threshold(v))
            vpreset_layout.addWidget(btn)
            self.video_threshold_presets[val] = btn
        self.video_threshold_presets["0.90"].setChecked(True)
        video_layout.addLayout(vpreset_layout)

        video_layout.addWidget(QLabel("视频采样帧率（帧/秒）"))
        vfps_layout = QHBoxLayout()
        self.video_fps_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_fps_slider.setRange(1, 10)
        self.video_fps_slider.setValue(2)
        self.video_fps_slider.setTracking(False)
        self.video_fps_slider.valueChanged.connect(self._update_video_fps_label)
        self.video_fps_slider.sliderMoved.connect(self._update_video_fps_label)
        vfps_layout.addWidget(self.video_fps_slider)
        self.video_fps_value_label = QLabel("1.0")
        self.video_fps_value_label.setStyleSheet("color: #a855f7; font-weight: bold; min-width: 32px;")
        vfps_layout.addWidget(self.video_fps_value_label)
        video_layout.addLayout(vfps_layout)

        video_layout.addWidget(QLabel("每视频最大帧数"))
        vmax_layout = QHBoxLayout()
        self.video_max_frames_slider = QSlider(Qt.Orientation.Horizontal)
        self.video_max_frames_slider.setRange(1, 16)
        self.video_max_frames_slider.setValue(4)
        self.video_max_frames_slider.setTracking(False)
        self.video_max_frames_slider.valueChanged.connect(self._update_video_max_frames_label)
        self.video_max_frames_slider.sliderMoved.connect(self._update_video_max_frames_label)
        vmax_layout.addWidget(self.video_max_frames_slider)
        self.video_max_frames_value_label = QLabel("32")
        self.video_max_frames_value_label.setStyleSheet("color: #a855f7; font-weight: bold; min-width: 32px;")
        vmax_layout.addWidget(self.video_max_frames_value_label)
        video_layout.addLayout(vmax_layout)

        self.video_settings.setVisible(False)
        layout.addWidget(self.video_settings)

        # Actions
        actions_layout = QHBoxLayout()
        self.start_btn = QPushButton("开始扫描")
        self.start_btn.setObjectName("primary")
        self.start_btn.clicked.connect(self.start_scan.emit)
        actions_layout.addWidget(self.start_btn)

        self.stop_btn = QPushButton("停止扫描")
        self.stop_btn.setObjectName("danger")
        self.stop_btn.setEnabled(False)
        self.stop_btn.clicked.connect(self.stop_scan.emit)
        actions_layout.addWidget(self.stop_btn)
        layout.addLayout(actions_layout)

        layout.addStretch()

    def _render_folder_list(self) -> None:
        # Clear existing items
        while self.folder_list_widget.count():
            item = self.folder_list_widget.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for i, path in enumerate(self._folders):
            row = QHBoxLayout()
            row.setSpacing(8)
            row.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(path)
            lbl.setToolTip(path)
            lbl.setWordWrap(False)
            row.addWidget(lbl, 1)
            btn = QPushButton("×")
            btn.setObjectName("iconButton")
            btn.clicked.connect(lambda checked, idx=i: self._remove_folder(idx))
            row.addWidget(btn)
            container = QWidget()
            container.setObjectName("folderItem")
            container.setLayout(row)
            self.folder_list_widget.addWidget(container)

    def _add_folder(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if folder and folder not in self._folders:
            self._folders.append(folder)
            self._render_folder_list()

    def _remove_folder(self, index: int) -> None:
        if 0 <= index < len(self._folders):
            self._folders.pop(index)
            self._render_folder_list()

    def _update_threshold_label(self, value: int) -> None:
        val = value / 100.0
        self.threshold_value_label.setText(f"{val:.2f}")
        for k, btn in self.threshold_presets.items():
            btn.setChecked(abs(float(k) - val) < 0.005)

    def _set_threshold(self, value: str) -> None:
        v = int(float(value) * 100)
        self.threshold_slider.setValue(v)
        self._update_threshold_label(v)

    def _update_video_threshold_label(self, value: int) -> None:
        val = value / 100.0
        self.video_threshold_value_label.setText(f"{val:.2f}")
        for k, btn in self.video_threshold_presets.items():
            btn.setChecked(abs(float(k) - val) < 0.005)

    def _set_video_threshold(self, value: str) -> None:
        v = int(float(value) * 100)
        self.video_threshold_slider.setValue(v)
        self._update_video_threshold_label(v)

    def _update_video_fps_label(self, value: int) -> None:
        val = value / 2.0
        self.video_fps_value_label.setText(f"{val:.1f}")

    def _update_video_max_frames_label(self, value: int) -> None:
        val = value * 8
        self.video_max_frames_value_label.setText(str(val))

    def _toggle_video_settings(self, state: int) -> None:
        self.video_settings.setVisible(state == Qt.CheckState.Checked.value)

    def set_gpu_status(self, available: bool, message: str) -> None:
        self.gpu_status_label.setText(message)
        self.gpu_status_label.setObjectName("statusOk" if available else "statusError")
        self.style().unpolish(self.gpu_status_label)
        self.style().polish(self.gpu_status_label)

    def get_folders(self) -> list[str]:
        return list(self._folders)

    def get_settings(self) -> dict:
        return {
            "folders": list(self._folders),
            "method": self.method_combo.currentData(),
            "threshold": self.threshold_slider.value() / 100.0,
            "video_enabled": self.video_toggle.isChecked(),
            "video_method": self.video_method_combo.currentData() if self.video_toggle.isChecked() else "gpu",
            "video_threshold": self.video_threshold_slider.value() / 100.0,
            "video_fps": self.video_fps_slider.value() / 2.0,
            "video_max_frames": self.video_max_frames_slider.value() * 8,
        }

    def set_running(self, running: bool) -> None:
        self.start_btn.setEnabled(not running)
        self.stop_btn.setEnabled(running)
        self.add_folder_btn.setEnabled(not running)
        self.method_combo.setEnabled(not running)
        self.threshold_slider.setEnabled(not running)
        self.video_toggle.setEnabled(not running)
        if self.video_toggle.isChecked():
            self.video_method_combo.setEnabled(not running)
            self.video_threshold_slider.setEnabled(not running)
            self.video_fps_slider.setEnabled(not running)
            self.video_max_frames_slider.setEnabled(not running)

    def load_settings(self, settings: dict) -> None:
        folders = settings.get("folders", [])
        self._folders = [f for f in folders if isinstance(f, str)]
        self._render_folder_list()

        method = settings.get("method", "gpu")
        idx = self.method_combo.findData(method)
        if idx >= 0:
            self.method_combo.setCurrentIndex(idx)

        threshold = settings.get("threshold", 0.95)
        self.threshold_slider.setValue(int(threshold * 100))
        self._update_threshold_label(int(threshold * 100))

        video_enabled = settings.get("video_enabled", False)
        self.video_toggle.setChecked(video_enabled)
        self._toggle_video_settings(Qt.CheckState.Checked.value if video_enabled else Qt.CheckState.Unchecked.value)

        if video_enabled:
            vt = settings.get("video_threshold", 0.90)
            self.video_threshold_slider.setValue(int(vt * 100))
            self._update_video_threshold_label(int(vt * 100))

            vfps = settings.get("video_fps", 1.0)
            self.video_fps_slider.setValue(int(vfps * 2))
            self._update_video_fps_label(int(vfps * 2))

            vmf = settings.get("video_max_frames", 32)
            self.video_max_frames_slider.setValue(vmf // 8)
            self._update_video_max_frames_label(vmf // 8)
