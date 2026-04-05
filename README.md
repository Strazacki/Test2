# Deterministic Data Engineering Pipeline

A modular, offline-first, pure Python data engineering pipeline for scanning, classifying, parsing, normalizing, and deduplicating data. Designed to work on Debian CLI without AI or LLMs.

## Requirements
- Python 3.9+
- SQLite3 (built-in)
- Dependencies: pandas, openpyxl, charset_normalizer

## Installation

1. Clone the repository.
2. It's recommended to create a virtual environment:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. Install the dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the pipeline using `main.py`. The pipeline operates on a local directory of files.

```bash
# Full pipeline run
python main.py --root /data --db ./data.db

# Force rescan of all files
python main.py --root /data --db ./data.db --rescan

# Run only the scanning stage
python main.py --root /data --db ./data.db --only-scan
```

## Workflow Overview

1. **Scan**: Recursively scans the target directory (`--root`). Hashes files, detects encoding using `charset_normalizer`, and stores metadata in the `files` table. Is idempotent by checking file size and modification time.
2. **Classify**: (To be implemented) Classifies files based on extension, headers, content, and heuristic signatures.
3. **Parse**: (To be implemented) Parses different formats (CSV, Excel, Text) handling errors gracefully line-by-line or chunk-by-chunk.
4. **Normalize**: (To be implemented) Normalizes phone numbers, dates (to UTC ISO8601), and event types.
5. **Deduplicate**: (To be implemented) Deduplicates records across sources preserving the richest record on conflict.

## Database Schema (SQLite)

- `files`: Stores metadata about discovered files.
- `events`: Stores normalized communication events. Unique by `row_fingerprint` (based on normalized fields).
- `processing_logs`: Stores row-level or file-level processing errors.

## Limitations

- Designed strictly for offline execution.
- Text parsing relies heavily on regular expressions and heuristics.
- Performance relies on SQLite batch operations; memory constraints exist for massive chunk processing.
