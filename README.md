# Universal Converter

一个面向 Windows / macOS / Linux 的桌面跨格式转换器。目标是用一个统一界面覆盖常见的**文本/数据、图片、PDF、Office、音视频和压缩包**转换场景。

## 已支持

- **文本/数据**：TXT、MD、CSV、JSON、YAML、XML
- **图片**：PNG、JPG/JPEG、WEBP、BMP、TIFF/TIF、GIF
- **PDF**：图片 → PDF、PDF 首页 → 图片、**PDF → 可编辑 DOCX**
- **PDF → DOCX**：重点功能。对文字型 PDF 提取文字块、字体大小/样式、图片，并尝试识别 PDF 表格为可编辑 Word 表格；每个 PDF 页面独立对应 Word 页面，尽量保留原始页面尺寸和版式。
- **Office**：DOC/DOCX、XLS/XLSX、PPT/PPTX、ODT/ODS/ODP、RTF（依赖 LibreOffice）
- **音视频**：MP3、WAV、FLAC、AAC、OGG、M4A、OPUS、MP4、MKV、AVI、MOV、WEBM、MPEG、MPG、M4V（依赖 FFmpeg）
- **压缩包**：ZIP、TAR、TAR.GZ/TGZ、TAR.BZ2、TAR.XZ

> PDF → DOCX 是“可编辑重建”，不是简单把 PDF 页面截图塞进 Word。复杂排版、特殊字体、浮动对象和扫描件仍可能与原 PDF 存在差异。扫描 PDF 的 OCR 计划在后续版本加入。

## PDF → DOCX 设计

转换器会优先使用 PyMuPDF 分析 PDF：

1. 读取每一页的文字块和字体信息
2. 保留文字大小、粗体、斜体和水平位置
3. 提取 PDF 内嵌图片并写入 DOCX
4. 尝试识别 PDF 表格并生成真正可编辑的 Word 表格
5. 按 PDF 页面尺寸创建 Word 页面并分页
6. 对没有可提取文字的页面保留页面视觉内容，避免内容直接丢失

当前版本重点优化**文字型 PDF**；扫描件 OCR 不属于当前版本的承诺能力。

## Windows Office 依赖自动化

Windows 版会自动检测 LibreOffice，不要求用户手动把 `soffice` 加入 PATH。

如果未安装 LibreOffice，程序提供重新检测、WinGet 自动安装和官方安装页入口。安装过程在后台线程执行，避免冻结界面。

### 注意

自动安装需要 Windows 的 **WinGet / App Installer**。程序不会把 LibreOffice 二进制文件打进 EXE。首次安装仍需要网络连接，并可能受到 Windows 管理员策略限制。

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

- **python-docx**：生成可编辑 DOCX，PDF → DOCX 核心依赖。
- **PyMuPDF**：PDF 解析、文字/图片/表格提取。
- **LibreOffice**：其他 Office 格式互转需要。Windows 版会自动检测并可通过 WinGet 一键安装。
- **FFmpeg**：音视频转换需要，并将 `ffmpeg` 加入 PATH。

## Windows EXE

```bash
pip install pyinstaller
pyinstaller --noconfirm --windowed --name UniversalConverter app_v3.py
```

项目的 GitHub Actions 会在 `v*.*.*` Tag 上自动构建 Windows x64 ZIP 并发布 GitHub Release。

## 测试

CI 包含 PDF → DOCX 回归测试，验证生成的 DOCX 可以被 `python-docx` 打开，并且 PDF 中的文字能够作为可编辑文本读取。

## 项目结构

```text
universal-converter/
├─ app.py
├─ app_v3.py
├─ converters/
│  ├─ __init__.py
│  ├─ core.py
│  └─ dependencies.py
├─ tests/
│  └─ test_core.py
├─ .github/workflows/test.yml
├─ .github/workflows/release.yml
├─ requirements.txt
└─ README.md
```

## 后续路线

1. **PDF → DOCX 版式继续优化**：段落间距、表格位置、页眉页脚、字体映射
2. 扫描 PDF OCR → DOCX
3. PDF 多页图片导出
4. Office → PDF 的专用预览和错误诊断
5. 转换历史、日志和取消任务
6. 自动检测输入格式并推荐目标格式
7. 插件式 converter adapter，方便加入 CAD、电子书等专业格式
8. iPhone + Android 本地转换 App
