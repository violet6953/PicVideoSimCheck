"""Progress panel showing scan stage and progress."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QLabel, QProgressBar, QVBoxLayout


class ProgressPanel(QFrame):
    """Panel displaying current scan stage, progress bar, and message."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("panel")
        self.setVisible(False)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel("扫描进度")
        title.setObjectName("sectionTitle")
        layout.addWidget(title)

        self.stage_badge = QLabel("准备中")
        self.stage_badge.setObjectName("stageBadge")
        layout.addWidget(self.stage_badge)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.stats_label = QLabel("")
        self.stats_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.stats_label)

        self.message_label = QLabel("准备中...")
        self.message_label.setObjectName("labelMuted")
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.message_label)

        layout.addStretch()

    def update_progress(self, stage: str, current: int, total: int, message: str) -> None:
        self.setVisible(True)
        self.stage_badge.setText(stage or "准备中")

        # Badge style based on stage
        badge_name = "stageBadge"
        if stage == "完成":
            badge_name = "stageBadgeCompleted"
        elif stage == "出错":
            badge_name = "stageBadgeError"
        elif stage == "已停止":
            badge_name = "stageBadgeStopped"

        if self.stage_badge.objectName() != badge_name:
            self.stage_badge.setObjectName(badge_name)
            self.style().unpolish(self.stage_badge)
            self.style().polish(self.stage_badge)

        pct = 0
        stats = ""
        if total > 0:
            pct = min(100, int((current / total) * 100))
            if stage == "扫描文件":
                stats = "扫描中..."
            elif stage == "图片特征提取":
                stats = f"{current} / {total} 张"
            elif stage == "图片相似度计算":
                stats = f"批次 {current} / {total}"
            elif stage == "视频相似度检测":
                stats = f"{current} / {total}"
            elif stage == "结果分组":
                stats = f"{current} / {total} 组"

        self.progress_bar.setValue(pct)
        self.stats_label.setText(stats)
        self.message_label.setText(message or "")

    def reset(self) -> None:
        self.setVisible(False)
        self.progress_bar.setValue(0)
        self.stats_label.setText("")
        self.message_label.setText("准备中...")
        self.stage_badge.setText("准备中")
        self.stage_badge.setObjectName("stageBadge")
