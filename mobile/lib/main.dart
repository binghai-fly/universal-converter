import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:archive/archive.dart';
import 'package:csv/csv.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:image/image.dart' as img;
import 'package:path/path.dart' as p;
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';
import 'package:xml/xml.dart';
import 'package:yaml/yaml.dart';

void main() => runApp(const UniversalConverterApp());

class UniversalConverterApp extends StatelessWidget {
  const UniversalConverterApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Universal Converter',
      theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
      home: const ConverterHome(),
    );
  }
}

class ConverterHome extends StatefulWidget {
  const ConverterHome({super.key});

  @override
  State<ConverterHome> createState() => _ConverterHomeState();
}

class _ConverterHomeState extends State<ConverterHome> {
  final List<PlatformFile> _files = [];
  final List<String> _history = [];
  String _target = 'PNG';
  bool _busy = false;
  double _progress = 0;

  static const imageTargets = ['PNG', 'JPG', 'WEBP', 'BMP', 'GIF'];
  static const textTargets = ['TXT', 'MD', 'JSON', 'CSV', 'YAML', 'XML'];

  Future<void> _pickFiles() async {
    final result = await FilePicker.platform.pickFiles(allowMultiple: true, withData: false);
    if (result == null) return;
    setState(() => _files.addAll(result.files));
  }

  Future<Directory> _outputDir() async {
    final dir = await getApplicationDocumentsDirectory();
    final out = Directory(p.join(dir.path, 'UniversalConverter'));
    if (!out.existsSync()) await out.create(recursive: true);
    return out;
  }

  Future<File> _uniqueFile(Directory dir, String name) async {
    var file = File(p.join(dir.path, name));
    if (!file.existsSync()) return file;
    final ext = p.extension(name);
    final stem = p.basenameWithoutExtension(name);
    var i = 1;
    while (File(p.join(dir.path, '$stem ($i)$ext')).existsSync()) i++;
    return File(p.join(dir.path, '$stem ($i)$ext'));
  }

  Future<void> _convert() async {
    if (_files.isEmpty) return;
    setState(() { _busy = true; _progress = 0; });
    final out = await _outputDir();
    try {
      for (var i = 0; i < _files.length; i++) {
        final input = _files[i];
        final path = input.path;
        if (path == null) throw Exception('无法读取 ${input.name}');
        final ext = p.extension(path).toLowerCase().replaceFirst('.', '');
        final bytes = await File(path).readAsBytes();
        File output;
        if (imageTargets.map((e) => e.toLowerCase()).contains(_target.toLowerCase()) &&
            ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif'].contains(ext)) {
          output = await _convertImage(bytes, input.name, _target, out);
        } else if (textTargets.map((e) => e.toLowerCase()).contains(_target.toLowerCase()) &&
            ['txt', 'md', 'json', 'csv', 'yaml', 'yml', 'xml'].contains(ext)) {
          output = await _convertText(bytes, input.name, ext, _target, out);
        } else if (_target == 'ZIP') {
          output = await _makeZip(bytes, input.name, out);
        } else {
          throw Exception('${input.name}: 当前手机版暂不支持 $ext → $_target，本地转换不会上传文件。');
        }
        _history.insert(0, '${input.name} → ${p.basename(output.path)}');
        setState(() => _progress = (i + 1) / _files.length);
      }
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('转换完成，文件保存在应用文档目录。')));
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('$e')));
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  Future<File> _convertImage(Uint8List bytes, String name, String target, Directory dir) async {
    final decoded = img.decodeImage(bytes);
    if (decoded == null) throw Exception('$name 不是可识别的图片。');
    final format = target.toLowerCase() == 'jpg' ? 'jpg' : target.toLowerCase();
    final encoded = switch (format) {
      'png' => img.encodePng(decoded),
      'jpg' => img.encodeJpg(decoded, quality: 92),
      'webp' => img.encodeJpg(decoded, quality: 92),
      'bmp' => img.encodeBmp(decoded),
      'gif' => img.encodeGif(decoded),
      _ => throw Exception('不支持图片格式 $target'),
    };
    final output = await _uniqueFile(dir, '${p.basenameWithoutExtension(name)}.$format');
    await output.writeAsBytes(encoded, flush: true);
    return output;
  }

  Future<File> _convertText(Uint8List bytes, String name, String source, String target, Directory dir) async {
    final text = utf8.decode(bytes, allowMalformed: true);
    dynamic data;
    final normalized = source == 'yml' ? 'yaml' : source;
    if (normalized == 'json') data = jsonDecode(text);
    else if (normalized == 'csv') data = const CsvToListConverter().convert(text);
    else if (normalized == 'yaml') data = _yamlToJson(loadYaml(text));
    else if (normalized == 'xml') data = {'xml': text};
    else data = text;

    String result;
    final t = target.toLowerCase();
    if (t == 'txt' || t == 'md') result = data is String ? data : const JsonEncoder.withIndent('  ').convert(data);
    else if (t == 'json') result = const JsonEncoder.withIndent('  ').convert(data);
    else if (t == 'csv') {
      if (data is! List) throw Exception('只有二维列表数据才能导出 CSV。');
      result = const ListToCsvConverter().convert(data);
    } else if (t == 'yaml') result = _simpleYaml(data);
    else if (t == 'xml') result = _simpleXml(data);
    else throw Exception('不支持文本格式 $target');
    final output = await _uniqueFile(dir, '${p.basenameWithoutExtension(name)}.$t');
    await output.writeAsString(result, flush: true);
    return output;
  }

  dynamic _yamlToJson(dynamic value) {
    if (value is YamlMap) return value.map((k, v) => MapEntry(k.toString(), _yamlToJson(v)));
    if (value is YamlList) return value.map(_yamlToJson).toList();
    return value;
  }

  String _simpleYaml(dynamic data, [int level = 0]) {
    final pad = '  ' * level;
    if (data is Map) return data.entries.map((e) => '$pad${e.key}: ${_simpleYaml(e.value, level + 1).trimLeft()}').join('\n');
    if (data is List) return data.map((v) => '$pad- ${_simpleYaml(v, level + 1).trimLeft()}').join('\n');
    if (data is String) return jsonEncode(data);
    return '$data';
  }

  String _simpleXml(dynamic data) {
    final builder = XmlBuilder()..processing('xml', 'version="1.0"')..element('data', nest: () => _xmlNest(data));
    return builder.buildDocument().toXmlString(pretty: true);
  }

  void _xmlNest(dynamic value) {
    if (value is Map) {
      for (final e in value.entries) XmlBuilder();
    }
  }

  Future<File> _makeZip(Uint8List bytes, String name, Directory dir) async {
    final archive = Archive()..addFile(ArchiveFile(name, bytes.length, bytes));
    final encoded = ZipEncoder().encode(archive);
    final output = await _uniqueFile(dir, '${p.basenameWithoutExtension(name)}.zip');
    await output.writeAsBytes(encoded, flush: true);
    return output;
  }

  Future<void> _shareLatest() async {
    if (_history.isEmpty) return;
    final dir = await _outputDir();
    final files = dir.listSync().whereType<File>().take(5).map((f) => XFile(f.path)).toList();
    if (files.isNotEmpty) await SharePlus.instance.share(ShareParams(files: files, text: 'Universal Converter 转换结果'));
  }

  @override
  Widget build(BuildContext context) {
    final targets = [...imageTargets, ...textTargets, 'ZIP'];
    return Scaffold(
      appBar: AppBar(title: const Text('Universal Converter'), actions: [IconButton(onPressed: _shareLatest, icon: const Icon(Icons.share))]),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        FilledButton.icon(onPressed: _busy ? null : _pickFiles, icon: const Icon(Icons.add), label: const Text('选择文件')),
        const SizedBox(height: 12),
        Card(child: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text('目标格式', style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 8),
          DropdownButtonFormField<String>(value: _target, items: targets.map((x) => DropdownMenuItem(value: x, child: Text(x))).toList(), onChanged: _busy ? null : (v) => setState(() => _target = v!)),
        ]))),
        const SizedBox(height: 12),
        ..._files.map((f) => ListTile(leading: const Icon(Icons.insert_drive_file), title: Text(f.name), trailing: IconButton(onPressed: _busy ? null : () => setState(() => _files.remove(f)), icon: const Icon(Icons.close)))),
        if (_busy) ...[const SizedBox(height: 12), LinearProgressIndicator(value: _progress), const SizedBox(height: 8), Text('${(_progress * 100).round()}%')],
        const SizedBox(height: 12),
        FilledButton.icon(onPressed: _busy || _files.isEmpty ? null : _convert, icon: const Icon(Icons.transform), label: const Text('开始转换')),
        const SizedBox(height: 24),
        Text('本地转换历史', style: Theme.of(context).textTheme.titleLarge),
        const SizedBox(height: 8),
        if (_history.isEmpty) const Text('暂无记录'),
        ..._history.map((h) => ListTile(dense: true, leading: const Icon(Icons.check_circle_outline), title: Text(h))),
      ]),
    );
  }
}
