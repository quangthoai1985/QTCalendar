"""Đóng gói bản phát hành chính thức QT Calendar cho Windows:
    PyInstaller onedir -> Bộ cài đặt Inno Setup -> Tệp tự cập nhật ngầm Update.zip -> Tính mã SHA-256.

Cách sử dụng:
    py -3.14 tools/build_release.py
    py -3.14 tools/build_release.py --skip-build   # dùng lại thư mục dist/QTCalendar đã build
"""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from qtcalendar import __version__
from qtcalendar.core import update_check as uc

DIST = ROOT / "dist"
APP_DIR_NAME = "QTCalendar"


def iscc_candidates() -> List[Path]:
    found = shutil.which("iscc")
    paths = [Path(found)] if found else []
    for base in (
        os.environ.get("LOCALAPPDATA"),
        os.environ.get("ProgramFiles(x86)"),
        os.environ.get("ProgramFiles"),
    ):
        if base:
            sub = "Programs/Inno Setup 6" if base == os.environ.get("LOCALAPPDATA") else "Inno Setup 6"
            paths.append(Path(base) / sub / "ISCC.exe")
    return paths


def find_iscc() -> Optional[Path]:
    return next((p for p in iscc_candidates() if p.is_file()), None)


def run_cmd(cmd: List[str], **kwargs) -> None:
    print("»", " ".join(cmd), flush=True)
    subprocess.run(cmd, check=True, cwd=str(ROOT), **kwargs)


def make_update_zip(app_dir: Path, out_path: Path) -> Path:
    """Nén `app_dir` thành file zip với thư mục gốc `QTCalendar/` cho auto-update."""
    if not (app_dir / uc.APP_EXE_NAME).is_file() or not (app_dir / "_internal").is_dir():
        raise SystemExit(f"{app_dir} không hợp lệ (thiếu {uc.APP_EXE_NAME} hoặc _internal) — hãy build trước.")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(".zip.part")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        for path in sorted(app_dir.rglob("*")):
            if path.is_file():
                zf.write(path, Path(APP_DIR_NAME) / path.relative_to(app_dir))
    if out_path.exists():
        out_path.unlink()
    tmp.rename(out_path)
    return out_path


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest().lower()


def main() -> None:
    parser = argparse.ArgumentParser(description="Build bản phát hành QT Calendar")
    parser.add_argument("--skip-build", action="store_true", help="Bỏ qua bước PyInstaller, dùng lại dist/QTCalendar")
    args = parser.parse_args()

    print(f"\n========================================================")
    print(f"  BẮT ĐẦU ĐÓNG GÓI PHÁT HÀNH QT CALENDAR v{__version__}")
    print(f"========================================================\n")

    # 1. Build PyInstaller onedir
    app_dir = DIST / APP_DIR_NAME
    if not args.skip_build:
        print("--- [1/4] Biên dịch ứng dụng bằng PyInstaller ---")
        build_bat = ROOT / "build.bat"
        run_cmd([str(build_bat)])
    else:
        print("--- [1/4] Bỏ qua PyInstaller (--skip-build) ---")

    if not app_dir.is_dir() or not (app_dir / uc.APP_EXE_NAME).is_file():
        raise SystemExit(f"Thư mục build {app_dir} không tồn tại hoặc thiếu tệp thực thi!")

    # 2. Tìm trình biên dịch Inno Setup (ISCC.exe)
    print("\n--- [2/4] Biên dịch bộ cài đặt Inno Setup ---")
    iscc = find_iscc()
    if iscc is None:
        raise SystemExit("Không tìm thấy Inno Setup (ISCC.exe). Hãy cài đặt Inno Setup 6.")
    print(f"Đã tìm thấy ISCC tại: {iscc}")

    iss_file = ROOT / "installer.iss"
    run_cmd([str(iscc), f"/DAppVersion={__version__}", str(iss_file)])

    setup_exe = DIST / "QTCalendar_Setup.exe"
    versioned_setup = DIST / f"QTCalendar_Setup_v{__version__}.exe"
    if setup_exe.is_file():
        shutil.copy2(setup_exe, versioned_setup)

    # 3. Nén tệp cập nhật ngầm Update.zip
    print("\n--- [3/4] Đóng gói tệp tự cập nhật Update.zip ---")
    update_zip = DIST / uc.UPDATE_ASSET_NAME
    make_update_zip(app_dir, update_zip)
    print(f"Đã tạo: {update_zip} ({uc.format_size(update_zip.stat().st_size)})")

    # 4. Tính mã SHA-256
    print("\n--- [4/4] Tính mã kiểm tra SHA-256 ---")
    files_to_hash = [setup_exe, versioned_setup, update_zip]
    checksums = []
    for file_path in files_to_hash:
        if file_path.is_file():
            digest = sha256_of(file_path)
            checksums.append(f"{digest} *{file_path.name}")
            print(f"  {file_path.name:32} SHA-256: {digest}")

    sha_file = DIST / f"SHA256SUMS_v{__version__}.txt"
    sha_file.write_text("\n".join(checksums) + "\n", encoding="utf-8")

    print(f"\n========================================================")
    print(f"  HOÀN TẤT ĐÓNG GÓI BẢN PHÁT HÀNH v{__version__}!")
    print(f"========================================================")
    print(f"Các tệp đã sẵn sàng trong thư mục dist/:")
    print(f"  1. Bộ cài đặt:       {versioned_setup.name} (và {setup_exe.name})")
    print(f"  2. Tệp tự cập nhật:  {update_zip.name}")
    print(f"  3. Mã băm SHA-256:   {sha_file.name}")
    print(f"\nĐể phát hành phiên bản mới:")
    print(f"  - Tạo Release trên GitHub: https://github.com/quangthoai1985/QTCalendar/releases/new")
    print(f"  - Đặt tag: v{__version__}")
    print(f"  - Tải lên các tệp trên vào mục Assets.")


if __name__ == "__main__":
    main()
