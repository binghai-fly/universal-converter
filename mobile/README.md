# Universal Converter Mobile

跨平台手机端（iPhone/iPad + Android）的本地优先转换器。

## 当前 MVP

- 多文件选择
- 本地图片转换：PNG / JPG / WEBP* / BMP / GIF
- 本地文本/数据转换：TXT / MD / JSON / CSV / YAML / XML（常见结构）
- 单文件 ZIP 打包
- 转换进度与历史
- 系统分享
- 不上传用户文件

> `WEBP` 编码目前使用兼容性优先策略，后续会替换为真正的 WebP 编码器。

## 开发环境

需要 Flutter stable、Android SDK 和 Xcode（iOS 构建需要 macOS）。

```bash
flutter pub get
flutter run
```

仓库中的 `mobile` 是 Flutter 源码层。Android/iOS 平台目录可用 `flutter create --platforms=android,ios .` 在该目录生成，然后执行 `flutter pub get`。

## 本地转换原则

文件只在设备本地处理，不需要登录或服务器。后续版本会增加原生 PDF、音频、视频和 Office 转换适配器；这些能力必须使用移动端可用的本地原生库，不能简单复用 Windows 的 LibreOffice/FFmpeg 可执行文件。
