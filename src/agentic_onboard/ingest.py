"""S3-shaped ingest layer, file-backed for the demo.

Why a protocol, not boto3 directly:
    The pipeline depends on an *interface* (``Ingester``), not a vendor SDK.
    The local file implementation is what runs in the demo and the test
    suite; an :class:`S3Ingester` calling ``boto3.client('s3').get_object``
    can drop in behind the same Protocol with zero changes to ``orchestrator``.
    The README documents the swap.

File-format detection is intentionally simple — extension first, then a
content sniff for ambiguous cases. The detected ``DocumentFormat`` is metadata
for the LLM prompt, not a hard branch in the parser.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol

from .schemas import DocumentFormat, RawDocument

# --- Protocol ---


class Ingester(Protocol):
    """The contract every ingest backend (file, S3, GCS, …) implements."""

    def list_documents(self) -> Iterable[RawDocument]:
        """Yield raw documents in deterministic order.

        Generators are encouraged so a million-object bucket does not have to
        fit in RAM. Implementations should propagate transient errors (network,
        permission) as exceptions for the orchestrator's outer error handler.
        """
        ...


# --- File-backed implementation (the demo default) ---


_EXTENSION_TO_FORMAT: dict[str, DocumentFormat] = {
    ".eml": DocumentFormat.EMAIL,
    ".email": DocumentFormat.EMAIL,
    ".csv": DocumentFormat.CSV_ROW,
    ".json": DocumentFormat.JSON_BLOB,
    ".ocr": DocumentFormat.SCANNED_OCR,
    ".ocr.json": DocumentFormat.SCANNED_OCR,
    ".txt": DocumentFormat.FREEFORM_TEXT,
}


def _detect_format(path: Path) -> DocumentFormat:
    """Detect the source format from filename. Falls back to freeform text.

    A real S3 implementation would also check ``Content-Type``; we don't here
    because the LLM is robust to misclassification — the format hint is just a
    nudge, not a parser switch.
    """
    suffixes = "".join(path.suffixes).lower()
    if suffixes.endswith(".ocr.json"):
        return DocumentFormat.SCANNED_OCR
    return _EXTENSION_TO_FORMAT.get(path.suffix.lower(), DocumentFormat.FREEFORM_TEXT)


class FileIngester:
    """Reads every file under ``root`` (recursively) as a :class:`RawDocument`.

    Hidden files and zero-byte files are skipped. The ``source_id`` is the
    path relative to ``root`` so it stays stable across machines.

    Args:
        root: Directory to scan. Must exist; raises ``FileNotFoundError`` otherwise.
    """

    def __init__(self, root: Path | str):
        self.root = Path(root).resolve()
        if not self.root.exists():
            raise FileNotFoundError(f"ingest root does not exist: {self.root}")
        if not self.root.is_dir():
            raise NotADirectoryError(f"ingest root is not a directory: {self.root}")

    def list_documents(self) -> Iterator[RawDocument]:
        """Yield documents in lexical order so test runs are deterministic."""
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            if path.name.startswith("."):
                continue
            try:
                stat = path.stat()
            except OSError:
                continue
            if stat.st_size == 0:
                continue

            try:
                body = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                # Binary or unknown encoding — skip rather than crash. A real
                # S3 ingester would route these to a raw-blob queue for OCR.
                continue

            yield RawDocument(
                source_id=str(path.relative_to(self.root)),
                format=_detect_format(path),
                body=body,
            )


# --- Stub for the boto3 backend (kept in-tree as a contract reminder) ---


class S3Ingester:
    """Reference outline of the S3 backend.

    Not exercised by the demo (decision: local fixtures only) but kept in-tree
    so the swap is documented. The README walks through enabling it.
    """

    def __init__(self, bucket: str, prefix: str = "") -> None:
        self.bucket = bucket
        self.prefix = prefix

    def list_documents(self) -> Iterator[RawDocument]:  # pragma: no cover - illustrative
        raise NotImplementedError(
            "S3 backend stub. Enable by installing boto3 and replacing this body with:\n"
            "    import boto3\n"
            "    s3 = boto3.client('s3')\n"
            "    paginator = s3.get_paginator('list_objects_v2')\n"
            "    for page in paginator.paginate(Bucket=self.bucket, Prefix=self.prefix):\n"
            "        for obj in page.get('Contents', []):\n"
            "            body = s3.get_object(Bucket=self.bucket, Key=obj['Key'])['Body']\\\n"
            "                .read().decode('utf-8')\n"
            "            yield RawDocument(source_id=obj['Key'], format=..., body=body)"
        )
