CREATE TABLE IF NOT EXISTS files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    size INTEGER NOT NULL,
    extension TEXT,
    mime_type TEXT,
    sha256_hash TEXT NOT NULL,
    mtime REAL NOT NULL,
    encoding TEXT,
    first_bytes BLOB,
    is_text BOOLEAN,
    file_category TEXT,
    type_detected TEXT,
    type_confidence REAL,
    scan_timestamp REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_file_id INTEGER NOT NULL,
    source_type TEXT,
    event_type TEXT,
    direction TEXT,
    timestamp_utc TEXT,
    duration_sec INTEGER,
    phone_a TEXT,
    phone_b TEXT,
    contact_name_raw TEXT,
    message_text TEXT,
    raw_data_json TEXT,
    row_fingerprint TEXT UNIQUE,
    FOREIGN KEY (source_file_id) REFERENCES files(id)
);

CREATE TABLE IF NOT EXISTS processing_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id INTEGER,
    stage TEXT NOT NULL,
    status TEXT NOT NULL,
    error_message TEXT,
    details TEXT,
    created_at REAL NOT NULL,
    FOREIGN KEY (file_id) REFERENCES files(id)
);

-- Note: The indexes mentioned in the prompt are to be created in indexes.sql,
-- but we might create them here or have a separate file. For now, we put the schema here.
