from pathlib import Path
from zipfile import ZipFile

from converters import convert


def test_text_json(tmp_path):
    src = tmp_path / "a.txt"
    dst = tmp_path / "a.json"
    src.write_text("hello", encoding="utf-8")
    convert(src, dst)
    assert dst.exists()
    assert '"hello"' in dst.read_text(encoding="utf-8")


def test_json_csv_roundtrip(tmp_path):
    src = tmp_path / "a.json"
    mid = tmp_path / "a.csv"
    dst = tmp_path / "a.yaml"
    src.write_text('[{"name":"Alice","age":20}]', encoding="utf-8")
    convert(src, mid)
    convert(mid, dst)
    assert "Alice" in dst.read_text(encoding="utf-8")


def test_image_conversion(tmp_path):
    from PIL import Image
    src = tmp_path / "a.png"
    dst = tmp_path / "a.jpg"
    Image.new("RGB", (16, 16), "white").save(src)
    convert(src, dst)
    assert dst.exists()


def test_zip_tar_conversion(tmp_path):
    import zipfile
    src = tmp_path / "a.zip"
    dst = tmp_path / "a.tar"
    payload = tmp_path / "hello.txt"
    payload.write_text("hello", encoding="utf-8")
    with zipfile.ZipFile(src, "w") as z:
        z.write(payload, "hello.txt")
    convert(src, dst)
    assert dst.exists()


def test_pdf_to_docx_preserves_editable_text_and_page_layout(tmp_path):
    import fitz
    from docx import Document

    src = tmp_path / "sample.pdf"
    dst = tmp_path / "sample.docx"
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.draw_line((72, 200), (523, 200), color=(0, 0, 0), width=1)
    page.insert_text((72, 90), "PDF layout test", fontsize=18)
    page.insert_text((72, 125), "This text should remain editable in DOCX.", fontsize=11)
    pdf.save(src)
    pdf.close()

    convert(src, dst)
    assert dst.exists()
    assert dst.stat().st_size > 0

    # Text lives in editable Word text boxes rather than being flattened into
    # the page image. Check the generated OOXML directly because python-docx's
    # high-level paragraph API does not expose VML text-box contents.
    with ZipFile(dst) as z:
        xml = z.read("word/document.xml").decode("utf-8")
    assert "PDF layout test" in xml
    assert "editable in DOCX" in xml
    assert "pdfText1" in xml
    assert "pdfPage0" in xml

    # The resulting document still has the source page size.
    doc = Document(dst)
    section = doc.sections[0]
    assert round(section.page_width.inches, 1) == round(595 / 72, 1)
    assert round(section.page_height.inches, 1) == round(842 / 72, 1)
