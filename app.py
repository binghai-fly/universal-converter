from __future__ import annotations

import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QFileDialog, QComboBox, QHBoxLayout, QLabel, QListWidget,
    QListWidgetItem, QMessageBox, QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from converters import convert

FORMATS = [
    "txt", "md", "csv", "json", "yaml", "xml",
    "png", "jpg", "jpeg", "webp", "bmp", "tiff", "gif", "pdf",
    "doc", "docx", "xls", "xlsx", "ppt", "pptx", "odt", "ods", "odp", "rtf",
    "mp3", "wav", "flac", "aac", "ogg", "m4a", "opus",
    "mp4", "mkv", "avi", "mov", "webm", "mpeg", "mpg", "m4v",
    "zip", "tar", "tar.gz", "tgz", "tar.bz2", "tar.xz",
]


class DropList(QListWidget):
    files_dropped = Signal(list)

    def __init__(self):
        super().__init__()
        self.setAcceptDrops(True)
        self.setSelectionMode(QListWidget.ExtendedSelection)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        paths = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        self.files_dropped.emit(paths)
        event.acceptProposedAction()


class Worker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, src: Path, dst: Path):
        super().__init__()
        self.src, self.dst = src, dst

    def run(self):
        try:
            convert(self.src, self.dst)
            self.done.emit(str(self.dst))
        except Exception as exc:
            self.failed.emit(f"{self.src.name}: {exc}")


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Converter 2.0")
        self.resize(820, 600)
        self._workers = []
        self._queue = []
        self._total = 0
        self._completed = 0
        self._errors = []
        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        title = QLabel("Universal Converter 2.0")
        title.setStyleSheet("font-size: 25px; font-weight: bold;")
        layout.addWidget(title)
        layout.addWidget(QLabel("支持拖拽文件，也可以点击“添加文件”。批量转换时会逐个处理，避免占满系统资源。"))

        self.files = DropList()
        self.files.files_dropped.connect(self.add_paths)
        layout.addWidget(QLabel("待转换文件："))
        layout.addWidget(self.files)

        row = QHBoxLayout()
        add = QPushButton("添加文件")
        add.clicked.connect(self.add_files)
        remove = QPushButton("移除选中")
        remove.clicked.connect(self.remove_selected)
        clear = QPushButton("清空")
        clear.clicked.connect(self.files.clear)
        row.addWidget(add)
        row.addWidget(remove)
        row.addWidget(clear)
        layout.addLayout(row)

        outrow = QHBoxLayout()
        outrow.addWidget(QLabel("目标格式："))
        self.format = QComboBox()
        self.format.addItems(FORMATS)
        self.format.setCurrentText("pdf")
        outrow.addWidget(self.format)
        layout.addLayout(outrow)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        self.convert_btn = QPushButton("开始批量转换")
        self.convert_btn.clicked.connect(self.start)
        layout.addWidget(self.convert_btn)

        self.status = QLabel("就绪。")
        layout.addWidget(self.status)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        self.add_paths(paths)

    def add_paths(self, paths):
        existing = {self.files.item(i).text() for i in range(self.files.count())}
        for path in paths:
            path = str(Path(path).resolve())
            if Path(path).is_file() and path not in existing:
                self.files.addItem(QListWidgetItem(path))
                existing.add(path)
        self.status.setText(f"已添加 {self.files.count()} 个文件。")

    def remove_selected(self):
        for item in self.files.selectedItems():
            self.files.takeItem(self.files.row(item))

    def start(self):
        if self.files.count() == 0:
            QMessageBox.warning(self, "提示", "请先添加文件。")
            return
        outdir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not outdir:
            return

        target = "." + self.format.currentText().lower()
        self._queue = [(Path(self.files.item(i).text()), Path(outdir)) for i in range(self.files.count())]
        self._total = len(self._queue)
        self._completed = 0
        self._errors = []
        self.convert_btn.setEnabled(False)
        self.progress.setValue(0)
        self._run_next(target)

    def _run_next(self, target):
        if not self._queue:
            self._finish()
            return
        src, outdir = self._queue.pop(0)
        dst = outdir / f"{src.stem}{target}"
        if dst.exists():
            dst = self._unique_path(dst)
        self.status.setText(f"转换中：{src.name}")
        worker = Worker(src, dst)
        self._workers.append(worker)
        worker.done.connect(self.one_done)
        worker.failed.connect(self.one_failed)
        worker.finished.connect(lambda: self._run_next(target))
        worker.start()

    @staticmethod
    def _unique_path(path: Path) -> Path:
        n = 1
        candidate = path
        while candidate.exists():
            candidate = path.with_name(f"{path.stem} ({n}){path.suffix}")
            n += 1
        return candidate

    def one_done(self, path):
        self._completed += 1
        self.progress.setValue(int(self._completed * 100 / self._total))
        self.status.setText(f"已完成：{Path(path).name} ({self._completed}/{self._total})")

    def one_failed(self, error):
        self._completed += 1
        self._errors.append(error)
        self.progress.setValue(int(self._completed * 100 / self._total))
        self.status.setText(f"失败：{self._completed}/{self._total}")

    def _finish(self):
        self.convert_btn.setEnabled(True)
        if self._errors:
            QMessageBox.warning(self, "转换完成，但有失败项", "\n\n".join(self._errors))
            self.status.setText(f"完成：成功 {self._total - len(self._errors)}，失败 {len(self._errors)}。")
        else:
            QMessageBox.information(self, "完成", f"全部 {self._total} 个文件转换完成。")
            self.status.setText(f"完成：{self._total}/{self._total}。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Universal Converter")
    window = App()
    window.show()
    sys.exit(app.exec())
