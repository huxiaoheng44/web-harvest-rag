"""
Run the end-to-end ingestion pipeline.

Usage:
    python pipeline.py
    python pipeline.py --test
    python pipeline.py --reset-index
    python pipeline.py --skip-scrape
"""

import argparse
import subprocess
from pathlib import Path

BASE_DIR = Path(__file__).parent


def run(command: list[str]):
    print(f"\n$ {' '.join(command)}")
    subprocess.run(command, cwd=BASE_DIR, check=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--test", action="store_true", help="Run the scraper in test mode before indexing")
    parser.add_argument("--reset-index", action="store_true", help="Reset the vector table before indexing")
    parser.add_argument("--skip-scrape", action="store_true", help="Reuse the existing knowledge base JSON")
    args = parser.parse_args()

    if not args.skip_scrape:
        scrape_command = ["python", "scraper.py"]
        if args.test:
            scrape_command.append("--test")
        run(scrape_command)

    index_command = ["python", "build_index.py"]
    if args.reset_index:
        index_command.append("--reset")
    run(index_command)
