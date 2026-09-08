# Universal Converter

一个跨格式的桌面文件转换器（Windows / macOS / Linux），采用 Python + PySide6。

## 当前支持

- 文本/数据：TXT、MD、CSV、JSON、YAML、XML
- 图片：PNG、JPG/JPEG、WEBP、BMP、TIFF、GIF（通过 Pillow）
- PDF：图片 → PDF、PDF → 图片（通过 PyMuPDF）
- Office：DOCX、XLSX、PPTX、ODT、ODS、ODP 等（通过 LibreOffice）
- 音视频：MP3、WAV、FLAC、AAC、MP4、MKV、AVI、MOV、WEBM 等（通过 FFmpeg）
- 压缩包：ZIP、TAR、GZ、BZ2、XZ（Python 标准库）

> “大部分格式”无法由一个纯 Python 库覆盖。项目采用适配器架构：内置处理常见格式，并自动调用 LibreOffice / FFmpeg 扩展 Office 和媒体格式。

## 运行

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

可选依赖：
- Windows 安装 FFmpeg 并加入 PATH
- 安装 LibreOffice 并加入 PATH

## 打包 Windows EXE

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name UniversalConverter app.py
```

## 设计

转换器先识别输入扩展名，再根据目标扩展名选择 converter adapter。未知格式不会静默损坏文件，而是给出明确错误。
