#!/usr/bin/env python3
"""Batch image generation — runs generate.py sequentially for n variations."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent


def main():
    parser = argparse.ArgumentParser(description="Generate n variations of a prompt")
    parser.add_argument("--prompt", required=True, help="Base image prompt")
    parser.add_argument("--count", type=int, default=4, help="Number of variations")
    parser.add_argument("--aspect-ratio", default="1:1")
    parser.add_argument("--resolution", default="2K")
    parser.add_argument("--model", default="gemini-3.1-flash-image-preview")
    parser.add_argument("--api-key", help="Google AI API key")
    parser.add_argument("--dry-run", action="store_true", help="Show cost estimate only")
    args = parser.parse_args()

    price_per = {"512": 0.020, "1K": 0.039, "2K": 0.078, "4K": 0.156}.get(args.resolution, 0.039)
    total_est = price_per * args.count
    print(f"Batch: {args.count} images @ ${price_per:.3f} each = ${total_est:.3f} estimated")

    if args.dry_run:
        print("Dry run — no images generated.")
        return

    results = []
    for i in range(1, args.count + 1):
        print(f"\n[{i}/{args.count}] Generating variation {i}...")
        cmd = [
            sys.executable,
            str(SCRIPT_DIR / "generate.py"),
            "--prompt", args.prompt,
            "--aspect-ratio", args.aspect_ratio,
            "--resolution", args.resolution,
            "--model", args.model,
        ]
        if args.api_key:
            cmd += ["--api-key", args.api_key]

        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.returncode != 0:
            print(f"  ERROR: {result.stderr.strip()}", file=sys.stderr)
            continue

        try:
            data = json.loads(result.stdout)
            results.append(data)
            print(f"  Saved: {data['image_path']}")

            log_cmd = [
                sys.executable,
                str(SCRIPT_DIR / "cost_tracker.py"),
                "log",
                "--model", args.model,
                "--resolution", args.resolution,
                "--prompt", args.prompt[:80],
            ]
            subprocess.run(log_cmd, capture_output=True)
        except json.JSONDecodeError:
            print(f"  Unexpected output: {result.stdout}", file=sys.stderr)

    print(f"\nBatch complete: {len(results)}/{args.count} images generated.")
    for r in results:
        print(f"  {r['image_path']}")


if __name__ == "__main__":
    main()
