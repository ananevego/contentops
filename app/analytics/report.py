"""CLI entry point: python -m app.analytics.report [--output-dir artifacts]."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.analytics.data import create_charts, load_content_frame, summary, trends


def build_analytics_report(output_dir: Path | str = "artifacts") -> dict:
    frame = load_content_frame()
    return {"summary": summary(frame), "trends": trends(frame), "charts": create_charts(frame, output_dir)}


def main() -> None:
    parser = argparse.ArgumentParser(description="Builds the safe ContentOps analytics report.")
    parser.add_argument("--output-dir", default="artifacts", help="Directory for generated PNG files")
    args = parser.parse_args()
    print(json.dumps(build_analytics_report(args.output_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
