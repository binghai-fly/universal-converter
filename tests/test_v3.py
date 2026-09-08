from pathlib import Path

from converters import convert


def test_text_round_trip(tmp_path: Path):
    src = tmp_path / "data.txt"
    json_file = tmp_path / "data.json"
    out = tmp_path / "data.txt"
    src.write_text("hello", encoding="utf-8")
    convert(src, json_file)
    convert(json_file, out)
    assert out.read_text(encoding="utf-8") == "hello"


def test_archive_zip_to_zip(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    (src_dir / "hello.txt").write_text("hello", encoding="utf-8")
    import zipfile
    src = tmp_path / "a.zip"
    with zipfile.ZipFile(src, "w") as z:
        z.write(src_dir / "hello.txt", "hello.txt")
    dst = tmp_path / "b.zip"
    convert(src, dst)
    with zipfile.ZipFile(dst) as z:
        assert z.read("hello.txt") == b"hello"
