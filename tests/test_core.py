from pathlib import Path
from converters import convert


def test_text_json(tmp_path):
    src = tmp_path / "a.txt"
    dst = tmp_path / "a.json"
    src.write_text("hello", encoding="utf-8")
    convert(src, dst)
    assert dst.exists()
