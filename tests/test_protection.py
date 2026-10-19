from __future__ import annotations

from pathlib import Path

import pymupdf
from docx import Document

from findarium.indexing.protection import probe_file

OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"


def test_normal_docx_is_ok(tmp_path: Path):
    path = tmp_path / "normal.docx"
    document = Document()
    document.add_paragraph("项目合同")
    document.save(str(path))
    assert probe_file(path).state == "ok"


def test_ole_magic_office_is_suspected(tmp_path: Path):
    path = tmp_path / "locked.docx"
    path.write_bytes(OLE_MAGIC + b"\x00" * 4096)
    result = probe_file(path)
    assert result.state in ("encrypted", "suspected")


def test_encrypted_pdf_is_detected(tmp_path: Path):
    path = tmp_path / "secret.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "secret")
    document.save(
        str(path),
        encryption=pymupdf.PDF_ENCRYPT_AES_256,
        user_pw="pw",
        owner_pw="pw",
    )
    document.close()
    result = probe_file(path)
    assert result.state == "encrypted"
    assert result.kind == "pdf_password"


def test_plain_pdf_is_ok(tmp_path: Path):
    path = tmp_path / "plain.pdf"
    document = pymupdf.open()
    page = document.new_page()
    page.insert_text((72, 72), "plain text")
    document.save(str(path))
    document.close()
    assert probe_file(path).state == "ok"
