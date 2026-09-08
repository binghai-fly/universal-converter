"""Conversion engine for common text, image, PDF, Office, media and archive formats."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
import xml.etree.ElementTree as ET

import fitz
import yaml
from PIL import Image
from docx import Document
from docx.enum.section import WD_SECTION
from docx.shared import Inches, Pt

from .dependencies import find_soffice

TEXT = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"}
OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf"}
MEDIA = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".opus", ".mp4", ".mkv", ".avi", ".mov", ".webm", ".mpeg", ".mpg", ".m4v"}
ARCHIVES = {".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz"}
ALL_FORMATS = sorted(TEXT | IMAGES | OFFICE | MEDIA | ARCHIVES | {".pdf"})


def format_name(path: Path) -> str:
    name = path.name.lower()
    if name.endswith(".tar.gz"): return ".tar.gz"
    if name.endswith(".tar.bz2"): return ".tar.bz2"
    if name.endswith(".tar.xz"): return ".tar.xz"
    return path.suffix.lower()


def convert(src: Path, dst: Path) -> None:
    src, dst = Path(src), Path(dst)
    if not src.exists(): raise FileNotFoundError(f"找不到输入文件：{src}")
    if src.is_dir(): raise ValueError("暂不支持直接转换文件夹，请先压缩成 ZIP/TAR。")
    if src.resolve() == dst.resolve(): raise ValueError("输入文件和输出文件不能相同。")
    dst.parent.mkdir(parents=True, exist_ok=True)
    s, d = format_name(src), format_name(dst)
    if s == d:
        shutil.copy2(src, dst); return
    if s == ".pdf" and d == ".docx":
        pdf_to_docx(src, dst); return
    if s in IMAGES and (d in IMAGES or d == ".pdf"):
        image_convert(src, dst); return
    if s == ".pdf" and d in IMAGES:
        pdf_to_image(src, dst); return
    if s in TEXT and d in TEXT:
        text_convert(src, dst); return
    if (s in OFFICE or d in OFFICE) and d not in MEDIA:
        office_convert(src, dst); return
    if s in MEDIA or d in MEDIA:
        ffmpeg_convert(src, dst); return
    if s in ARCHIVES or d in ARCHIVES:
        archive_convert(src, dst); return
    raise ValueError(f"暂不支持：{s} → {d}")


def image_convert(src: Path, dst: Path) -> None:
    with Image.open(src) as original:
        im = original.convert("RGB") if dst.suffix.lower() in {".jpg", ".jpeg"} and original.mode in {"RGBA", "LA", "P"} else original
        save_kwargs = {"quality": 95} if dst.suffix.lower() in {".jpg", ".jpeg", ".webp"} else {}
        im.save(dst, **save_kwargs)


def pdf_to_image(src: Path, dst: Path) -> None:
    doc = fitz.open(src)
    try:
        if len(doc) == 0: raise ValueError("PDF 没有页面")
        doc[0].get_pixmap(dpi=150, alpha=False).save(dst)
    finally:
        doc.close()


def _pdf_font_name(span: dict) -> str:
    name = span.get("font", "Arial")
    if "+" in name: name = name.split("+", 1)[-1]
    return name or "Arial"


def _add_pdf_text_block(docx: Document, block: dict, page_width_pt: float) -> None:
    lines = []
    for line in block.get("lines", []):
        spans = line.get("spans", [])
        if spans: lines.append((line, spans))
    if not lines: return
    x0, y0, x1, y1 = block["bbox"]
    p = docx.add_paragraph()
    p.paragraph_format.left_indent = Inches(max(0, x0) / 72)
    p.paragraph_format.space_before = Pt(max(0, y0) * 72 / page_width_pt * 0)  # reset; page spacing is handled by line geometry
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.0
    for li, (line, spans) in enumerate(lines):
        if li:
            p.add_run().add_break()
        for span in spans:
            text = span.get("text", "")
            if not text: continue
            run = p.add_run(text)
            run.font.name = _pdf_font_name(span)
            size = float(span.get("size", 10) or 10)
            run.font.size = Pt(max(5, min(size, 72)))
            flags = int(span.get("flags", 0))
            run.bold = bool(flags & 16)
            run.italic = bool(flags & 2)


def _add_pdf_image_block(docx: Document, block: dict, page_width_pt: float) -> None:
    data = block.get("image")
    if not data: return
    x0, y0, x1, y1 = block["bbox"]
    width_pt = max(1, x1 - x0)
    max_width_pt = max(72, page_width_pt - x0 - 18)
    width_pt = min(width_pt, max_width_pt)
    p = docx.add_paragraph()
    p.paragraph_format.left_indent = Inches(max(0, x0) / 72)
    p.paragraph_format.space_after = Pt(0)
    try:
        p.add_run().add_picture(BytesIO(data), width=Inches(width_pt / 72))
    except Exception:
        return


def _table_bbox(table) -> tuple[float, float, float, float]:
    bbox = getattr(table, "bbox", (0, 0, 0, 0))
    return tuple(float(x) for x in bbox)


def _overlaps(a, b) -> bool:
    ax0, ay0, ax1, ay1 = a; bx0, by0, bx1, by1 = b
    return not (ax1 <= bx0 or bx1 <= ax0 or ay1 <= by0 or by1 <= ay0)


def _add_pdf_table(docx: Document, table) -> None:
    data = table.extract()
    if not data: return
    rows = len(data); cols = max((len(r) for r in data), default=0)
    if not rows or not cols: return
    wt = docx.add_table(rows=rows, cols=cols)
    wt.style = "Table Grid"
    for r, row in enumerate(data):
        for c, value in enumerate(row):
            wt.cell(r, c).text = "" if value is None else str(value)
    docx.add_paragraph().paragraph_format.space_after = Pt(0)


def pdf_to_docx(src: Path, dst: Path) -> None:
    """Convert a text-based PDF into an editable DOCX while approximating page layout.

    Text spans keep font size/style and horizontal position; images are embedded and
    detected PDF tables become editable Word tables when PyMuPDF can detect them.
    Scanned/image-only pages are preserved as page images so the visual layout is not lost.
    OCR is intentionally left for a later release.
    """
    pdf = fitz.open(src)
    try:
        if len(pdf) == 0: raise ValueError("PDF 没有页面")
        docx = Document()
        first = True
        for page in pdf:
            if not first:
                section = docx.add_section(WD_SECTION.NEW_PAGE)
            else:
                section = docx.sections[0]
                first = False
            rect = page.rect
            section.page_width = Inches(rect.width / 72)
            section.page_height = Inches(rect.height / 72)
            section.top_margin = Inches(0.15)
            section.bottom_margin = Inches(0.15)
            section.left_margin = Inches(0.15)
            section.right_margin = Inches(0.15)

            blocks = page.get_text("dict").get("blocks", [])
            text_blocks = [b for b in blocks if b.get("type") == 0 and any(s.get("text", "").strip() for l in b.get("lines", []) for s in l.get("spans", []))]
            image_blocks = [b for b in blocks if b.get("type") == 1 and b.get("image")]
            try:
                tables = list(page.find_tables().tables)
            except Exception:
                tables = []
            table_boxes = [_table_bbox(t) for t in tables]
            if not text_blocks and not image_blocks and not tables:
                pix = page.get_pixmap(dpi=150, alpha=False)
                p = docx.add_paragraph()
                p.add_run().add_picture(BytesIO(pix.tobytes("png")), width=Inches(min(rect.width, 540) / 72))
                continue
            items = []
            for b in text_blocks:
                if not any(_overlaps(tuple(b["bbox"]), tb) for tb in table_boxes): items.append((b["bbox"][1], 0, b))
            for b in image_blocks: items.append((b["bbox"][1], 1, b))
            for t in tables: items.append((_table_bbox(t)[1], 2, t))
            items.sort(key=lambda x: (x[0], x[1]))
            for _, kind, obj in items:
                if kind == 0: _add_pdf_text_block(docx, obj, rect.width)
                elif kind == 1: _add_pdf_image_block(docx, obj, rect.width)
                else: _add_pdf_table(docx, obj)
        if len(docx.paragraphs) == 0:
            raise ValueError("PDF 未提取到可转换内容")
        docx.save(dst)
    finally:
        pdf.close()


def _read_text_data(src: Path):
    raw = src.read_text(encoding="utf-8-sig")
    suffix = src.suffix.lower()
    if suffix == ".json": return json.loads(raw)
    if suffix in {".yaml", ".yml"}: return yaml.safe_load(raw)
    if suffix == ".csv": return list(csv.DictReader(raw.splitlines()))
    if suffix == ".xml": return xml_to_dict(ET.fromstring(raw))
    return raw


def text_convert(src: Path, dst: Path) -> None:
    obj = _read_text_data(src); suffix = dst.suffix.lower()
    if suffix == ".json": dst.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    elif suffix in {".yaml", ".yml"}: dst.write_text(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), encoding="utf-8")
    elif suffix == ".csv":
        if not isinstance(obj, list) or not all(isinstance(row, dict) for row in obj): raise ValueError("只有对象数组/表格数据才能可靠转换为 CSV。")
        keys = list(dict.fromkeys(key for row in obj for key in row))
        with dst.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore"); writer.writeheader(); writer.writerows(obj)
    elif suffix == ".xml": dst.write_text(dict_to_xml(obj), encoding="utf-8")
    else:
        if not isinstance(obj, str): obj = json.dumps(obj, ensure_ascii=False, indent=2)
        dst.write_text(obj, encoding="utf-8")


def xml_to_dict(elem: ET.Element):
    children = list(elem)
    if not children: return elem.text or ""
    out = {}
    for child in children:
        value = xml_to_dict(child)
        if child.tag in out:
            if not isinstance(out[child.tag], list): out[child.tag] = [out[child.tag]]
            out[child.tag].append(value)
        else: out[child.tag] = value
    return {elem.tag: out}


def dict_to_xml(obj) -> str:
    if not isinstance(obj, dict) or len(obj) != 1: raise ValueError("XML 输出需要一个唯一的根节点对象。")
    root_name, value = next(iter(obj.items())); root = ET.Element(str(root_name)); _fill_xml(root, value)
    return ET.tostring(root, encoding="unicode")


def _fill_xml(parent: ET.Element, value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            values = child if isinstance(child, list) else [child]
            for item in values: node = ET.SubElement(parent, str(key)); _fill_xml(node, item)
    elif isinstance(value, list):
        for item in value: node = ET.SubElement(parent, "item"); _fill_xml(node, item)
    elif value is not None: parent.text = str(value)


def office_convert(src: Path, dst: Path) -> None:
    soffice = find_soffice()
    if not soffice: raise RuntimeError("未检测到 LibreOffice。请在“Office 依赖”中自动安装，或手动安装后重试。")
    with tempfile.TemporaryDirectory() as td:
        cmd = [soffice, "--headless", "--convert-to", dst.suffix.lstrip("."), "--outdir", td, str(src)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        produced = Path(td) / f"{src.stem}{dst.suffix}"
        if p.returncode != 0 or not produced.exists(): raise RuntimeError((p.stderr or p.stdout or "LibreOffice 转换失败").strip())
        shutil.copy2(produced, dst)


def ffmpeg_convert(src: Path, dst: Path) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg: raise RuntimeError("音视频转换需要 FFmpeg，并确保 ffmpeg 在 PATH 中。")
    p = subprocess.run([ffmpeg, "-hide_banner", "-y", "-i", str(src), str(dst)], capture_output=True, text=True, timeout=1800)
    if p.returncode != 0: raise RuntimeError((p.stderr or p.stdout or "FFmpeg 转换失败")[-4000:])


def _extract_archive(src: Path, workdir: Path) -> None:
    suffix = format_name(src)
    if suffix == ".zip":
        with zipfile.ZipFile(src) as z: z.extractall(workdir)
    elif suffix in {".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"}:
        with tarfile.open(src, "r:*") as tar:
            if hasattr(tarfile, "data_filter"): tar.extractall(workdir, filter="data")
            else: tar.extractall(workdir)
    else: raise ValueError(f"暂不支持解压：{suffix}")


def _archive_directory(workdir: Path, dst: Path) -> None:
    suffix = format_name(dst)
    if suffix == ".zip":
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for path in workdir.rglob("*"):
                if path.is_file(): z.write(path, path.relative_to(workdir))
        return
    mode = {".tar": "w", ".tar.gz": "w:gz", ".tgz": "w:gz", ".tar.bz2": "w:bz2", ".tar.xz": "w:xz"}.get(suffix)
    if not mode: raise ValueError(f"暂不支持生成归档：{suffix}")
    with tarfile.open(dst, mode) as tar:
        for path in workdir.rglob("*"): tar.add(path, arcname=path.relative_to(workdir))


def archive_convert(src: Path, dst: Path) -> None:
    supported = {".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"}
    if format_name(src) not in supported: raise ValueError("输入压缩格式目前仅支持 ZIP/TAR/TAR.GZ/TGZ/TAR.BZ2/TAR.XZ。")
    if format_name(dst) not in supported: raise ValueError("输出压缩格式目前仅支持 ZIP/TAR/TAR.GZ/TGZ/TAR.BZ2/TAR.XZ。")
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td) / "payload"; workdir.mkdir(); _extract_archive(src, workdir); _archive_directory(workdir, dst)
