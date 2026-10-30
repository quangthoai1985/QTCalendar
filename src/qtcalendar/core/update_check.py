"""Kiểm tra & cài đặt bản cập nhật QT Calendar từ GitHub Release.

Luồng hoạt động:
1. `check_for_update()` đọc `https://api.github.com/repos/quangthoai1985/QTCalendar/releases/latest`,
   so sánh thẻ phiên bản (vd `v1.0.1`) với `__version__` theo SemVer.
2. `download_asset()` tải `QTCalendar_Update.zip` vào `%LOCALAPPDATA%\\QTCalendar\\updates\\`
   (có báo tiến trình %, hỗ trợ huỷ bỏ), kiểm tra kích thước và SHA-256.
3. Bản đóng gói onedir (`sys.frozen`): `prepare_install()` giải nén vào thư mục tạm + sinh script PowerShell;
   `launch_install()` chạy script khi ứng dụng thoát — script đợi tiến trình thoát, đổi thư mục cài thành
   `.old` (bản dự phòng), đưa bản mới vào, giữ lại tệp gỡ cài đặt `unins*` của Inno Setup, cập nhật
   `DisplayVersion` trong Registry («Apps & features») rồi mở lại ứng dụng. Lần khởi động sau
   `cleanup_previous_update()` xoá `.old`.
4. Nếu đang chạy từ mã nguồn (source code): chỉ thông báo có bản mới và mở trình duyệt tải về.

Mọi kết nối HTTPS xác thực bằng `_ssl_context()`: kho chứng chỉ Windows + bộ gốc `certifi`
đóng gói kèm (máy chưa có sẵn gốc của GitHub vẫn cập nhật được).
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import re
import shutil
import ssl
import subprocess
import sys
import tempfile
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, List, NamedTuple, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from .. import APP_ID, APP_NAME, __github_repo__, __version__
from .config import data_dir

API_HOSTS = frozenset({"api.github.com"})
DOWNLOAD_HOSTS = frozenset({"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"})
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
API_OVERRIDE_ENV = "QT_CALENDAR_UPDATE_API"

CHECK_INTERVAL = timedelta(days=1)
API_TIMEOUT = 10.0
DOWNLOAD_TIMEOUT = 30.0
MAX_API_BYTES = 2 * 1024 * 1024
MAX_ASSET_BYTES = 1024 * 1024 * 1024
CHUNK_SIZE = 256 * 1024
USER_AGENT = f"QTCalendar/{__version__} (+https://github.com/{__github_repo__})"

APP_EXE_NAME = "QTCalendar.exe"
UPDATE_ASSET_NAME = "QTCalendar_Update.zip"
SETUP_ASSET_NAME = "QTCalendar_Setup.exe"
UPDATES_ROOT_NAME = "QTCalendar"

#: AppId của bộ cài Inno Setup (installer.iss)
INNO_APP_ID = "{C8E2856F-F57B-4F1D-891E-4B022B8C3A42}"
UPDATE_SCRIPT_NAME = "apply_update.ps1"
UPDATE_LOG_NAME = "update.log"
PENDING_MARKER_NAME = "pending_update.json"
STAGING_DIR_NAME = "staging"

ProgressCallback = Callable[[int, int], None]
CancelCheck = Callable[[], bool]


class UpdateError(Exception):
    """Lỗi kiểm tra / tải / cài bản cập nhật (thông điệp tiếng Việt hiển thị được cho người dùng)."""


class UpdateCancelled(UpdateError):
    """Người dùng huỷ thao tác."""


class ReleaseNotFound(UpdateError):
    """Kho chưa có bản phát hành chính thức nào."""


class InstallDirNotWritable(UpdateError):
    """Thư mục cài đặt không có quyền ghi."""


# ─── Phiên bản SemVer ──────────────────────────────────────────────────────

_SEMVER_RE = re.compile(r"^[vV]?(\d+)\.(\d+)\.(\d+)(?:-([0-9A-Za-z.-]+))?(?:\+[0-9A-Za-z.-]+)?$")


class SemVer(NamedTuple):
    major: int
    minor: int
    patch: int
    prerelease: str = ""

    @property
    def core(self) -> str:
        return f"{self.major}.{self.minor}.{self.patch}"

    @property
    def text(self) -> str:
        return f"{self.core}-{self.prerelease}" if self.prerelease else self.core

    @property
    def is_prerelease(self) -> bool:
        return bool(self.prerelease)

    def sort_key(self) -> tuple[int, int, int, int, str]:
        pre_flag = 0 if self.prerelease else 1
        return (self.major, self.minor, self.patch, pre_flag, self.prerelease)


def parse_version(raw: str) -> Optional[SemVer]:
    """Phân tích chuỗi phiên bản (chấp nhận tiền tố `v`/`V`). Trả `None` nếu sai định dạng."""
    if not raw:
        return None
    match = _SEMVER_RE.match(raw.strip())
    if not match:
        return None
    return SemVer(
        major=int(match.group(1)),
        minor=int(match.group(2)),
        patch=int(match.group(3)),
        prerelease=match.group(4) or "",
    )


def is_newer(remote: str, current: str) -> bool:
    """Trả `True` nếu `remote` cao hơn `current` theo quy ước SemVer."""
    r_ver = parse_version(remote)
    c_ver = parse_version(current)
    if r_ver is None or c_ver is None:
        return False
    return r_ver.sort_key() > c_ver.sort_key()


# ─── Cấu trúc dữ liệu Release ──────────────────────────────────────────────

@dataclass(frozen=True)
class AssetInfo:
    name: str
    url: str
    size: int
    sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag_name: str
    published_at: str
    html_url: str
    body: str = ""
    asset: Optional[AssetInfo] = None
    setup_asset: Optional[AssetInfo] = None

    @property
    def title(self) -> str:
        return f"QT Calendar v{self.version}"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.asset is not None:
            data["asset"] = self.asset.to_dict()
        if self.setup_asset is not None:
            data["setup_asset"] = self.setup_asset.to_dict()
        return data


def _asset_from_item(item: dict[str, Any], sha256_by_name: Optional[dict[str, str]] = None) -> AssetInfo:
    name = str(item.get("name") or "")
    url = str(item.get("browser_download_url") or "")
    size = int(item.get("size") or 0)
    sha256 = ""
    if sha256_by_name and name in sha256_by_name:
        sha256 = sha256_by_name[name]
    elif item.get("digest"):
        digest = str(item["digest"])
        if digest.lower().startswith("sha256:"):
            sha256 = digest[7:].strip().lower()
    return AssetInfo(name=name, url=url, size=size, sha256=sha256)


def parse_release(data: dict[str, Any]) -> Optional[ReleaseInfo]:
    """Trích xuất `ReleaseInfo` từ payload JSON của GitHub Release."""
    tag = str(data.get("tag_name") or "").strip()
    ver = parse_version(tag)
    if ver is None:
        return None
    assets = data.get("assets") or []
    update_asset: Optional[AssetInfo] = None
    setup_asset: Optional[AssetInfo] = None

    for item in assets:
        name = str(item.get("name") or "")
        if name == UPDATE_ASSET_NAME:
            update_asset = _asset_from_item(item)
        elif name == SETUP_ASSET_NAME or name.endswith("_Setup.exe"):
            setup_asset = _asset_from_item(item)

    return ReleaseInfo(
        version=ver.text,
        tag_name=tag,
        published_at=str(data.get("published_at") or ""),
        html_url=str(data.get("html_url") or f"https://github.com/{__github_repo__}/releases/tag/{tag}"),
        body=str(data.get("body") or "").strip(),
        asset=update_asset,
        setup_asset=setup_asset,
    )


# ─── Tải về & mạng ─────────────────────────────────────────────────────────

class _StrictRedirectHandler(HTTPRedirectHandler):
    """Chỉ chấp nhận chuyển hướng trong danh sách máy chủ GitHub an toàn."""

    def redirect_request(self, req: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> Request:
        validate_url(newurl, allowed_hosts=DOWNLOAD_HOSTS | API_HOSTS)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _loopback_allowed() -> bool:
    return bool(os.environ.get(API_OVERRIDE_ENV))


def validate_url(url: str, allowed_hosts: frozenset[str]) -> None:
    parts = urlsplit(url)
    if parts.scheme != "https" and not (_loopback_allowed() and parts.scheme == "http"):
        raise UpdateError(f"Giao thức URL không an toàn (chỉ nhận HTTPS): {url}")
    host = (parts.hostname or "").lower()
    allowed = allowed_hosts | (LOOPBACK_HOSTS if _loopback_allowed() else frozenset())
    if host not in allowed:
        raise UpdateError(f"Máy chủ không nằm trong danh sách cho phép: {host}")


def _ssl_context() -> ssl.SSLContext:
    """Ngữ cảnh SSL: kho chứng chỉ Windows + bộ gốc `certifi` đóng gói kèm.

    Python chỉ tin chứng chỉ gốc ĐANG có trong kho Windows, mà Windows chỉ tải gốc
    còn thiếu khi trình duyệt cần tới ⇒ máy chưa từng mở GitHub bằng Edge báo
    `CERTIFICATE_VERIFY_FAILED: unable to get local issuer certificate`. Vẫn giữ kho
    Windows vì chứng chỉ của phần mềm diệt virus/tường lửa cơ quan nằm ở đó.
    """
    ctx = ssl.create_default_context()
    try:
        import certifi

        ctx.load_verify_locations(cafile=certifi.where())
    except (ImportError, OSError, ssl.SSLError):
        pass  # chạy từ mã nguồn chưa cài certifi: chỉ dùng kho Windows
    return ctx


def _urlopen(req: Request, timeout: float = API_TIMEOUT) -> Any:
    opener = build_opener(_StrictRedirectHandler, HTTPSHandler(context=_ssl_context()))
    return opener.open(req, timeout=timeout)


def release_api_url() -> str:
    override = os.environ.get(API_OVERRIDE_ENV)
    if override:
        return override.strip()
    return f"https://api.github.com/repos/{__github_repo__}/releases/latest"


def fetch_latest_release() -> ReleaseInfo:
    """Lấy thông tin bản phát hành mới nhất từ GitHub API."""
    url = release_api_url()
    validate_url(url, API_HOSTS)
    req = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/vnd.github.v3+json",
        },
    )
    try:
        with _urlopen(req, timeout=API_TIMEOUT) as resp:
            content = resp.read(MAX_API_BYTES + 1)
            if len(content) > MAX_API_BYTES:
                raise UpdateError("Phản hồi từ máy chủ cập nhật vượt quá giới hạn an toàn.")
            data = json.loads(content.decode("utf-8"))
    except HTTPError as exc:
        if exc.code == 404:
            raise ReleaseNotFound("Chưa có bản phát hành chính thức nào trên GitHub.") from exc
        raise UpdateError(f"Máy chủ cập nhật báo lỗi HTTP {exc.code}.") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"Không thể kết nối máy chủ cập nhật: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise UpdateError("Dữ liệu từ máy chủ cập nhật không hợp lệ.") from exc

    rel = parse_release(data)
    if rel is None:
        raise UpdateError("Không đọc được thông tin phiên bản từ bản phát hành.")
    return rel


def check_for_update(current_version: str = __version__) -> Optional[ReleaseInfo]:
    """Kiểm tra xem có bản mới hơn không. Trả `None` nếu đang ở bản mới nhất."""
    rel = fetch_latest_release()
    if is_newer(rel.version, current_version):
        return rel
    return None


def updates_dir() -> Path:
    """Thư mục lưu trữ bản cập nhật tải về: `%LOCALAPPDATA%\\QTCalendar\\updates`."""
    path = data_dir() / "updates"
    path.mkdir(parents=True, exist_ok=True)
    return path


def format_size(bytes_num: int) -> str:
    """Định dạng dung lượng người đọc được (ví dụ: `15.4 MB`)."""
    if bytes_num < 1024:
        return f"{bytes_num} B"
    if bytes_num < 1024 * 1024:
        return f"{bytes_num / 1024:.1f} KB"
    return f"{bytes_num / (1024 * 1024):.1f} MB"


def download_asset(
    asset: AssetInfo,
    dest_path: Optional[Path] = None,
    progress_cb: Optional[ProgressCallback] = None,
    should_cancel: Optional[CancelCheck] = None,
) -> Path:
    """Tải tệp cập nhật, kiểm tra SHA-256."""
    validate_url(asset.url, DOWNLOAD_HOSTS)
    target = dest_path or (updates_dir() / asset.name)
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_suffix(".part")

    req = Request(asset.url, headers={"User-Agent": USER_AGENT})
    sha = hashlib.sha256()
    downloaded = 0
    total = asset.size

    try:
        with _urlopen(req, timeout=DOWNLOAD_TIMEOUT) as resp:
            content_length = resp.headers.get("Content-Length")
            if content_length:
                try:
                    total = int(content_length)
                except ValueError:
                    pass

            with open(part, "wb") as out_fh:
                while True:
                    if should_cancel and should_cancel():
                        raise UpdateCancelled("Đã huỷ tải bản cập nhật.")
                    chunk = resp.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_ASSET_BYTES:
                        raise UpdateError("Tệp tải về vượt quá dung lượng cho phép.")
                    sha.update(chunk)
                    out_fh.write(chunk)
                    if progress_cb:
                        progress_cb(downloaded, total)

        # Kiểm tra kích thước
        if total > 0 and downloaded != total:
            raise UpdateError(f"Tệp tải về không trọn vẹn: {downloaded}/{total} byte.")

        # Kiểm tra SHA-256 nếu có
        calc_hash = sha.hexdigest().lower()
        if asset.sha256 and calc_hash != asset.sha256.lower():
            raise UpdateError(f"Mã băm SHA-256 không khớp (nhận {calc_hash[:12]}..., mong đợi {asset.sha256[:12]}...).")

        if target.exists():
            target.unlink()
        part.rename(target)
        return target
    except Exception:
        if part.exists():
            try:
                part.unlink()
            except OSError:
                pass
        raise


# ─── Cài đặt & Thay thế phiên bản ──────────────────────────────────────────

@dataclass(frozen=True)
class InstallPlan:
    staging_dir: Path
    install_dir: Path
    script_path: Path
    target_version: str
    relaunch: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "staging_dir": str(self.staging_dir),
            "install_dir": str(self.install_dir),
            "script_path": str(self.script_path),
            "target_version": self.target_version,
            "relaunch": self.relaunch,
        }


def is_frozen() -> bool:
    """Trả về `True` nếu đang chạy bản đã build đóng gói (PyInstaller)."""
    return getattr(sys, "frozen", False)


def current_install_dir() -> Optional[Path]:
    """Thư mục cài đặt hiện tại của ứng dụng."""
    if not is_frozen():
        return None
    return Path(sys.executable).resolve().parent


def can_write_install_dir(path: Path) -> bool:
    """Kiểm tra quyền ghi vào thư mục cài đặt."""
    try:
        test_file = path / f".write_test_{os.getpid()}"
        test_file.write_text("ok", encoding="utf-8")
        test_file.unlink()
        return True
    except OSError:
        return False


def find_app_dir(root: Path) -> Path:
    """Tìm thư mục chứa `QTCalendar.exe` và `_internal` bên trong file zip đã giải nén."""
    if (root / APP_EXE_NAME).is_file():
        return root
    matches = list(root.glob(f"*/{APP_EXE_NAME}"))
    if matches:
        return matches[0].parent
    matches_all = list(root.rglob(APP_EXE_NAME))
    if matches_all:
        return matches_all[0].parent
    raise UpdateError(f"Gói cập nhật không chứa tệp thực thi chính {APP_EXE_NAME}.")


def extract_update(zip_path: Path, dest_dir: Path, progress_cb: Optional[ProgressCallback] = None) -> Path:
    """Giải nén an toàn file cập nhật vào thư mục staging."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "r") as zf:
        members = zf.infolist()
        total = len(members)
        for idx, member in enumerate(members, 1):
            target_path = (dest_dir / member.filename).resolve()
            if not str(target_path).startswith(str(dest_dir.resolve())):
                raise UpdateError(f"Phát hiện đường dẫn giải nén không an toàn: {member.filename}")
            zf.extract(member, dest_dir)
            if progress_cb:
                progress_cb(idx, total)

    return find_app_dir(dest_dir)


def update_script_text(
    staging_app_dir: Path,
    install_dir: Path,
    target_version: str,
    pid: int,
    relaunch: bool = True,
    inno_app_id: str = INNO_APP_ID,
) -> str:
    """Sinh kịch bản PowerShell hoán đổi tệp cập nhật ngầm."""
    exe_path = install_dir / APP_EXE_NAME
    log_path = updates_dir() / UPDATE_LOG_NAME

    return f"""# Kịch bản tự cập nhật QT Calendar
$ErrorActionPreference = "Stop"
$LogFile = "{str(log_path).replace('\\', '\\\\')}"
$PidToWait = {pid}
$InstallDir = "{str(install_dir).replace('\\', '\\\\')}"
$StagingDir = "{str(staging_app_dir).replace('\\', '\\\\')}"
$TargetVersion = "{target_version}"
$Relaunch = ${str(relaunch).lower()}
$ExePath = "{str(exe_path).replace('\\', '\\\\')}"
$InnoAppId = "{inno_app_id}"

function Log($msg) {{
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
    "[$timestamp] $msg" | Out-File -Append -FilePath $LogFile -Encoding utf8
}}

Log "Bắt đầu tiến trình cập nhật lên v$TargetVersion..."

# 1. Đợi tiến trình QT Calendar cũ thoát hẳn (tối đa 30 giây)
if ($PidToWait -gt 0) {{
    try {{
        $proc = Get-Process -Id $PidToWait -ErrorAction SilentlyContinue
        if ($proc) {{
            Log "Đợi tiến trình PID $PidToWait thoát..."
            $exited = $proc.WaitForExit(30000)
            if (-not $exited) {{
                Log "Tiến trình chưa thoát sau 30s - dừng tiến trình để tiếp tục hoán đổi tệp..."
                $proc.CloseMainWindow() | Out-Null
                Start-Sleep -Seconds 2
                $proc | Stop-Process -Force -ErrorAction SilentlyContinue
            }}
        }}
    }} catch {{
        Log "Không cần đợi PID $PidToWait ($_)"
    }}
}}
Start-Sleep -Milliseconds 600

# 2. Hoán đổi thư mục cài đặt
$OldDir = "$InstallDir.old"
if (Test-Path $OldDir) {{
    Remove-Item -Recurse -Force $OldDir -ErrorAction SilentlyContinue
}}

# Bảo lưu các tệp gỡ cài đặt của Inno Setup (unins*)
$UninstallFiles = Get-ChildItem -Path $InstallDir -Filter "unins*" -File -ErrorAction SilentlyContinue

# Thử đổi tên tối đa 20 lần (mỗi lần cách 500ms) để đợi Windows nhả file handle
$renamed = $false
for ($i = 0; $i -lt 20 -and -not $renamed; $i++) {{
    try {{
        Log "Thử đổi tên $InstallDir -> $OldDir (lần $($i + 1))..."
        Rename-Item -Path $InstallDir -NewName "$([System.IO.Path]::GetFileName($InstallDir)).old"
        $renamed = $true
    }} catch {{
        Start-Sleep -Milliseconds 500
    }}
}}

if (-not $renamed) {{
    Log "Lỗi: Không thể đổi tên thư mục cài đặt sau 10s (tệp bị khoá). Huỷ cập nhật."
    if ($Relaunch -and (Test-Path $ExePath)) {{
        Start-Process -FilePath $ExePath
    }}
    exit 1
}}

try {{
    Log "Chuyển bản mới từ $StagingDir vào $InstallDir"
    Move-Item -Path $StagingDir -Destination $InstallDir
    
    # Khôi phục tệp gỡ cài đặt Inno Setup vào thư mục mới
    if ($UninstallFiles) {{
        foreach ($file in $UninstallFiles) {{
            Copy-Item -Path $file.FullName -Destination $InstallDir -Force -ErrorAction SilentlyContinue
        }}
    }}
}} catch {{
    Log "Lỗi khi chuyển bản mới: $_. Đang khôi phục bản cũ..."
    if (Test-Path $InstallDir) {{
        Remove-Item -Recurse -Force $InstallDir -ErrorAction SilentlyContinue
    }}
    if (Test-Path $OldDir) {{
        Rename-Item -Path $OldDir -NewName $([System.IO.Path]::GetFileName($InstallDir))
    }}
    if ($Relaunch -and (Test-Path $ExePath)) {{
        Start-Process -FilePath $ExePath
    }}
    exit 2
}}

# 3. Cập nhật Registry DisplayVersion trong Inno Setup Uninstall
try {{
    $RegKey = "HKCU:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\$($InnoAppId)_is1"
    if (Test-Path $RegKey) {{
        Set-ItemProperty -Path $RegKey -Name "DisplayVersion" -Value $TargetVersion -ErrorAction SilentlyContinue
        Log "Đã cập nhật Registry DisplayVersion = $TargetVersion"
    }}
}} catch {{
    Log "Không thể ghi Registry DisplayVersion (không nghiêm trọng): $_"
}}

Log "Cập nhật thành công lên v$TargetVersion!"

# 4. Mở lại ứng dụng nếu yêu cầu
if ($Relaunch -and (Test-Path $ExePath)) {{
    Log "Khởi động lại ứng dụng: $ExePath"
    Start-Process -FilePath $ExePath
}}
"""


def write_update_script(script_text: str) -> Path:
    path = updates_dir() / UPDATE_SCRIPT_NAME
    path.write_text(script_text, encoding="utf-8")
    return path


def prepare_install(
    zip_path: Path,
    target_version: str,
    install_dir: Path,
    relaunch: bool = True,
    progress_cb: Optional[ProgressCallback] = None,
    should_cancel: Optional[CancelCheck] = None,
) -> InstallPlan:
    """Giải nén tệp cập nhật và tạo sẵn script hoán đổi."""
    staging = updates_dir() / STAGING_DIR_NAME
    if staging.exists():
        try:
            shutil.rmtree(staging)
        except OSError:
            pass

    app_staging = extract_update(zip_path, staging, progress_cb=progress_cb)
    if should_cancel and should_cancel():
        raise UpdateCancelled("Đã huỷ chuẩn bị cài đặt bản cập nhật.")

    script_content = update_script_text(
        staging_app_dir=app_staging,
        install_dir=install_dir,
        target_version=target_version,
        pid=os.getpid(),
        relaunch=relaunch,
    )
    script_path = write_update_script(script_content)

    return InstallPlan(
        staging_dir=app_staging,
        install_dir=install_dir,
        script_path=script_path,
        target_version=target_version,
        relaunch=relaunch,
    )


def launch_install(plan: InstallPlan) -> None:
    """Khởi chạy script cập nhật ngầm qua PowerShell và thoát ứng dụng hiện tại."""
    cmd = [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-WindowStyle",
        "Hidden",
        "-File",
        str(plan.script_path),
    ]
    # cwd của app thường là thư mục cài đặt (shortcut đặt "Start in" = {app}); nếu PowerShell kế thừa
    # cwd đó, chính nó sẽ khoá thư mục và lệnh đổi tên thành `.old` luôn thất bại.
    subprocess.Popen(
        cmd,
        cwd=str(plan.script_path.parent),
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        close_fds=True,
    )


def cleanup_previous_update() -> None:
    """Dọn dẹp thư mục `.old` và các tệp tạm sau khi cập nhật thành công."""
    inst = current_install_dir()
    if inst is not None:
        old_dir = Path(f"{inst}.old")
        if old_dir.is_dir():
            try:
                shutil.rmtree(old_dir, ignore_errors=True)
            except OSError:
                pass
    staging = updates_dir() / STAGING_DIR_NAME
    if staging.is_dir():
        try:
            shutil.rmtree(staging, ignore_errors=True)
        except OSError:
            pass
