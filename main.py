import argparse
import logging
import time
import sys
from pathlib import Path
from datetime import datetime

from db import Database
from scanner import Scanner

def setup_logging(log_dir: str):
    """Setup standard text logging format for console and file."""
    Path(log_dir).mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = Path(log_dir) / f"run_{timestamp}.log"

    formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] [%(module)s] %(message)s")

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    logging.basicConfig(
        level=logging.INFO,
        handlers=[file_handler, console_handler]
    )

def main():
    parser = argparse.ArgumentParser(description="Data Engineering Pipeline for deterministic analysis")
    parser.add_argument("--root", type=str, default="/data", help="Root directory to scan")
    parser.add_argument("--db", type=str, default="./data.db", help="Path to SQLite database")
    parser.add_argument("--rescan", action="store_true", help="Force rescan of all files")
    parser.add_argument("--only-scan", action="store_true", help="Only run the scan stage")
    parser.add_argument("--only-parse", action="store_true", help="Only run the parse stage (not implemented yet)")

    args = parser.parse_args()

    setup_logging("logs")
    logger = logging.getLogger(__name__)

    logger.info("Starting Data Engineering Pipeline")
    logger.info(f"Configuration: root={args.root}, db={args.db}")

    try:
        db = Database(args.db)

        # 1. Scan Stage
        if not args.only_parse:
            logger.info("Starting Stage 1: SCAN")
            scanner = Scanner(db, args.root)
            scanner.scan(force_rescan=args.rescan)

        if args.only_scan:
            logger.info("Stopping after scan stage due to --only-scan")
            return

        # Placeholders for future stages
        logger.info("Starting Stage 2: CLASSIFY (Not implemented yet)")
        logger.info("Starting Stage 3: PARSE (Not implemented yet)")
        logger.info("Starting Stage 4: NORMALIZE (Not implemented yet)")
        logger.info("Starting Stage 5: DEDUPE (Not implemented yet)")

        logger.info("Pipeline completed successfully.")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
    finally:
        if 'db' in locals():
            db.close()

if __name__ == "__main__":
    main()
