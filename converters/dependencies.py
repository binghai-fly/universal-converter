"""External dependency discovery and Windows setup helpers."""
from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

LIBREOFFICE_DOWNLOAD_URL = "https://www.libreoffice.org/download/download-libreoffice/"


def find_soffice() -> str | None:
    """Find LibreOffice without requiring the user to edit PATH."""
    candidates = []

    for name in ("soffice.exe", "soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            candidates.append(found)

    if os.name == "nt":
        program_files = [
            os.environ.get("PROGRAMFILES"),
            os.environ.get("PROGRAMW6432"),
            os.environ.get("PROGRAMFILES(X86)"),
            os.environ.get("LOCALAPPDATA"),
        ]
        relative = (
            Path("LibreOffice") / "program" / "soffice.exe",
            Path("LibreOffice") / "program" / "soffice.com",
            Path("LibreOfficePortable") / "App" / "libreoffice" / "program" / "soffice.exe",
        )
        for root in filter(None, program_files):
            base = Path(root)
            for rel in relative:
                candidates.append(str(base / rel))

        # Common per-user Scoop installation.
        userprofile = os.environ.get("USERPROFILE")
        if userprofile:
            candidates.append(str(Path(userprofile) / "scoop" / "apps" / "libreoffice" / "current" / "program" / "soffice.exe"))

    for candidate in candidates:
        path = Path(candidate)
        if path.exists() and path.is_file():
            return str(path)
    return None


def office_available() -> bool:
    return find_soffice() is not None


def install_libreoffice_windows() -> tuple[bool, str]:
    """Try a consented, non-interactive install via WinGet on Windows."""
    if os.name != "nt":
        return False, "自动安装 LibreOffice 目前仅针对 Windows。"

    winget = shutil.which("winget")
    if not winget:
        return False, "未找到 Windows App Installer/WinGet。请使用官方安装包安装 LibreOffice。"

    cmd = [
        winget,
        "install",
        "--id", "TheDocumentFoundation.LibreOffice",
        "--exact",
        "--silent",
        "--accept-package-agreements",
        "--accept-source-agreements",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return False, "LibreOffice 安装超时，请检查网络后重试。"
    except OSError as exc:
        return False, f"无法启动 WinGet：{exc}"

    if proc.returncode == 0 and find_soffice():
        return True, "LibreOffice 安装完成。"

    detail = (proc.stderr or proc.stdout or "WinGet 安装失败").strip()
    return False, detail[-2000:]
