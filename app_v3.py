"""Universal Converter 3.0 - modern PySide6 desktop UI.

The original app.py is kept for compatibility. Run this file for the 3.0 UI.
"""
import sys
import webbrowser
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
from converters.dependencies import (
    LIBREOFFICE_DOWNLOAD_URL,
    find_soffice,
    install_libreoffice_windows,
)

FORMATS = [
    ("文本 / 数据", ["txt", "md", "csv", "json", "yaml", "xml"]),
    ("图片", ["png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif"]),
    ("文档 / PDF", ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "rtf"]),
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
        self._placeholder = "将文件拖到这里，或点击“添加文件”"
        self._update_placeholder()

    def _update_placeholder(self):
        if self.count() == 0:
            self.addItem(self._placeholder)
            item = self.item(0)
            item.setFlags(Qt.NoItemFlags)
        elif self.count() == 1 and self.item(0).text() == self._placeholder:
            self.takeItem(0)

    def add_file(self, path: str):
        self._update_placeholder()
        self.addItem(path)

    def remove_selected_files(self):
        for item in self.selectedItems():
            self.takeItem(self.row(item))
        self._update_placeholder()

    def clear_files(self):
        super().clear()
        self._update_placeholder()

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


class OfficeInstallWorker(QThread):
    finished = Signal(bool, str)

    def run(self):
        ok, message = install_libreoffice_windows()
        self.finished.emit(ok, message)


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Converter 3.0")
        self.resize(920, 740)
        self.setAcceptDrops(True)
        self.worker = None
        self.office_worker = None
        self.jobs = []
        self.build_ui()
        self.refresh_office_status()

    def build_ui(self):
        root = QVBoxLayout(self)
        title = QLabel("Universal Converter 3.0")
        title.setObjectName("title")
        root.addWidget(title)
        sub = QLabel("批量转换 · 拖拽导入 · 自动避免覆盖 · 转换历史")
        sub.setObjectName("subtitle")
        root.addWidget(sub)

        office_box = QGroupBox("Office 依赖")
        office_layout = QHBoxLayout(office_box)
        self.office_status = QLabel("正在检测 LibreOffice…")
        office_layout.addWidget(self.office_status, 1)
        check_office = QPushButton("重新检测")
        check_office.clicked.connect(self.refresh_office_status)
        office_layout.addWidget(check_office)
        self.install_office_btn = QPushButton("自动安装 LibreOffice")
        self.install_office_btn.clicked.connect(self.install_office)
        office_layout.addWidget(self.install_office_btn)
        manual_office = QPushButton("官方安装页")
        manual_office.clicked.connect(lambda: webbrowser.open(LIBREOFFICE_DOWNLOAD_URL))
        office_layout.addWidget(manual_office)
        root.addWidget(office_box)

        box = QGroupBox("文件")
        bl = QVBoxLayout(box)
        self.files = DropList()
        self.files.files_dropped.connect(self.add_paths)
        bl.addWidget(self.files)
        buttons = QHBoxLayout()
        add = QPushButton("添加文件")
        add.clicked.connect(self.pick_files)
        remove = QPushButton("移除选中")
        remove.clicked.connect(self.remove_selected)
        clear = QPushButton("清空")
        clear.clicked.connect(self.files.clear_files)
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

    def refresh_office_status(self):
        path = find_soffice()
        if path:
            self.office_status.setText(f"✓ LibreOffice 已就绪：{path}")
            self.install_office_btn.setEnabled(False)
        else:
            self.office_status.setText("⚠ 未检测到 LibreOffice；Office 转换不可用")
            self.install_office_btn.setEnabled(True)

    def install_office(self):
        if sys.platform != "win32":
            QMessageBox.information(self, "Windows 功能", "自动安装目前只针对 Windows。你可以使用“官方安装页”手动安装。")
            return
        answer = QMessageBox.question(
            self,
            "自动安装 LibreOffice",
            "程序将调用 Windows WinGet 安装 LibreOffice。是否继续？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes,
        )
        if answer != QMessageBox.Yes:
            return
        self.install_office_btn.setEnabled(False)
        self.status.setText("正在安装 LibreOffice，请稍候…")
        self.office_worker = OfficeInstallWorker()
        self.office_worker.finished.connect(self.office_install_done)
        self.office_worker.start()

    def office_install_done(self, ok, message):
        self.refresh_office_status()
        if ok:
            self.status.setText("LibreOffice 已安装，可以进行 Office 转换。")
            QMessageBox.information(self, "安装完成", message)
        else:
            self.status.setText("LibreOffice 自动安装未完成。")
            QMessageBox.warning(
                self,
                "安装未完成",
                f"{message}\n\n你也可以点击“官方安装页”手动安装 LibreOffice。",
            )

    def pick_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        self.add_paths(paths)

    def add_paths(self, paths):
        existing = {self.files.item(i).text() for i in range(self.files.count()) if self.files.item(i).flags() != Qt.NoItemFlags}
        for p in paths:
            if p and Path(p).is_file() and p not in existing:
                self.files.add_file(p)
                existing.add(p)
        count = sum(1 for i in range(self.files.count()) if self.files.item(i).flags() != Qt.NoItemFlags)
        self.status.setText(f"已添加 {count} 个文件")

    def remove_selected(self):
        self.files.remove_selected_files()

    def pick_output(self):
        path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if path:
            self.output_dir = Path(path)
            self.output_label.setText(f"输出目录：{self.output_dir}")

    def start(self):
        file_items = [self.files.item(i).text() for i in range(self.files.count()) if self.files.item(i).flags() != Qt.NoItemFlags]
        if not file_items:
            QMessageBox.warning(self, "提示", "请先添加文件。")
            return
        if not self.output_dir:
            self.pick_output()
            if not self.output_dir:
                return

        target = self.format.currentData()
        jobs = []
        for path in file_items:
            src = Path(path)
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
        if self.office_worker and self.office_worker.isRunning():
            QMessageBox.warning(self, "正在安装", "请等待 LibreOffice 安装完成后再退出。")
            event.ignore()
            return
        event.accept()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Universal Converter")
    w = App()
    w.show()
    sys.exit(app.exec())
