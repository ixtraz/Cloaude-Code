#!/usr/bin/env python3
"""Cost tracking for banana-claude image generation sessions."""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

LEDGER_PATH = Path.home() / ".banana" / "costs.json"

PRICING = {
    # Gemini direct
    "gemini-3.1-flash-image-preview": {"512": 0.020, "1K": 0.039, "2K": 0.078, "4K": 0.156},
    "gemini-2.5-flash-image":         {"512": 0.020, "1K": 0.039, "2K": 0.078, "4K": 0.156},
    # kie.ai models (flat per image, resolution-independent unless noted)
    "nano-banana-pro":   {"512": 0.090, "1K": 0.090, "2K": 0.100, "4K": 0.120},
    "nano-banana-2":     {"512": 0.020, "1K": 0.039, "2K": 0.078, "4K": 0.078},
    "flux-kontext-pro":  {"512": 0.040, "1K": 0.040, "2K": 0.050, "4K": 0.050},
    "flux-kontext-dev":  {"512": 0.025, "1K": 0.025, "2K": 0.030, "4K": 0.030},
    "4o-image":          {"512": 0.040, "1K": 0.040, "2K": 0.080, "4K": 0.160},
    "gpt-image-2":       {"512": 0.030, "1K": 0.050, "2K": 0.100, "4K": 0.190},
    "midjourney":        {"512": 0.030, "1K": 0.030, "2K": 0.050, "4K": 0.050},
    "grok-imagine":      {"512": 0.030, "1K": 0.030, "2K": 0.040, "4K": 0.040},
    "seedream":          {"512": 0.020, "1K": 0.020, "2K": 0.030, "4K": 0.030},
    "seedream-5-lite":   {"512": 0.020, "1K": 0.035, "2K": 0.035, "4K": 0.035},
}
DEFAULT_PRICE = 0.039


def lookup_price(model, resolution, batch=False):
    """Returns estimated cost per image in USD."""
    model_prices = None
    # longest key first so "seedream-5-lite" matches before "seedream"
    for key in sorted(PRICING, key=len, reverse=True):
        if key in model:
            model_prices = PRICING[key]
            break
    price = (model_prices or {}).get(resolution, DEFAULT_PRICE)
    return price * 0.5 if batch else price


def load_ledger():
    if LEDGER_PATH.exists():
        with open(LEDGER_PATH) as f:
            return json.load(f)
    return {"entries": []}


def save_ledger(ledger):
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(LEDGER_PATH, "w") as f:
        json.dump(ledger, f, indent=2)


def cmd_log(args):
    price = lookup_price(args.model, args.resolution, getattr(args, "batch", False))
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "model": args.model,
        "resolution": args.resolution,
        "cost": price,
        "prompt": (args.prompt or "")[:80],
        "batch": getattr(args, "batch", False),
    }
    ledger = load_ledger()
    ledger["entries"].append(entry)
    save_ledger(ledger)
    print(f"Logged: ${price:.3f} ({args.model}, {args.resolution})")


def cmd_summary(args):
    ledger = load_ledger()
    entries = ledger["entries"]
    if not entries:
        print("No entries yet.")
        return
    total = sum(e["cost"] for e in entries)
    print(f"Total entries: {len(entries)}")
    print(f"Total cost:    ${total:.3f}")
    last7 = [e for e in entries if _days_ago(e["timestamp"]) <= 7]
    print(f"Last 7 days:   ${sum(e['cost'] for e in last7):.3f} ({len(last7)} images)")


def cmd_today(args):
    ledger = load_ledger()
    today = [e for e in ledger["entries"] if _days_ago(e["timestamp"]) < 1]
    if not today:
        print("No generations today.")
        return
    total = sum(e["cost"] for e in today)
    print(f"Today: {len(today)} images, ${total:.3f}")
    for e in today:
        ts = e["timestamp"][:16].replace("T", " ")
        print(f"  [{ts}] ${e['cost']:.3f}  {e['model']} {e['resolution']}  {e['prompt'][:40]}")


def cmd_estimate(args):
    price = lookup_price(args.model, args.resolution)
    batch_price = price * 0.5
    total = price * args.count
    batch_total = batch_price * args.count
    print(f"Estimate for {args.count} images ({args.model}, {args.resolution}):")
    print(f"  Standard: ${total:.3f}  (${price:.3f}/img)")
    print(f"  Batch API: ${batch_total:.3f}  (${batch_price:.3f}/img, 50% discount, async)")


def cmd_reset(args):
    if not args.confirm:
        print("Pass --confirm to reset the ledger.", file=sys.stderr)
        sys.exit(1)
    save_ledger({"entries": []})
    print("Ledger reset.")


def _days_ago(iso_ts):
    try:
        ts = datetime.fromisoformat(iso_ts)
        now = datetime.now(timezone.utc)
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        return (now - ts).total_seconds() / 86400
    except Exception:
        return 9999


def main():
    parser = argparse.ArgumentParser(description="Track banana-claude generation costs")
    sub = parser.add_subparsers(dest="command")

    p_log = sub.add_parser("log", help="Log a generation")
    p_log.add_argument("--model", required=True)
    p_log.add_argument("--resolution", required=True, choices=["512", "1K", "2K", "4K"])
    p_log.add_argument("--prompt", default="")
    p_log.add_argument("--batch", action="store_true")

    sub.add_parser("summary", help="Show cost summary")
    sub.add_parser("today", help="Show today's usage")

    p_est = sub.add_parser("estimate", help="Estimate batch cost")
    p_est.add_argument("--model", default="gemini-3.1-flash-image-preview")
    p_est.add_argument("--resolution", default="1K", choices=["512", "1K", "2K", "4K"])
    p_est.add_argument("--count", type=int, default=10)

    p_reset = sub.add_parser("reset", help="Clear ledger")
    p_reset.add_argument("--confirm", action="store_true")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"log": cmd_log, "summary": cmd_summary, "today": cmd_today,
     "estimate": cmd_estimate, "reset": cmd_reset}[args.command](args)


if __name__ == "__main__":
    main()
