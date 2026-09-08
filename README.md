# Universal Converter

一个面向 Windows / macOS / Linux 的桌面跨格式转换器。目标是用一个统一界面覆盖常见的**文本/数据、图片、PDF、Office、音视频和压缩包**转换场景。

## 已支持

- **文本/数据**：TXT、MD、CSV、JSON、YAML、XML
- **图片**：PNG、JPG/JPEG、WEBP、BMP、TIFF/TIF、GIF
- **PDF**：常见图片 → PDF、PDF 首页 → 图片
- **Office**：DOC/DOCX、XLS/XLSX、PPT/PPTX、ODT/ODS/ODP、RTF（依赖 LibreOffice）
- **音视频**：MP3、WAV、FLAC、AAC、OGG、M4A、OPUS、MP4、MKV、AVI、MOV、WEBM、MPEG、MPG、M4V（依赖 FFmpeg）
- **压缩包**：ZIP、TAR、TAR.GZ/TGZ、TAR.BZ2、TAR.XZ

> “市面上大部分格式”不代表所有格式都能无损互转。Office 和音视频格式由 LibreOffice / FFmpeg 提供能力，复杂 PDF、受 DRM 保护的媒体、专业设计文件等仍可能需要专用软件。

## 2.0 改进

- 支持**拖拽添加文件**
- 支持批量转换，并改为**单任务队列**，减少并发转换导致的 CPU/RAM 峰值
- 自动避免覆盖已有输出文件，例如 `photo (1).jpg`
- 增加 XML 输出和 ZIP/TAR 系列互转
- 增强错误提示、超时保护和输入/输出相同文件检查
- GitHub Actions 自动运行测试

## 安装

```bash
python -m venv .venv
```

Windows：

```bash
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

macOS / Linux：

```bash
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

### 外部依赖

- **LibreOffice**：Office 格式互转需要，并将 `soffice` 加入 PATH。
- **FFmpeg**：音视频转换需要，并将 `ffmpeg` 加入 PATH。

## Windows EXE

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name UniversalConverter app.py
```

## 项目结构

```text
universal-converter/
├─ app.py
├─ converters/
│  ├─ __init__.py
│  └─ core.py
├─ tests/
│  └─ test_core.py
├─ .github/workflows/test.yml
├─ requirements.txt
└─ README.md
```

## 后续路线

1. Windows 一键安装包 / EXE
2. 自动检测输入格式并推荐可用目标格式
3. PDF 多页批量图片导出
4. Office → PDF 的专用预览和错误诊断
5. 转换历史、日志和取消任务
6. 插件式 converter adapter，方便加入 CAD、电子书等专业格式
