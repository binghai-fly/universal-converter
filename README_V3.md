# Universal Converter 3.0

Universal Converter 是一个面向 Windows / macOS / Linux 的桌面跨格式转换器。

## 3.0

- 拖拽导入文件
- 批量转换与并发任务
- 转换历史和错误信息
- 自动避免覆盖已有输出文件
- 文本/数据：TXT、MD、CSV、JSON、YAML、XML
- 图片：PNG、JPG/JPEG、WEBP、BMP、TIFF、GIF
- PDF / Office：PDF、DOC/DOCX、XLS/XLSX、PPT/PPTX、ODT/ODS/ODP、RTF
- 音视频：MP3、WAV、FLAC、AAC、OGG、M4A、OPUS、MP4、MKV、AVI、MOV、WEBM、MPEG、MPG、M4V
- 压缩包：ZIP、TAR、TGZ、TAR.GZ、TAR.BZ2、TAR.XZ

## 外部依赖

Office 转换使用 LibreOffice 的 headless 模式；音视频转换使用 FFmpeg。两者都需要安装并加入 PATH。

## Windows

双击 `build_windows.bat` 可构建 Windows 桌面程序。生成文件位于 `dist/UniversalConverter/UniversalConverter.exe`。

运行 3.0：

```bash
pip install -r requirements-v3.txt
python app_v3.py
```
