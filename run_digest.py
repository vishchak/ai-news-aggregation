#!/usr/bin/env python3
"""
News Digest Agent - CLI Entry Point

Runs the LangGraph agent to fetch, score, and deliver a personalized news digest.

Usage:
    python run_digest.py                    # Full run, sends email
    python run_digest.py --dry-run          # Preview only, no email
    python run_digest.py --dry-run --test   # Process only 3 articles
"""

import argparse
import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent / "src"))

from agent import run_pipeline


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the digest run."""
    log_level = logging.DEBUG if verbose else logging.INFO

    # Create logs directory if needed
    log_dir = Path(__file__).parent / "logs"
    log_dir.mkdir(exist_ok=True)

    # Log file with date
    log_file = log_dir / f"digest_{datetime.now().strftime('%Y%m%d')}.log"

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(log_file),
        ],
    )


def main():
    parser = argparse.ArgumentParser(
        description="Generate and send personalized news digest",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_digest.py --dry-run          Preview digest without sending
    python run_digest.py --dry-run --test   Quick test with 3 articles
    python run_digest.py                    Full run with email delivery

Requirements:
    - Ollama running: ollama serve
    - Model installed: ollama pull llama3.1:8b
    - Email config in .env: GMAIL_USER, GMAIL_APP_PASSWORD, EMAIL_RECIPIENT
        """,
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate digest but don't send email",
    )

    parser.add_argument(
        "--test",
        action="store_true",
        help="Process only 3 articles (for quick testing)",
    )

    parser.add_argument(
        "--min-score",
        type=float,
        default=6.0,
        help="Minimum relevance score 1-10 (default: 6.0)",
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable debug logging",
    )

    parser.add_argument(
        "--output",
        type=str,
        help="Save digest to file (markdown)",
    )

    args = parser.parse_args()

    setup_logging(args.verbose)
    logger = logging.getLogger(__name__)

    logger.info("=" * 60)
    logger.info("NEWS DIGEST AGENT")
    logger.info("=" * 60)

    if args.dry_run:
        logger.info("Mode: DRY RUN (no email)")
    if args.test:
        logger.info("Mode: TEST (3 articles only)")

    # Run the pipeline
    try:
        result = asyncio.run(run_pipeline(
            dry_run=args.dry_run,
            min_score=args.min_score,
            max_articles=3 if args.test else None,
        ))
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(130)
    except Exception as e:
        logger.error(f"Pipeline failed: {e}")
        sys.exit(1)

    # Check for errors
    if result.get("error"):
        logger.error(f"Error: {result['error']}")
        sys.exit(1)

    # Print stats
    stats = result.get("stats", {})
    logger.info("-" * 60)
    logger.info("RESULTS")
    logger.info("-" * 60)
    logger.info(f"Articles fetched:   {stats.get('fetched', 0)}")
    logger.info(f"After dedup:        {stats.get('after_dedupe', 0)}")
    logger.info(f"Passed filter:      {stats.get('passed_filter', 0)}")
    logger.info(f"Email sent:         {stats.get('email_sent', False)}")

    # Save to file if requested
    if args.output:
        output_path = Path(args.output)
        output_path.write_text(result.get("digest_markdown", ""))
        logger.info(f"Saved to: {output_path}")

    # Print preview in dry-run mode
    if args.dry_run:
        print("\n" + "=" * 60)
        print("DIGEST PREVIEW")
        print("=" * 60 + "\n")
        print(result.get("digest_markdown", "No content"))

    logger.info("Done!")


if __name__ == "__main__":
    main()
