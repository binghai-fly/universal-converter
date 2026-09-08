"""Universal Converter 3.0 - modern PySide6 desktop UI.

The original app.py is kept for compatibility. Run this file for the 3.0 UI.
"""
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QListWidget, QMessageBox, QProgressBar,
    QGroupBox, QCheckBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView
)

from converters import convert

FORMATS = [
    ("文本 / 数据", ["txt", "md", "csv", "json", "yaml", "xml"]),
    ("图片", ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"]),
    ("文档 / PDF", ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp"]),
    ("音频", ["mp3", "wav", "flac", "aac", "ogg", "m4a"]),
    ("视频", ["mp4", "mkv", "avi", "mov", "webm", "mpeg", "mpg"]),
    ("压缩包", ["zip", "tar", "tar.gz", "tgz", "tar.bz2", "tar.xz"]),
]
ALL_FORMATS = [x for _, xs in FORMATS for x in xs]


def suffix(path: Path) -> str:
    name = path.name.lower()
    for ext in sorted(ALL_FORMATS, key=len, reverse=True):
        if name.endswith("." + ext):
            return ext
    return path.suffix.lower().lstrip(".")


def make_output_path(src: Path, outdir: Path, target: str) -> Path:
    dst = outdir / f"{src.stem}.{target}"
    i = 1
    while dst.exists():
        dst = outdir / f"{src.stem} ({i}).{target}"
        i += 1
    return dst


class DropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.setMinimumHeight(180)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        paths = [u.toLocalFile() for u in event.mimeData().urls() if u.isLocalFile()]
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class Worker(QThread):
    item_done = Signal(int, str, str)
    all_done = Signal()

    def __init__(self, jobs):
        super().__init__()
        self.jobs = jobs
        self.cancelled = False

    def run(self):
        with ThreadPoolExecutor(max_workers=min(4, max(1, len(self.jobs)))) as pool:
            futures = {pool.submit(convert, src, dst): (i, src, dst)
                       for i, (src, dst) in enumerate(self.jobs)}
            for future in as_completed(futures):
                i, src, dst = futures[future]
                try:
                    future.result()
                    self.item_done.emit(i, "完成", str(dst))
                except Exception as exc:
                    self.item_done.emit(i, "失败", str(exc))
        self.all_done.emit()


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Converter 3.0")
        self.resize(920, 680)
        self.setAcceptDrops(True)
        self.worker = None
        self.jobs = []
        self.history = []
        self.build_ui()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Universal Converter 3.0")
        title.setObjectName("title")
        root.addWidget(title)
        sub = QLabel("批量转换 · 拖拽导入 · 自动避免覆盖 · 转换历史")
        sub.setObjectName("subtitle")
        root.addWidget(sub)

        box = QGroupBox("文件")
        bl = QVBoxLayout(box)
        self.files = DropList()
        self.files.files_dropped.connect(self.add_paths)
        self.files.setPlaceholderText("将文件拖到这里，或点击“添加文件”")
        bl.addWidget(self.files)
        buttons = QHBoxLayout()
        add = QPushButton("添加文件")
        add.clicked.connect(self.pick_files)
        remove = QPushButton("移除选中")
        remove.clicked.connect(self.remove_selected)
        clear = QPushButton("清空")
        clear.clicked.connect(self.files.clear)
        buttons.addWidget(add)
        buttons.addWidget(remove)
        buttons.addWidget(clear)
        buttons.addStretch()
        bl.addLayout(buttons)
        root.addWidget(box)

        options = QHBoxLayout()
        options.addWidget(QLabel("目标格式"))
        self.format = QComboBox()
        for group, xs in FORMATS:
            for ext in xs:
                self.format.addItem(f"{ext.upper()}  ·  {group}", ext)
        options.addWidget(self.format, 1)
        self.same_ext = QCheckBox("允许同格式复制")
        self.same_ext.setChecked(False)
        options.addWidget(self.same_ext)
        root.addLayout(options)

        out = QHBoxLayout()
        self.output_label = QLabel("输出目录：未选择")
        out.addWidget(self.output_label, 1)
        choose = QPushButton("选择输出目录")
        choose.clicked.connect(self.pick_output)
        out.addWidget(choose)
        root.addLayout(out)
        self.output_dir = None

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        root.addWidget(self.progress)

        self.status = QLabel("准备就绪")
        root.addWidget(self.status)
        self.start_btn = QPushButton("开始转换")
        self.start_btn.clicked.connect(self.start)
        root.addWidget(self.start_btn)

        hist_box = QGroupBox("本次会话历史")
        hl = QVBoxLayout(hist_box)
        self.history_table = QTableWidget(0, 3)
        self.history_table.setHorizontalHeaderLabels(["状态", "文件", "输出 / 错误"])
        self.history_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.history_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.history_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.history_table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        hl.addWidget(self.history_table)
        root.addWidget(hist_box)

    def pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        self.add_paths(paths)

    def add_paths(self, paths):
        existing = {self.files.item(i).text() for i in range(self.files.count())}
        for p in paths:
            if p and Path(p).is_file() and p not in existing:
                self.files.addItem(p)
                existing.add(p)
        self.status.setText(f"已添加 {self.files.count()} 个文件")

    def remove_selected(self):
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))

    def pick_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir = Path(path)
            self.output_label.setText(f"输出目录：{self.output_dir}")

    def start(self):
        if self.files.count() == 0:
            QMessageBox.warning(self, "提示", "请先添加文件。")
            return
        if not self.output_dir:
            self.pick_output()
            if not self.output_dir:
                return

        target = self.format.currentData()
        jobs = []
        for i in range(self.files.count()):
            src = Path(self.files.item(i).text())
            if suffix(src) == target and not self.same_ext.isChecked():
                self.add_history("跳过", src.name, "输入和输出格式相同")
                continue
            jobs.append((src, make_output_path(src, self.output_dir, target)))

        if not jobs:
            self.status.setText("没有可转换的文件")
            return
        self.jobs = jobs
        self.history_table.setRowCount(0)
        self.progress.setValue(0)
        self.start_btn.setEnabled(False)
        self.status.setText(f"正在转换 {len(jobs)} 个文件…")
        self.worker = Worker(jobs)
        self.worker.item_done.connect(self.item_done)
        self.worker.all_done.connect(self.all_done)
        self.worker.start()

    def add_history(self, status, name, detail):
        row = self.history_table.rowCount()
        self.history_table.insertRow(row)
        for col, text in enumerate((status, name, detail)):
            self.history_table.setItem(row, col, QTableWidgetItem(text))

    def item_done(self, index, status, detail):
        src = self.jobs[index][0]
        self.add_history(status, src.name, detail)
        done = self.history_table.rowCount()
        total = len(self.jobs)
        self.progress.setValue(min(100, int(done / total * 100)))

    def all_done(self):
        self.start_btn.setEnabled(True)
        self.progress.setValue(100)
        failed = sum(1 for r in range(self.history_table.rowCount())
                     if self.history_table.item(r, 0).text() == "失败")
        self.status.setText(f"完成：{len(self.jobs) - failed} 成功，{failed} 失败")
        if failed:
            QMessageBox.warning(self, "转换完成", self.status.text())
        else:
            QMessageBox.information(self, "转换完成", self.status.text())

    def closeEvent(self, event):
        if self.worker and self.worker.isRunning():
            QMessageBox.warning(self, "正在转换", "请等待当前任务完成后再退出。")
            event.ignore()
            return
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Universal Converter")
    w = App()
    w.show()
    sys.exit(app.exec())
