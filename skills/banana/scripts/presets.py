#!/usr/bin/env python3
"""Preset management for banana-claude brand/style consistency."""

import argparse
import json
import sys
from pathlib import Path

PRESETS_DIR = Path.home() / ".banana" / "presets"

BUILTIN_PRESETS = {
    "tech-saas": {
        "name": "tech-saas",
        "description": "Professional SaaS aesthetics with minimalist design",
        "colorPalette": ["#2563EB", "#FFFFFF", "#1E293B"],
        "illustrationStyle": "flat vector, glassmorphism, isometric 3D",
        "typography": "bold geometric sans-serif",
        "lighting": "soft diffused studio lighting",
        "mood": ["professional", "trustworthy", "modern"],
        "defaults": {"aspectRatio": "16:9", "resolution": "1K", "model": "gemini-3.1-flash-image-preview"},
    },
    "luxury-brand": {
        "name": "luxury-brand",
        "description": "Sophisticated visual language establishing exclusivity",
        "colorPalette": ["#0A0A0A", "#C9A84C", "#F5F0E8"],
        "illustrationStyle": "rich photographic textures, editorial photography",
        "typography": "elegant serif, refined letterforms",
        "lighting": "dramatic studio rim lighting, single high-key source",
        "mood": ["exclusive", "aspirational", "refined"],
        "defaults": {"aspectRatio": "4:5", "resolution": "2K", "model": "gemini-3.1-flash-image-preview"},
    },
    "editorial-magazine": {
        "name": "editorial-magazine",
        "description": "Bold visual impact for contemporary editorial work",
        "colorPalette": ["#E63946", "#1A1A1A", "#FFFFFF"],
        "illustrationStyle": "strong geometric composition, documentary photography",
        "typography": "condensed bold headlines, high-contrast hierarchy",
        "lighting": "high-contrast directional, dramatic shadows",
        "mood": ["bold", "contemporary", "impactful"],
        "defaults": {"aspectRatio": "3:2", "resolution": "2K", "model": "gemini-3.1-flash-image-preview"},
    },
}


def load_preset(name):
    if name in BUILTIN_PRESETS:
        return BUILTIN_PRESETS[name]
    path = PRESETS_DIR / f"{name}.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return None


def save_preset(name, data):
    PRESETS_DIR.mkdir(parents=True, exist_ok=True)
    with open(PRESETS_DIR / f"{name}.json", "w") as f:
        json.dump(data, f, indent=2)


def cmd_list(args):
    names = list(BUILTIN_PRESETS.keys())
    if PRESETS_DIR.exists():
        names += [p.stem for p in PRESETS_DIR.glob("*.json")]
    names = sorted(set(names))
    if not names:
        print("No presets found.")
        return
    for name in names:
        tag = " (built-in)" if name in BUILTIN_PRESETS else ""
        preset = load_preset(name)
        desc = preset.get("description", "") if preset else ""
        print(f"  {name}{tag} — {desc}")


def cmd_show(args):
    preset = load_preset(args.name)
    if not preset:
        print(f"Preset '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)
    print(json.dumps(preset, indent=2))


def cmd_create(args):
    print(f"Creating preset '{args.name}' (press Enter to accept defaults):")
    data = {
        "name": args.name,
        "description": input("Description: ").strip(),
        "colorPalette": [c.strip() for c in (input("Colors (comma-separated hex): ") or "#000000").split(",")],
        "illustrationStyle": input("Illustration style: ").strip(),
        "typography": input("Typography: ").strip(),
        "lighting": input("Lighting: ").strip(),
        "mood": [m.strip() for m in (input("Mood keywords (comma-separated): ") or "").split(",")],
        "defaults": {
            "aspectRatio": input("Default aspect ratio [16:9]: ").strip() or "16:9",
            "resolution": input("Default resolution [2K]: ").strip() or "2K",
            "model": "gemini-3.1-flash-image-preview",
        },
    }
    save_preset(args.name, data)
    print(f"Preset '{args.name}' saved to {PRESETS_DIR / args.name}.json")


def cmd_remove(args):
    if args.name in BUILTIN_PRESETS:
        print(f"Cannot remove built-in preset '{args.name}'.", file=sys.stderr)
        sys.exit(1)
    path = PRESETS_DIR / f"{args.name}.json"
    if not path.exists():
        print(f"Preset '{args.name}' not found.", file=sys.stderr)
        sys.exit(1)
    path.unlink()
    print(f"Preset '{args.name}' removed.")


def main():
    parser = argparse.ArgumentParser(description="Manage banana-claude brand presets")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("list", help="List all presets")

    p_show = sub.add_parser("show", help="Show preset details")
    p_show.add_argument("name")

    p_create = sub.add_parser("create", help="Create a new preset interactively")
    p_create.add_argument("name")

    p_remove = sub.add_parser("remove", help="Remove a preset")
    p_remove.add_argument("name")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    {"list": cmd_list, "show": cmd_show, "create": cmd_create, "remove": cmd_remove}[args.command](args)


if __name__ == "__main__":
    main()
