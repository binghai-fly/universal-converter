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


def test_pdf_to_docx_editable(tmp_path):
    import fitz
    from docx import Document

    src = tmp_path / "sample.pdf"
    dst = tmp_path / "sample.docx"
    pdf = fitz.open()
    page = pdf.new_page(width=595, height=842)
    page.insert_text((72, 90), "Universal Converter PDF Test", fontsize=18)
    page.insert_text((72, 125), "This text should remain editable in DOCX.", fontsize=11)
    pdf.save(src)
    pdf.close()

    convert(src, dst)
    assert dst.exists()
    assert dst.stat().st_size > 0
    doc = Document(dst)
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "Universal Converter PDF Test" in text
    assert "editable in DOCX" in text
