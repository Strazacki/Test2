CREATE INDEX IF NOT EXISTS idx_events_timestamp_utc ON events(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_events_phone_a ON events(phone_a);
CREATE INDEX IF NOT EXISTS idx_events_phone_b ON events(phone_b);
CREATE INDEX IF NOT EXISTS idx_files_type_detected ON files(type_detected);
CREATE INDEX IF NOT EXISTS idx_files_sha256_hash ON files(sha256_hash);
