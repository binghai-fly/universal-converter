import sys
from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFileDialog, QComboBox, QListWidget, QMessageBox, QProgressBar
)

from converters import convert


class Worker(QThread):
    done = Signal(str)
    failed = Signal(str)

    def __init__(self, src, dst):
        super().__init__()
        self.src, self.dst = src, dst

    def run(self):
        try:
            convert(Path(self.src), Path(self.dst))
            self.done.emit(str(self.dst))
        except Exception as e:
            self.failed.emit(str(e))


class App(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Universal Converter")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        title = QLabel("Universal Converter")
        title.setStyleSheet("font-size: 24px; font-weight: bold;")
        layout.addWidget(title)

        self.files = QListWidget()
        layout.addWidget(QLabel("待转换文件："))
        layout.addWidget(self.files)

        row = QHBoxLayout()
        add = QPushButton("添加文件")
        add.clicked.connect(self.add_files)
        clear = QPushButton("清空")
        clear.clicked.connect(self.files.clear)
        row.addWidget(add)
        row.addWidget(clear)
        layout.addLayout(row)

        outrow = QHBoxLayout()
        outrow.addWidget(QLabel("目标格式："))
        self.format = QComboBox()
        self.format.addItems([
            "txt", "md", "csv", "json", "yaml", "xml",
            "png", "jpg", "webp", "bmp", "tiff", "pdf",
            "docx", "xlsx", "pptx", "mp3", "wav", "flac",
            "mp4", "mkv", "avi", "mov", "webm", "zip"
        ])
        outrow.addWidget(self.format)
        layout.addLayout(outrow)

        self.progress = QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.hide()
        layout.addWidget(self.progress)

        self.convert_btn = QPushButton("开始转换")
        self.convert_btn.clicked.connect(self.start)
        layout.addWidget(self.convert_btn)

        self.status = QLabel("请选择文件并选择目标格式。")
        layout.addWidget(self.status)

    def add_files(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "选择文件")
        for p in paths:
            if not any(self.files.item(i).text() == p for i in range(self.files.count())):
                self.files.addItem(p)

    def start(self):
        if self.files.count() == 0:
            QMessageBox.warning(self, "提示", "请先添加文件。")
            return

        target = self.format.currentText()
        outdir = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if not outdir:
            return

        self.convert_btn.setEnabled(False)
        self.progress.show()
        self._remaining = self.files.count()
        self._errors = []

        for i in range(self.files.count()):
            src = Path(self.files.item(i).text())
            dst = Path(outdir) / f"{src.stem}.{target}"
            worker = Worker(src, dst)
            worker.done.connect(self.one_done)
            worker.failed.connect(self.one_failed)
            worker.finished.connect(worker.deleteLater)
            worker.start()
            if not hasattr(self, "_workers"):
                self._workers = []
            self._workers.append(worker)

    def one_done(self, path):
        self._remaining -= 1
        self.status.setText(f"已完成：{path}")
        self.finish_if_ready()

    def one_failed(self, err):
        self._remaining -= 1
        self._errors.append(err)
        self.finish_if_ready()

    def finish_if_ready(self):
        if self._remaining > 0:
            return
        self.progress.hide()
        self.convert_btn.setEnabled(True)
        if self._errors:
            QMessageBox.warning(self, "部分失败", "\n\n".join(self._errors))
        else:
            QMessageBox.information(self, "完成", "全部文件转换完成。")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = App()
    w.show()
    sys.exit(app.exec())
