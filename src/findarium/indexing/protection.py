from __future__ import annotations

import math
import zipfile
from dataclasses import dataclass
from pathlib import Path

from ..i18n import msg
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
                        "encrypted", "office_encrypted_zip", msg("protect.office_encrypted_zip")
                    )
                if "[Content_Types].xml" not in names:
                    return ProtectionResult(
                        "suspected",
                        "office_unexpected_zip",
                        msg("protect.office_unexpected_zip"),
                    )
                # ZIP entries themselves can be encrypted by some DLP tools.
                for info in archive.infolist():
                    if info.flag_bits & 0x1:
                        return ProtectionResult(
                            "encrypted", "zip_encrypted", msg("protect.zip_encrypted")
                        )
        except (zipfile.BadZipFile, OSError):
            return ProtectionResult(
                "suspected", "office_bad_zip", msg("protect.office_bad_zip")
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
                        "encrypted", "office_password", msg("protect.office_password")
                    )
        except Exception:
            pass
        return ProtectionResult(
            "suspected",
            "office_ole_container",
            msg("protect.office_ole_container"),
        )

    if _entropy(head) >= 7.2:
        return ProtectionResult(
            "suspected", "high_entropy", msg("protect.high_entropy")
        )
    return ProtectionResult("ok")


def _pdf_probe(path: Path, head: bytes) -> ProtectionResult:
    if b"%PDF-" not in head[:1024]:
        if _entropy(head) >= 7.2:
            return ProtectionResult(
                "suspected", "pdf_unrecognized", msg("protect.pdf_unrecognized")
            )
        return ProtectionResult("ok")
    try:
        import pymupdf

        document = pymupdf.open(str(path))
        try:
            if document.needs_pass:
                return ProtectionResult(
                    "encrypted", "pdf_password", msg("protect.pdf_password")
                )
        finally:
            document.close()
    except Exception as exc:
        text = str(exc).lower()
        if any(token in text for token in ("password", "encrypted", "decrypt", "密码", "加密")):
            return ProtectionResult("encrypted", "pdf_password", msg("protect.pdf_no_decrypt"))
        return ProtectionResult(
            "suspected", "pdf_unreadable", msg("protect.pdf_unreadable", error=str(exc))
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
