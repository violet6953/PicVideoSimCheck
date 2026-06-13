"""Qt Stylesheet for PicSimProcess dark theme."""

DARK_STYLE = """
QMainWindow {
    background-color: #0a0f1a;
}

QWidget {
    background-color: #0a0f1a;
    color: #e2e8f0;
    font-family: "Microsoft YaHei UI", "PingFang SC", "Segoe UI", sans-serif;
    font-size: 13px;
}

/* Scroll areas */
QScrollArea {
    border: none;
    background-color: transparent;
}

QScrollBar:vertical {
    background-color: transparent;
    width: 8px;
    border-radius: 4px;
}

QScrollBar::handle:vertical {
    background-color: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    min-height: 32px;
}

QScrollBar::handle:vertical:hover {
    background-color: rgba(255, 255, 255, 0.20);
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 8px;
    border-radius: 4px;
}

QScrollBar::handle:horizontal {
    background-color: rgba(255, 255, 255, 0.12);
    border-radius: 4px;
    min-width: 32px;
}

QScrollBar::handle:horizontal:hover {
    background-color: rgba(255, 255, 255, 0.20);
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
}

/* Panels */
QFrame#panel {
    background-color: rgba(30, 41, 59, 0.80);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 16px;
}

QFrame#groupCard {
    background-color: rgba(30, 41, 59, 0.70);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}

QFrame#groupCardVideo {
    background-color: rgba(30, 41, 59, 0.70);
    border: 1px solid rgba(168, 85, 247, 0.25);
    border-radius: 12px;
}

QFrame#resultItem {
    background-color: rgba(15, 23, 42, 0.60);
    border: 2px solid transparent;
    border-radius: 8px;
}

QFrame#resultItem:hover {
    border: 2px solid #3b82f6;
    background-color: rgba(15, 23, 42, 0.80);
}

QFrame#resultItem[selected="true"] {
    border: 2px solid #ef4444;
    background-color: rgba(239, 68, 68, 0.10);
}

QFrame#resultItemVideo:hover {
    border: 2px solid #a855f7;
    background-color: rgba(15, 23, 42, 0.80);
}

QFrame#folderItem {
    background-color: rgba(15, 23, 42, 0.50);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
}

/* Labels */
QLabel {
    color: #e2e8f0;
    background-color: transparent;
}

QLabel#title {
    font-size: 16px;
    font-weight: bold;
    color: #e2e8f0;
}

QLabel#sectionTitle {
    font-size: 15px;
    font-weight: bold;
    color: #e2e8f0;
}

QLabel#labelMuted {
    color: #94a3b8;
    font-size: 12px;
}

QLabel#versionLabel {
    color: #64748b;
    font-size: 11px;
    padding: 2px 8px;
}

QLabel#stageBadge {
    background-color: rgba(59, 130, 246, 0.15);
    color: #60a5fa;
    border: 1px solid rgba(59, 130, 246, 0.30);
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
}

QLabel#stageBadgeCompleted {
    background-color: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.30);
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
}

QLabel#stageBadgeError {
    background-color: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.30);
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
}

QLabel#stageBadgeStopped {
    background-color: rgba(245, 158, 11, 0.15);
    color: #f59e0b;
    border: 1px solid rgba(245, 158, 11, 0.30);
    border-radius: 12px;
    padding: 4px 12px;
    font-size: 12px;
}

QLabel#typeBadgeImage {
    background-color: rgba(59, 130, 246, 0.20);
    color: #60a5fa;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: bold;
}

QLabel#typeBadgeVideo {
    background-color: rgba(168, 85, 247, 0.20);
    color: #c084fc;
    border-radius: 6px;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: bold;
}

QLabel#videoIndicator {
    background-color: rgba(168, 85, 247, 0.85);
    color: white;
    border-radius: 4px;
    padding: 2px 6px;
    font-size: 10px;
    font-weight: bold;
}

QLabel#statusOk {
    color: #22c55e;
}

QLabel#statusError {
    color: #ef4444;
}

QLabel#filename {
    font-weight: 500;
    color: #e2e8f0;
}

QLabel#meta {
    color: #94a3b8;
    font-size: 11px;
}

/* Buttons */
QPushButton {
    background-color: #475569;
    color: white;
    border: none;
    border-radius: 8px;
    padding: 8px 16px;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #334155;
}

QPushButton:pressed {
    background-color: #1e293b;
    padding-top: 9px;
    padding-bottom: 7px;
}

QPushButton:disabled {
    background-color: #334155;
    color: #64748b;
}

QPushButton#primary {
    background-color: #3b82f6;
}

QPushButton#primary:hover {
    background-color: #2563eb;
}

QPushButton#primary:pressed {
    background-color: #1d4ed8;
    padding-top: 9px;
    padding-bottom: 7px;
}

QPushButton#danger {
    background-color: #ef4444;
}

QPushButton#danger:hover {
    background-color: #dc2626;
}

QPushButton#danger:pressed {
    background-color: #b91c1c;
    padding-top: 9px;
    padding-bottom: 7px;
}

QPushButton#secondary {
    background-color: #475569;
}

QPushButton#secondary:pressed {
    background-color: #1e293b;
    padding-top: 9px;
    padding-bottom: 7px;
}

QPushButton#preset {
    background-color: rgba(15, 23, 42, 0.50);
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 6px 12px;
}

QPushButton#preset:hover {
    background-color: rgba(15, 23, 42, 0.80);
    color: #e2e8f0;
}

QPushButton#preset:pressed {
    background-color: rgba(15, 23, 42, 1.00);
    padding-top: 7px;
    padding-bottom: 5px;
}

QPushButton#preset:checked {
    background-color: #3b82f6;
    color: white;
    border-color: #3b82f6;
}

QPushButton#preset:checked:pressed {
    background-color: #1d4ed8;
}

QPushButton#presetVideo:checked {
    background-color: #a855f7;
    color: white;
    border-color: #a855f7;
}

QPushButton#presetVideo:checked:pressed {
    background-color: #7e22ce;
}

QPushButton#small {
    padding: 6px 12px;
    font-size: 12px;
}

QPushButton#iconButton {
    background-color: transparent;
    color: #ef4444;
    font-size: 16px;
    padding: 2px 6px;
    border-radius: 4px;
}

QPushButton#iconButton:hover {
    background-color: rgba(239, 68, 68, 0.10);
}

QPushButton#iconButton:pressed {
    background-color: rgba(239, 68, 68, 0.20);
    padding-top: 3px;
    padding-bottom: 1px;
}

QPushButton#navButton {
    background-color: rgba(255, 255, 255, 0.08);
    color: #e2e8f0;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 22px;
    min-width: 44px;
    min-height: 44px;
    font-size: 18px;
}

QPushButton#navButton:hover {
    background-color: rgba(255, 255, 255, 0.18);
}

QPushButton#navButton:pressed {
    background-color: rgba(255, 255, 255, 0.25);
    padding-top: 9px;
    padding-bottom: 7px;
}

QPushButton#navButton:disabled {
    background-color: rgba(255, 255, 255, 0.04);
    color: #64748b;
}

/* Slider */
QSlider {
    background-color: transparent;
}

QSlider::groove:horizontal {
    height: 6px;
    background-color: rgba(255, 255, 255, 0.10);
    border-radius: 3px;
}

QSlider::handle:horizontal {
    background-color: #3b82f6;
    width: 18px;
    height: 18px;
    border-radius: 9px;
    margin: -6px 0;
    border: 2px solid #0a0f1a;
}

QSlider::handle:horizontal:hover {
    background-color: #60a5fa;
    width: 20px;
    height: 20px;
    border-radius: 10px;
    margin: -7px 0;
}

QSlider::sub-page:horizontal {
    background-color: #3b82f6;
    border-radius: 3px;
}

QSlider#videoSlider::handle:horizontal {
    background-color: #a855f7;
}

QSlider#videoSlider::handle:horizontal:hover {
    background-color: #c084fc;
}

QSlider#videoSlider::sub-page:horizontal {
    background-color: #a855f7;
}

/* Inputs */
QComboBox {
    background-color: rgba(15, 23, 42, 0.60);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 12px;
    color: #e2e8f0;
    min-width: 120px;
}

QComboBox:hover, QComboBox:focus {
    border-color: #3b82f6;
}

QComboBox::drop-down {
    border: none;
    width: 24px;
}

QComboBox QAbstractItemView {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid rgba(255, 255, 255, 0.08);
    selection-background-color: #3b82f6;
}

QCheckBox {
    color: #e2e8f0;
    spacing: 8px;
    background-color: transparent;
}

QCheckBox::indicator {
    width: 18px;
    height: 18px;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.20);
    background-color: rgba(15, 23, 42, 0.60);
}

QCheckBox::indicator:checked {
    background-color: #3b82f6;
    border-color: #3b82f6;
    image: url(data:image/svg+xml;base64,PD94bWwgdmVyc2lvbj0iMS4wIiBlbmNvZGluZz0iVVRGLTgiPz48c3ZnIHdpZHRoPSIxMiIgaGVpZ2h0PSIxMiIgdmlld0JveD0iMCAwIDEyIDEyIiB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciPjxwYXRoIGQ9Ik0yIDYgTDUgOSBMMTAgMyIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBmaWxsPSJub25lIiBzdHJva2UtbGluZWNhcD0icm91bmQiIHN0cm9rZS1saW5lam9pbj0icm91bmQiLz48L3N2Zz4=);
}

/* Progress bar */
QProgressBar {
    background-color: rgba(255, 255, 255, 0.05);
    border-radius: 10px;
    height: 20px;
    text-align: center;
    color: #e2e8f0;
    font-size: 11px;
}

QProgressBar::chunk {
    background-color: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #3b82f6, stop:1 #60a5fa);
    border-radius: 10px;
}

/* Tab widget */
QTabWidget::pane {
    border: none;
    background-color: transparent;
}

QTabBar::tab {
    background-color: transparent;
    color: #94a3b8;
    border: none;
    border-bottom: 3px solid transparent;
    padding: 10px 24px;
    font-weight: 500;
}

QTabBar::tab:hover {
    color: #e2e8f0;
}

QTabBar::tab:selected {
    color: #3b82f6;
    border-bottom-color: #3b82f6;
}

/* Splitter */
QSplitter::handle:horizontal {
    background-color: rgba(255, 255, 255, 0.06);
    width: 2px;
    margin: 8px 0;
    border-radius: 1px;
}

QSplitter::handle:horizontal:hover {
    background-color: #3b82f6;
}

/* Dialogs */
QDialog {
    background-color: #0f172a;
}

QMessageBox {
    background-color: #0f172a;
}

QMessageBox QLabel {
    color: #e2e8f0;
}

QMessageBox QPushButton {
    min-width: 80px;
}

/* Line edit */
QLineEdit {
    background-color: rgba(15, 23, 42, 0.60);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 8px 12px;
    color: #e2e8f0;
}

QLineEdit:focus {
    border-color: #3b82f6;
}

/* Tooltip */
QToolTip {
    background-color: #1e293b;
    color: #e2e8f0;
    border: 1px solid rgba(255, 255, 255, 0.10);
    border-radius: 6px;
    padding: 6px 10px;
}

QFrame#previewImageContainer {
    background-color: rgba(0, 0, 0, 0.30);
    border-radius: 12px;
}

QFrame#videoSettings {
    background-color: rgba(15, 23, 42, 0.40);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}
"""
