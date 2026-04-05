import os
import hashlib
import mimetypes
import logging
import time
from pathlib import Path
from charset_normalizer import from_bytes

logger = logging.getLogger(__name__)

class Scanner:
    def __init__(self, db, root_dir: str, batch_size: int = 1000):
        self.db = db
        self.root_dir = Path(root_dir)
        self.batch_size = batch_size

    def scan(self, force_rescan: bool = False):
        """Recursively scan files in root_dir."""
        logger.info(f"Starting scan of {self.root_dir} (force_rescan={force_rescan})")
        batch = []
        scan_timestamp = time.time()
        files_scanned = 0
        files_skipped = 0

        # Initialize mimetypes
        mimetypes.init()

        for dirpath, dirnames, filenames in os.walk(self.root_dir):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                str_path = str(file_path.absolute())

                try:
                    stat = file_path.stat()
                    mtime = stat.st_mtime
                    size = stat.st_size

                    # Idempotency check: if not force rescan, see if it already exists and is unchanged
                    if not force_rescan:
                        existing = self.db.get_file_by_path(str_path)
                        if existing and existing['mtime'] == mtime and existing['size'] == size:
                            files_skipped += 1
                            continue

                    extension = file_path.suffix.lower() if file_path.suffix else None
                    mime_type, _ = mimetypes.guess_type(str_path)

                    sha256_hash = self._calculate_hash(file_path)
                    first_bytes = self._get_first_bytes(file_path)
                    encoding = self._detect_encoding(first_bytes)

                    is_text = self._is_text(mime_type, encoding)
                    file_category = self._determine_category(extension, mime_type, is_text)

                    batch.append((
                        str_path, size, extension, mime_type, sha256_hash,
                        mtime, encoding, first_bytes, is_text, file_category, scan_timestamp
                    ))
                    files_scanned += 1

                    if len(batch) >= self.batch_size:
                        self.db.batch_insert_files(batch)
                        batch = []
                        logger.debug(f"Inserted batch of {self.batch_size} files")

                except (PermissionError, OSError) as e:
                    logger.warning(f"Failed to access file {str_path}: {e}")
                    self.db.insert_processing_log(
                        file_id=None,
                        stage="scan",
                        status="error",
                        error_message=str(e),
                        details=f"File: {str_path}",
                        created_at=time.time()
                    )
                except Exception as e:
                    logger.error(f"Unexpected error processing file {str_path}: {e}")

        # Insert remaining
        if batch:
            self.db.batch_insert_files(batch)

        logger.info(f"Scan complete. Scanned: {files_scanned}, Skipped: {files_skipped}")
        return files_scanned

    def _calculate_hash(self, file_path: Path) -> str:
        """Calculate SHA256 hash of a file."""
        h = hashlib.sha256()
        try:
            with open(file_path, "rb") as f:
                while chunk := f.read(8192):
                    h.update(chunk)
        except OSError:
            return ""
        return h.hexdigest()

    def _get_first_bytes(self, file_path: Path, num_bytes: int = 512) -> bytes:
        """Read the first N bytes of a file."""
        try:
            with open(file_path, "rb") as f:
                return f.read(num_bytes)
        except OSError:
            return b""

    def _detect_encoding(self, first_bytes: bytes) -> str:
        """Detect text encoding using charset_normalizer on the first bytes."""
        if not first_bytes:
            return None

        try:
            result = from_bytes(first_bytes).best()
            return result.encoding if result else None
        except Exception:
            return None

    def _is_text(self, mime_type: str, encoding: str) -> bool:
        """Determine if a file is likely text."""
        if mime_type and mime_type.startswith("text/"):
            return True
        if mime_type in ["application/json", "application/xml", "application/csv"]:
            return True
        if encoding is not None:
            return True
        return False

    def _determine_category(self, extension: str, mime_type: str, is_text: bool) -> str:
        """Determine preliminary file category."""
        ext = extension or ""
        mime = mime_type or ""

        if ext in [".xls", ".xlsx"] or "spreadsheet" in mime or "excel" in mime:
            return "excel"
        if ext in [".csv", ".tsv"] or "csv" in mime:
            return "csv_like"
        if is_text:
            return "text"
        return "binary"
