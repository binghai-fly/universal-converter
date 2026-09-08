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
