"""Kiểm chứng "sống" của QT Calendar trên Windows thật.

Script này **chạy ứng dụng thật** (không phải preview) rồi đo các tính chất
quan trọng nhất của một desktop widget:

1. Tiến trình khởi động được và cửa sổ xuất hiện.
2. Cửa sổ **là cửa sổ con của Progman** (⇒ không bị ẩn bởi ``Win + D``) và
   không phải top-level, không có trong Alt+Tab.
3. Toạ độ màn hình khớp với vị trí đã lưu trong ``settings.json``.
4. Đo RAM (working set / private bytes).
5. Ghi/đọc/xoá giá trị khởi động cùng Windows trong Registry.
6. Chụp ảnh toàn màn hình để đối chiếu thị giác.

Cách chạy::

    $env:PYTHONUTF8="1"
    python -X utf8 scripts/verify_live.py

Script tự tắt ứng dụng sau khi đo (không để tiến trình treo).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wintypes
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from qtcalendar.platform import autostart, desktop_pin, win32  # noqa: E402

user32 = ctypes.WinDLL("user32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)


def _windows_of_process(pid: int) -> list[int]:
    """Liệt kê mọi cửa sổ (kể cả cửa sổ con không lộ ra) của tiến trình."""
    found: list[int] = []

    @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    def _cb(hwnd, _lparam):
        wpid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        if wpid.value == pid:
            found.append(int(hwnd))
        return True

    user32.EnumWindows(_cb, 0)
    # EnumWindows chỉ trả top-level; cửa sổ con phải EnumChildWindows từ progman
    progman = win32.find_window("Progman")
    if progman:
        found_children: list[int] = []

        @ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        def _child_cb(hwnd, _lparam):
            wpid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
            if wpid.value == pid:
                found_children.append(int(hwnd))
            return True

        user32.EnumChildWindows(progman, _child_cb, 0)
        found.extend(found_children)
    return found


def _class_name(hwnd: int) -> str:
    return win32.get_class_name(hwnd) or "?"


def find_widget_window(pid: int) -> int:
    """Tìm cửa sổ widget của tiến trình (ưu tiên cửa sổ đang visible).

    Qt tạo kèm vài cửa sổ phụ (``Qt6112ThemeChangeObserverWindow``,
    ``Qt6112TrayIconMessageWindowClass``…) có kích thước lớn nhưng **ẩn**,
    nên phải lọc theo cả tên lớp và trạng thái visible.
    """
    candidates: list[tuple[int, int]] = []  # (ưu tiên, hwnd)
    for hwnd in _windows_of_process(pid):
        rect = win32.get_window_rect(hwnd)
        if not rect:
            continue
        width, height = rect[2] - rect[0], rect[3] - rect[1]
        if width < 200 or height < 300:
            continue
        cls = _class_name(hwnd)
        if "Observer" in cls or "MessageWindow" in cls:
            continue
        visible = win32.is_window_visible(hwnd)
        parent = win32.get_parent(hwnd)
        parent_is_desktop = bool(parent) and _class_name(parent) in ("Progman", "WorkerW")
        score = 0
        if visible:
            score += 2
        if parent_is_desktop:
            score += 4
        candidates.append((score, hwnd))
    if not candidates:
        return 0
    candidates.sort(key=lambda item: item[0], reverse=True)
    return candidates[0][1]


def read_memory(pid: int) -> dict[str, float]:
    """Đọc working set / private bytes qua ``Get-Process`` của PowerShell."""
    script = (
        "$p = Get-Process -Id " + str(pid) + "; "
        'Write-Output ("{0} {1} {2}" -f $p.WorkingSet64, '
        "$p.PrivateMemorySize64, $p.PagedMemorySize64)"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            capture_output=True,
            text=True,
            timeout=30,
        )
        parts = out.stdout.strip().split()
        if len(parts) >= 2:
            ws, priv = int(parts[0]), int(parts[1])
            return {
                "working_set_mb": round(ws / 1048576, 1),
                "private_mb": round(priv / 1048576, 1),
            }
    except Exception:
        pass
    return {}


def screenshot(path: Path) -> bool:
    """Chụp màn hình bằng Qt (không cần thư viện ngoài)."""
    os.environ.setdefault("QT_QPA_PLATFORM", "windows")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication(sys.argv[:1])
    screen = app.primaryScreen()
    if screen is None:
        return False
    pm = screen.grabWindow(0)
    path.parent.mkdir(parents=True, exist_ok=True)
    return bool(pm.save(str(path), "PNG"))


def main() -> int:
    config = Path(os.environ.get("TEMP", ".")) / "qtcal_verify_live" / "settings.json"
    config.parent.mkdir(parents=True, exist_ok=True)
    config.write_text(
        json.dumps(
            {
                "x": 940,
                "y": 120,
                "width": 344,
                "height": 468,
                "opacity": 1.0,
                "theme": "giay_do",
                "view": "bloc",
                "placement": "desktop",
                "hidden": False,
                "run_at_startup": False,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    env = dict(os.environ)
    env["QTCALENDAR_CONFIG"] = str(config)
    env["PYTHONUTF8"] = "1"
    pyw = Path(sys.executable).with_name("pythonw.exe")
    launcher = pyw if pyw.is_file() else Path(sys.executable)
    proc = subprocess.Popen(
        [str(launcher), str(ROOT / "run_qtcalendar.pyw")],
        cwd=str(ROOT),
        env=env,
    )

    report: dict = {"pid": proc.pid}
    hwnd = 0
    for _ in range(40):
        time.sleep(0.25)
        hwnd = find_widget_window(proc.pid)
        if hwnd:
            break
    report["window_found"] = bool(hwnd)
    report["hwnd"] = hwnd

    if hwnd:
        parent = win32.get_parent(hwnd)
        progman = win32.find_window("Progman")
        rect = win32.get_window_rect(hwnd)
        style = win32.get_window_long(hwnd, win32.GWL_STYLE)
        exstyle = win32.get_window_long(hwnd, win32.GWL_EXSTYLE)
        report.update(
            {
                "parent": parent,
                "parent_class": _class_name(parent) if parent else "",
                "progman": progman,
                "pinned_to_progman": bool(parent and parent == progman),
                "is_top_level": parent == 0,
                "visible": win32.is_window_visible(hwnd),
                "rect": rect,
                "style_hex": f"0x{style & 0xFFFFFFFF:08X}",
                "ws_child": bool(style & win32.WS_CHILD),
                "ws_popup": bool(style & win32.WS_POPUP),
                "ex_toolwindow": bool(exstyle & win32.WS_EX_TOOLWINDOW),
                "class": _class_name(hwnd),
                "is_pinned_api": desktop_pin.is_pinned(hwnd),
                "desktop_host": desktop_pin.find_desktop_host(),
            }
        )
        time.sleep(0.6)
        report["memory"] = read_memory(proc.pid)

    # ---- Registry khởi động cùng Windows ----
    before = autostart.read_raw()
    enabled_ok = autostart.enable()
    report["autostart"] = {
        "command": autostart.build_command(),
        "before": before,
        "enable_ok": enabled_ok,
        "after_enable": autostart.read_raw(),
        "is_enabled": autostart.is_enabled(),
    }
    autostart.set_enabled(bool(before))  # khôi phục trạng thái ban đầu
    report["autostart"]["restored"] = autostart.read_raw() == before

    shot = Path(os.environ.get("TEMP", ".")) / "qtcal_verify_live" / "desktop.png"
    report["screenshot"] = {"path": str(shot), "saved": screenshot(shot)}

    # ---- tắt app ----
    try:
        proc.terminate()
        proc.wait(timeout=8)
    except Exception:
        proc.kill()
    report["app_exited"] = proc.poll() is not None

    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
