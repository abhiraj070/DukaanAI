"""Storage service for uploaded documents with SHA256 integrity validation."""

import hashlib
import os
from pathlib import Path

from app.core.config import get_settings
from app.core.errors import BadRequestError

ALLOWED_EXTENSIONS = {
    ".csv": "CSV",
    ".xlsx": "XLSX",
    ".xls": "XLSX",
    ".pdf": "PDF",
    ".png": "IMAGE",
    ".jpg": "IMAGE",
    ".jpeg": "IMAGE",
    ".txt": "TEXT",
}


class StorageService:
    """Manages secure file storage, integrity hashes, and path resolution."""

    def __init__(self, base_dir: str | None = None) -> None:
        settings = get_settings()
        self.base_dir = Path(base_dir or "storage")
        self.max_bytes = settings.MAX_UPLOAD_MB * 1024 * 1024
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def validate_and_save(
        self, business_id: str, filename: str, content: bytes
    ) -> tuple[str, str, str, int]:
        """Validate file size and extension, calculate SHA256 hash, and persist to disk.

        Returns:
            Tuple of (storage_path, file_type, sha256_hash, file_size_bytes)
        """
        size = len(content)
        if size > self.max_bytes:
            limit_mb = self.max_bytes / (1024 * 1024)
            actual_mb = size / (1024 * 1024)
            raise BadRequestError(f"File size ({actual_mb:.1f}MB) exceeds limit ({limit_mb:.0f}MB)")
        if size == 0:
            raise BadRequestError("Uploaded file is empty")

        ext = Path(filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            allowed = ", ".join(ALLOWED_EXTENSIONS.keys())
            raise BadRequestError(f"Unsupported file format '{ext}'. Supported formats: {allowed}")

        file_type = ALLOWED_EXTENSIONS[ext]
        sha256_hash = hashlib.sha256(content).hexdigest()

        # Isolated directory per tenant business
        tenant_dir = self.base_dir / business_id
        tenant_dir.mkdir(parents=True, exist_ok=True)

        safe_filename = f"{sha256_hash[:16]}_{Path(filename).name}"
        destination = tenant_dir / safe_filename

        with open(destination, "wb") as f:
            f.write(content)

        return str(destination), file_type, sha256_hash, size

    def read_file(self, storage_path: str) -> bytes:
        """Read bytes of a persisted file."""
        if not os.path.exists(storage_path):
            raise BadRequestError("Stored file could not be located on disk")
        with open(storage_path, "rb") as f:
            return f.read()
