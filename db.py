import sqlite3
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class Database:
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self):
        """Initialize the database schema and indexes."""
        # Read schema
        schema_path = Path("sql/schema.sql")
        indexes_path = Path("sql/indexes.sql")

        try:
            with open(schema_path, "r", encoding="utf-8") as f:
                schema_sql = f.read()
            self.conn.executescript(schema_sql)

            if indexes_path.exists():
                with open(indexes_path, "r", encoding="utf-8") as f:
                    indexes_sql = f.read()
                self.conn.executescript(indexes_sql)

            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to initialize database: {e}")
            raise

    def get_connection(self):
        return self.conn

    def close(self):
        if self.conn:
            self.conn.close()

    def batch_insert_files(self, files_data):
        """
        Batch insert into the files table.
        files_data is a list of tuples corresponding to:
        (path, size, extension, mime_type, sha256_hash, mtime, encoding, first_bytes, is_text, file_category, scan_timestamp)
        """
        query = """
        INSERT INTO files (path, size, extension, mime_type, sha256_hash, mtime, encoding, first_bytes, is_text, file_category, scan_timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(path) DO UPDATE SET
            size = excluded.size,
            extension = excluded.extension,
            mime_type = excluded.mime_type,
            sha256_hash = excluded.sha256_hash,
            mtime = excluded.mtime,
            encoding = excluded.encoding,
            first_bytes = excluded.first_bytes,
            is_text = excluded.is_text,
            file_category = excluded.file_category,
            scan_timestamp = excluded.scan_timestamp;
        """
        try:
            cursor = self.conn.cursor()
            cursor.executemany(query, files_data)
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Batch insert files failed: {e}")
            self.conn.rollback()

    def insert_processing_log(self, file_id, stage, status, error_message, details, created_at):
        query = """
        INSERT INTO processing_logs (file_id, stage, status, error_message, details, created_at)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (file_id, stage, status, error_message, details, created_at))
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Insert processing log failed: {e}")
            self.conn.rollback()

    def get_file_by_path(self, path):
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM files WHERE path = ?", (path,))
        return cursor.fetchone()
