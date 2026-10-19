from __future__ import annotations

import math
import zipfile
from dataclasses import dataclass
from pathlib import Path

from .extractors import normalized_extension

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
ZIP_MAGIC = b"PK\x03\x04"
OFFICE_EXTS = {".docx", ".xlsx", ".pptx"}


@dataclass
class ProtectionResult:
    # ok | encrypted | suspected | permission
    state: str
    kind: str | None = None
    detail: str = ""
    error: str | None = None

    @property
    def blocks_indexing(self) -> bool:
        return self.state in ("encrypted", "suspected")


def _entropy(data: bytes) -> float:
    if not data:
        return 0.0
    counts = [0] * 256
    for byte in data:
        counts[byte] += 1
    total = len(data)
    value = 0.0
    for count in counts:
        if count:
            p = count / total
            value -= p * math.log2(p)
    return value


def _office_probe(path: Path, head: bytes) -> ProtectionResult:
    if head.startswith(ZIP_MAGIC):
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                if "EncryptionInfo" in names or "EncryptedPackage" in names:
                    return ProtectionResult(
                        "encrypted", "office_encrypted_zip", "检测到 Office 加密包"
                    )
                if "[Content_Types].xml" not in names:
                    return ProtectionResult(
                        "suspected",
                        "office_unexpected_zip",
                        "Office 文件缺少 OOXML 结构，疑似受保护或已损坏",
                    )
                # ZIP entries themselves can be encrypted by some DLP tools.
                for info in archive.infolist():
                    if info.flag_bits & 0x1:
                        return ProtectionResult(
                            "encrypted", "zip_encrypted", "ZIP 内容已加密"
                        )
        except (zipfile.BadZipFile, OSError):
            return ProtectionResult(
                "suspected", "office_bad_zip", "无法读取 Office 文件内容，疑似受保护"
            )
        return ProtectionResult("ok")

    if head.startswith(OLE_MAGIC):
        try:
            import olefile

            with olefile.OleFileIO(str(path)) as ole:
                names = {
                    "/".join(item).lower() for item in ole.listdir(streams=True, storages=True)
                }
                if "encryptioninfo" in names or "encryptedpackage" in names:
                    return ProtectionResult(
                        "encrypted", "office_password", "检测到 Office 密码加密容器"
                    )
        except Exception:
            pass
        return ProtectionResult(
            "suspected",
            "office_ole_container",
            "Office 扩展名对应 OLE 容器，可能是加密文档或旧格式",
        )

    if _entropy(head) >= 7.2:
        return ProtectionResult(
            "suspected", "high_entropy", "文件头无法识别且熵较高，疑似受保护或加密"
        )
    return ProtectionResult("ok")


def _pdf_probe(path: Path, head: bytes) -> ProtectionResult:
    if b"%PDF-" not in head[:1024]:
        if _entropy(head) >= 7.2:
            return ProtectionResult(
                "suspected", "pdf_unrecognized", "PDF 文件头无法识别，疑似受保护"
            )
        return ProtectionResult("ok")
    try:
        import pymupdf

        document = pymupdf.open(str(path))
        try:
            if document.needs_pass:
                return ProtectionResult(
                    "encrypted", "pdf_password", "PDF 需要密码或权限密码"
                )
        finally:
            document.close()
    except Exception as exc:
        text = str(exc).lower()
        if any(token in text for token in ("password", "encrypted", "decrypt", "密码", "加密")):
            return ProtectionResult("encrypted", "pdf_password", "PDF 无法解密")
        return ProtectionResult(
            "suspected", "pdf_unreadable", f"PDF 无法打开：{exc}"
        )
    return ProtectionResult("ok")


def probe_file(path: Path) -> ProtectionResult:
    """Inspect a file's container without attempting to decrypt its contents."""
    try:
        size = path.stat().st_size
        if size == 0:
            return ProtectionResult("ok")
        with path.open("rb") as fh:
            head = fh.read(4096)
    except PermissionError as exc:
        return ProtectionResult("permission", error=str(exc))
    except OSError as exc:
        return ProtectionResult("permission", error=str(exc))

    ext = normalized_extension(path)
    if ext in OFFICE_EXTS:
        return _office_probe(path, head)
    if ext == ".pdf":
        return _pdf_probe(path, head)
    return ProtectionResult("ok")


def is_encryption_exception(exc: BaseException) -> bool:
    text = f"{type(exc).__name__}: {exc}".lower()
    return any(
        token in text
        for token in (
            "password",
            "encrypted",
            "encrypt",
            "decrypt",
            "需要密码",
            "密码",
            "加密",
        )
    )


def classify_probe_result(result: ProtectionResult) -> dict[str, str | None]:
    return {
        "status": {
            "encrypted": "encrypted",
            "suspected": "encrypted_suspected",
        }.get(result.state, "failed"),
        "kind": result.kind,
        "detail": result.detail or result.error or "",
    }
