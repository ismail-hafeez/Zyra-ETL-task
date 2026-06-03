"""
CLI entry point for the Zyra ETL pipeline.

Usage:
    python -m src.main --url https://www.bucknell.edu
    python -m src.main --file data/university_domains.txt
    python -m src.main --all
"""

import argparse
import logging
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pipeline import run_pipeline, run_batch
from src.utils import get_domain


def setup_logging():
    """Configure structured logging to console."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Zyra ETL Pipeline — Extract university admissions and tuition data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
            Examples:
            python -m src.main --url https://www.bucknell.edu
            python -m src.main --file data/university_domains.txt
            python -m src.main --all
        """,
    )

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--url",
        type=str,
        help="Process a single university domain URL",
    )
    group.add_argument(
        "--file",
        type=str,
        help="Process all domains listed in a text file (one URL per line)",
    )
    group.add_argument(
        "--all",
        action="store_true",
        help="Process all domains from data/university_domains.txt",
    )

    args = parser.parse_args()
    setup_logging()

    logger = logging.getLogger(__name__)

    if args.url:
        # Single university
        logger.info(f"Processing single domain: {args.url}")
        result = run_pipeline(args.url)
        _print_summary([result])

    elif args.file:
        # From a custom file
        filepath = os.path.abspath(args.file)
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            sys.exit(1)

        with open(filepath, 'r') as f:
            urls = [line.strip() for line in f if line.strip()]

        logger.info(f"Processing {len(urls)} domains from {filepath}")
        results = run_batch(urls)
        _print_summary(results)

    elif args.all:
        # From default domains file
        urls = list(get_domain())
        logger.info(f"Processing all {len(urls)} domains from default file")
        results = run_batch(urls)
        _print_summary(results)


def _print_summary(results: list):
    """Print a human-readable execution summary to console."""
    print("\n" + "=" * 60)
    print("EXECUTION SUMMARY")
    print("=" * 60)

    for r in results:
        status = "✓ SUCCESS" if r.success else "✗ FAILED"
        name = r.university_name or "Unknown"

        print(f"\n{status}: {name}")
        print(f"  Domain:       {r.domain_url}")
        print(f"  Pages found:  {r.pages_discovered}")
        print(f"  Pages used:   {r.pages_fetched}")
        print(f"  Tuition items:{r.tuition_items}")
        print(f"  Deadlines:    {r.deadlines}")
        print(f"  Fields:       {r.fields_populated}/{r.fields_total} populated")
        print(f"  Time:         {r.elapsed_time:.1f}s")

        if r.output_file:
            print(f"  Output:       {r.output_file}")

        if r.quality_warnings:
            print(f"  Warnings:")
            for w in r.quality_warnings:
                print(f"    ⚠ {w}")

        if r.error:
            print(f"  Error:        {r.error}")

    print("\n" + "=" * 60)
    total = len(results)
    passed = sum(1 for r in results if r.success)
    print(f"Total: {passed}/{total} succeeded")
    print("=" * 60)


if __name__ == "__main__":
    main()