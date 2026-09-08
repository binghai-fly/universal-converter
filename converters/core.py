"""Conversion engine for common text, image, PDF, Office, media and archive formats."""
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import tarfile
import tempfile
import zipfile
from pathlib import Path
import xml.etree.ElementTree as ET

import fitz
import yaml
from PIL import Image


TEXT = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".tif", ".gif"}
OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp", ".rtf"}
MEDIA = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".opus",
    ".mp4", ".mkv", ".avi", ".mov", ".webm", ".mpeg", ".mpg", ".m4v",
}
ARCHIVES = {".zip", ".tar", ".gz", ".bz2", ".xz", ".tgz"}

ALL_FORMATS = sorted(TEXT | IMAGES | OFFICE | MEDIA | ARCHIVES | {".pdf"})


def format_name(path: Path) -> str:
    """Return a normalized extension, including .tgz."""
    name = path.name.lower()
    if name.endswith(".tar.gz"):
        return ".tar.gz"
    if name.endswith(".tar.bz2"):
        return ".tar.bz2"
    if name.endswith(".tar.xz"):
        return ".tar.xz"
    return path.suffix.lower()


def convert(src: Path, dst: Path) -> None:
    """Convert *src* into *dst* using the best available adapter."""
    src = Path(src)
    dst = Path(dst)
    if not src.exists():
        raise FileNotFoundError(f"找不到输入文件：{src}")
    if src.is_dir():
        raise ValueError("暂不支持直接转换文件夹，请先压缩成 ZIP/TAR。")
    if src.resolve() == dst.resolve():
        raise ValueError("输入文件和输出文件不能相同。")

    dst.parent.mkdir(parents=True, exist_ok=True)
    s, d = format_name(src), format_name(dst)

    if s == d:
        shutil.copy2(src, dst)
        return

    if s in IMAGES and (d in IMAGES or d == ".pdf"):
        image_convert(src, dst)
        return
    if s == ".pdf" and d in IMAGES:
        pdf_to_image(src, dst)
        return
    if s in TEXT and d in TEXT:
        text_convert(src, dst)
        return
    if (s in OFFICE or d in OFFICE) and d not in MEDIA:
        office_convert(src, dst)
        return
    if s in MEDIA or d in MEDIA:
        ffmpeg_convert(src, dst)
        return
    if s in ARCHIVES or d in ARCHIVES:
        archive_convert(src, dst)
        return

    raise ValueError(f"暂不支持：{s} → {d}")


def image_convert(src: Path, dst: Path) -> None:
    with Image.open(src) as original:
        im = original.convert("RGB") if dst.suffix.lower() in {".jpg", ".jpeg"} and original.mode in {"RGBA", "LA", "P"} else original
        save_kwargs = {"quality": 95} if dst.suffix.lower() in {".jpg", ".jpeg", ".webp"} else {}
        im.save(dst, **save_kwargs)


def pdf_to_image(src: Path, dst: Path) -> None:
    """Render the first PDF page at 150 DPI into the requested image format."""
    doc = fitz.open(src)
    try:
        if not doc:
            raise ValueError("PDF 没有页面")
        page = doc[0]
        pix = page.get_pixmap(dpi=150, alpha=False)
        pix.save(dst)
    finally:
        doc.close()


def _read_text_data(src: Path):
    raw = src.read_text(encoding="utf-8-sig")
    suffix = src.suffix.lower()
    if suffix == ".json":
        return json.loads(raw)
    if suffix in {".yaml", ".yml"}:
        return yaml.safe_load(raw)
    if suffix == ".csv":
        return list(csv.DictReader(raw.splitlines()))
    if suffix == ".xml":
        return xml_to_dict(ET.fromstring(raw))
    return raw


def text_convert(src: Path, dst: Path) -> None:
    obj = _read_text_data(src)
    suffix = dst.suffix.lower()

    if suffix == ".json":
        dst.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    elif suffix in {".yaml", ".yml"}:
        dst.write_text(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), encoding="utf-8")
    elif suffix == ".csv":
        if not isinstance(obj, list) or not all(isinstance(row, dict) for row in obj):
            raise ValueError("只有对象数组/表格数据才能可靠转换为 CSV。")
        keys = list(dict.fromkeys(key for row in obj for key in row))
        with dst.open("w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(obj)
    elif suffix == ".xml":
        dst.write_text(dict_to_xml(obj), encoding="utf-8")
    else:
        if not isinstance(obj, str):
            obj = json.dumps(obj, ensure_ascii=False, indent=2)
        dst.write_text(obj, encoding="utf-8")


def xml_to_dict(elem: ET.Element):
    children = list(elem)
    if not children:
        return elem.text or ""
    out = {}
    for child in children:
        value = xml_to_dict(child)
        if child.tag in out:
            if not isinstance(out[child.tag], list):
                out[child.tag] = [out[child.tag]]
            out[child.tag].append(value)
        else:
            out[child.tag] = value
    return {elem.tag: out}


def dict_to_xml(obj) -> str:
    if not isinstance(obj, dict) or len(obj) != 1:
        raise ValueError("XML 输出需要一个唯一的根节点对象。")
    root_name, value = next(iter(obj.items()))
    root = ET.Element(str(root_name))
    _fill_xml(root, value)
    return ET.tostring(root, encoding="unicode")


def _fill_xml(parent: ET.Element, value) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            values = child if isinstance(child, list) else [child]
            for item in values:
                node = ET.SubElement(parent, str(key))
                _fill_xml(node, item)
    elif isinstance(value, list):
        for item in value:
            node = ET.SubElement(parent, "item")
            _fill_xml(node, item)
    elif value is not None:
        parent.text = str(value)


def _find_program(*names: str) -> str | None:
    for name in names:
        path = shutil.which(name)
        if path:
            return path
    return None


def office_convert(src: Path, dst: Path) -> None:
    soffice = _find_program("soffice", "libreoffice")
    if not soffice:
        raise RuntimeError("Office 格式转换需要 LibreOffice，并确保 soffice 在 PATH 中。")
    with tempfile.TemporaryDirectory() as td:
        cmd = [soffice, "--headless", "--convert-to", dst.suffix.lstrip("."), "--outdir", td, str(src)]
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
        produced = Path(td) / f"{src.stem}{dst.suffix}"
        if p.returncode != 0 or not produced.exists():
            detail = (p.stderr or p.stdout or "LibreOffice 转换失败").strip()
            raise RuntimeError(detail)
        shutil.copy2(produced, dst)


def ffmpeg_convert(src: Path, dst: Path) -> None:
    ffmpeg = _find_program("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("音视频转换需要 FFmpeg，并确保 ffmpeg 在 PATH 中。")
    p = subprocess.run(
        [ffmpeg, "-hide_banner", "-y", "-i", str(src), str(dst)],
        capture_output=True, text=True, timeout=1800,
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "FFmpeg 转换失败")[-4000:])


def _extract_archive(src: Path, workdir: Path) -> None:
    suffix = format_name(src)
    if suffix == ".zip":
        with zipfile.ZipFile(src) as z:
            z.extractall(workdir)
    elif suffix in {".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"}:
        with tarfile.open(src, "r:*") as tar:
            if hasattr(tarfile, "data_filter"):
                tar.extractall(workdir, filter="data")
            else:
                tar.extractall(workdir)
    else:
        raise ValueError(f"暂不支持解压：{suffix}")


def _archive_directory(workdir: Path, dst: Path) -> None:
    suffix = format_name(dst)
    if suffix == ".zip":
        with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as z:
            for path in workdir.rglob("*"):
                if path.is_file():
                    z.write(path, path.relative_to(workdir))
        return
    mode = {".tar": "w", ".tar.gz": "w:gz", ".tgz": "w:gz", ".tar.bz2": "w:bz2", ".tar.xz": "w:xz"}.get(suffix)
    if not mode:
        raise ValueError(f"暂不支持生成归档：{suffix}")
    with tarfile.open(dst, mode) as tar:
        for path in workdir.rglob("*"):
            tar.add(path, arcname=path.relative_to(workdir))


def archive_convert(src: Path, dst: Path) -> None:
    supported = {".zip", ".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tar.xz"}
    if format_name(src) not in supported:
        raise ValueError("输入压缩格式目前仅支持 ZIP/TAR/TAR.GZ/TGZ/TAR.BZ2/TAR.XZ。")
    if format_name(dst) not in supported:
        raise ValueError("输出压缩格式目前仅支持 ZIP/TAR/TAR.GZ/TGZ/TAR.BZ2/TAR.XZ。")
    with tempfile.TemporaryDirectory() as td:
        workdir = Path(td) / "payload"
        workdir.mkdir()
        _extract_archive(src, workdir)
        _archive_directory(workdir, dst)
