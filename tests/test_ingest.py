"""FileIngester: format detection, recursion, hidden-file skipping."""

from __future__ import annotations

from pathlib import Path

import pytest

from agentic_onboard.ingest import FileIngester
from agentic_onboard.schemas import DocumentFormat


class TestFileIngester:
    def test_detects_email_format(self, tmp_path: Path) -> None:
        (tmp_path / "msg.eml").write_text("From: a@b.example\n\nhi", encoding="utf-8")
        docs = list(FileIngester(tmp_path).list_documents())
        assert len(docs) == 1
        assert docs[0].format is DocumentFormat.EMAIL

    def test_detects_json_blob(self, tmp_path: Path) -> None:
        (tmp_path / "rec.json").write_text('{"x":1}', encoding="utf-8")
        docs = list(FileIngester(tmp_path).list_documents())
        assert docs[0].format is DocumentFormat.JSON_BLOB

    def test_detects_ocr_double_extension(self, tmp_path: Path) -> None:
        (tmp_path / "scan.ocr.json").write_text('{"x":1}', encoding="utf-8")
        docs = list(FileIngester(tmp_path).list_documents())
        assert docs[0].format is DocumentFormat.SCANNED_OCR

    def test_unknown_extension_falls_back_to_freeform(self, tmp_path: Path) -> None:
        (tmp_path / "weird.xyz").write_text("blob", encoding="utf-8")
        docs = list(FileIngester(tmp_path).list_documents())
        assert docs[0].format is DocumentFormat.FREEFORM_TEXT

    def test_hidden_files_skipped(self, tmp_path: Path) -> None:
        (tmp_path / ".hidden").write_text("secret", encoding="utf-8")
        (tmp_path / "visible.txt").write_text("hi", encoding="utf-8")
        docs = list(FileIngester(tmp_path).list_documents())
        assert len(docs) == 1
        assert docs[0].source_id == "visible.txt"

    def test_zero_byte_files_skipped(self, tmp_path: Path) -> None:
        (tmp_path / "empty.txt").touch()
        (tmp_path / "real.txt").write_text("hi", encoding="utf-8")
        docs = list(FileIngester(tmp_path).list_documents())
        assert [d.source_id for d in docs] == ["real.txt"]

    def test_recursive_walk(self, tmp_path: Path) -> None:
        (tmp_path / "sub").mkdir()
        (tmp_path / "a.txt").write_text("a", encoding="utf-8")
        (tmp_path / "sub" / "b.txt").write_text("b", encoding="utf-8")
        docs = list(FileIngester(tmp_path).list_documents())
        assert sorted(d.source_id for d in docs) == ["a.txt", "sub/b.txt"]

    def test_missing_root_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            FileIngester(tmp_path / "does-not-exist")

    def test_file_path_not_allowed_as_root(self, tmp_path: Path) -> None:
        f = tmp_path / "file.txt"
        f.write_text("hi", encoding="utf-8")
        with pytest.raises(NotADirectoryError):
            FileIngester(f)
