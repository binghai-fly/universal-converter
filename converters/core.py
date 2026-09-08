import csv, json, shutil, subprocess, tempfile, tarfile, zipfile
from pathlib import Path

import yaml
from PIL import Image
import fitz


TEXT = {".txt", ".md", ".csv", ".json", ".yaml", ".yml", ".xml"}
IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tiff", ".gif"}
OFFICE = {".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".odt", ".ods", ".odp"}
MEDIA = {".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a", ".mp4", ".mkv",
         ".avi", ".mov", ".webm", ".mpeg", ".mpg"}


def convert(src: Path, dst: Path):
    if not src.exists():
        raise FileNotFoundError(src)

    s, d = src.suffix.lower(), dst.suffix.lower()
    dst.parent.mkdir(parents=True, exist_ok=True)

    if s in IMAGES and d in IMAGES | {".pdf"}:
        return image_convert(src, dst)

    if s == ".pdf" and d in IMAGES:
        return pdf_to_images(src, dst)

    if s in TEXT and d in TEXT:
        return text_convert(src, dst)

    if s in OFFICE or d in OFFICE:
        return office_convert(src, dst)

    if s in MEDIA or d in MEDIA:
        return ffmpeg_convert(src, dst)

    if s == ".zip" and d in {".tar", ".gz", ".bz2", ".xz"}:
        return archive_extract_convert(src, dst)

    if s == ".zip" and d == ".zip":
        shutil.copy2(src, dst)
        return

    raise ValueError(f"暂不支持：{s} → {d}")


def image_convert(src, dst):
    with Image.open(src) as im:
        if dst.suffix.lower() in {".jpg", ".jpeg"} and im.mode in {"RGBA", "LA"}:
            im = im.convert("RGB")
        im.save(dst)


def pdf_to_images(src, dst):
    doc = fitz.open(src)
    if len(doc) == 0:
        raise ValueError("PDF 没有页面")
    page = doc[0]
    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
    pix.save(dst)


def text_convert(src, dst):
    raw = src.read_text(encoding="utf-8-sig")

    if src.suffix.lower() in {".json"}:
        obj = json.loads(raw)
    elif src.suffix.lower() in {".yaml", ".yml"}:
        obj = yaml.safe_load(raw)
    elif src.suffix.lower() == ".csv":
        rows = list(csv.DictReader(raw.splitlines()))
        obj = rows
    elif src.suffix.lower() == ".xml":
        import xml.etree.ElementTree as ET
        obj = xml_to_dict(ET.fromstring(raw))
    else:
        obj = raw

    if dst.suffix.lower() == ".json":
        dst.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    elif dst.suffix.lower() in {".yaml", ".yml"}:
        dst.write_text(yaml.safe_dump(obj, allow_unicode=True, sort_keys=False), encoding="utf-8")
    elif dst.suffix.lower() == ".csv":
        if not isinstance(obj, list) or not all(isinstance(x, dict) for x in obj):
            raise ValueError("只有对象数组/表格数据才能可靠转换为 CSV")
        keys = list(dict.fromkeys(k for row in obj for k in row))
        with dst.open("w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=keys)
            w.writeheader()
            w.writerows(obj)
    else:
        if not isinstance(obj, str):
            obj = json.dumps(obj, ensure_ascii=False, indent=2)
        dst.write_text(obj, encoding="utf-8")


def xml_to_dict(elem):
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


def office_convert(src, dst):
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    if not soffice:
        raise RuntimeError("Office 格式转换需要安装 LibreOffice，并确保 soffice 在 PATH 中。")
    with tempfile.TemporaryDirectory() as td:
        cmd = [
            soffice, "--headless", "--convert-to", dst.suffix.lstrip("."),
            "--outdir", td, str(src)
        ]
        p = subprocess.run(cmd, capture_output=True, text=True)
        produced = Path(td) / f"{src.stem}{dst.suffix}"
        if p.returncode != 0 or not produced.exists():
            raise RuntimeError((p.stderr or p.stdout or "LibreOffice 转换失败").strip())
        shutil.copy2(produced, dst)


def ffmpeg_convert(src, dst):
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("音视频转换需要安装 FFmpeg，并确保 ffmpeg 在 PATH 中。")
    p = subprocess.run(
        [ffmpeg, "-y", "-i", str(src), str(dst)],
        capture_output=True, text=True
    )
    if p.returncode != 0:
        raise RuntimeError((p.stderr or p.stdout or "FFmpeg 转换失败")[-3000:])


def archive_extract_convert(src, dst):
    raise ValueError("压缩包格式转换暂未启用，避免产生错误的归档结构。")
