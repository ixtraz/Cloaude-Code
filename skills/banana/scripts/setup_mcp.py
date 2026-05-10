#!/usr/bin/env python3
"""Configure the nanobanana MCP server in Claude Code settings."""

import argparse
import json
import os
import sys
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
MCP_SERVER_NAME = "nanobanana-mcp"
MCP_COMMAND = "npx"
MCP_ARGS = ["-y", "@ycse/nanobanana-mcp"]
DEFAULT_MODEL = "gemini-3.1-flash-image-preview"
OUTPUT_DIR = str(Path.home() / "Documents" / "nanobanana_generated")
DEFAULT_BACKEND = "gemini"   # "gemini" | "kie"


def load_settings():
    if SETTINGS_PATH.exists():
        with open(SETTINGS_PATH) as f:
            return json.load(f)
    return {}


def save_settings(settings):
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        json.dump(settings, f, indent=2)
    print(f"Settings saved to {SETTINGS_PATH}")


def _prompt_key(prompt_text):
    key = input(prompt_text).strip()
    if not key:
        print("ERROR: No API key provided.", file=sys.stderr)
        sys.exit(1)
    return key


def get_gemini_key(args_key):
    if args_key:
        return args_key
    key = os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    # re-use key already stored in settings
    existing = load_settings()
    stored = existing.get("mcpServers", {}).get(MCP_SERVER_NAME, {}).get("env", {}).get("GOOGLE_AI_API_KEY")
    if stored:
        return stored
    return _prompt_key("Google AI API key (https://aistudio.google.com/apikey): ")


def get_kie_key(args_kie_key):
    if args_kie_key:
        return args_kie_key
    key = os.environ.get("KIE_API_KEY") or os.environ.get("KIE_AI_API_KEY")
    if key:
        return key
    return _prompt_key("kie.ai API key (https://kie.ai/) — press Enter to skip: ") or None


def _mask(key):
    return key[:4] + "****" + key[-4:] if len(key) > 8 else "****"


def cmd_setup(args):
    gemini_key = get_gemini_key(args.key)
    kie_key = get_kie_key(args.kie_key)
    backend = args.backend or DEFAULT_BACKEND

    settings = load_settings()
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}

    env = {
        "GOOGLE_AI_API_KEY": gemini_key,
        "NANOBANANA_MODEL": DEFAULT_MODEL,
        "NANOBANANA_OUTPUT_DIR": OUTPUT_DIR,
        "BANANA_BACKEND": backend,
    }
    if kie_key:
        env["KIE_API_KEY"] = kie_key

    settings["mcpServers"][MCP_SERVER_NAME] = {
        "command": MCP_COMMAND,
        "args": MCP_ARGS,
        "env": env,
    }
    save_settings(settings)
    print(f"\nMCP server '{MCP_SERVER_NAME}' configured.")
    print(f"  Backend:     {backend}")
    print(f"  Gemini key:  {_mask(gemini_key)}")
    if kie_key:
        print(f"  kie.ai key:  {_mask(kie_key)}")
    print("\nRestart Claude Code to activate the nanobanana-mcp tools.")


def cmd_check(args):
    settings = load_settings()
    servers = settings.get("mcpServers", {})
    if MCP_SERVER_NAME not in servers:
        print(f"MCP server '{MCP_SERVER_NAME}' is NOT configured.")
        print("Run 'python3 setup_mcp.py' to configure it.")
        return
    cfg = servers[MCP_SERVER_NAME]
    env = cfg.get("env", {})
    print(f"MCP server '{MCP_SERVER_NAME}' is configured.")
    print(f"  Command:     {cfg.get('command')} {' '.join(cfg.get('args', []))}")
    print(f"  Backend:     {env.get('BANANA_BACKEND', DEFAULT_BACKEND)}")
    print(f"  Model:       {env.get('NANOBANANA_MODEL', DEFAULT_MODEL)}")
    gk = env.get("GOOGLE_AI_API_KEY", "")
    kk = env.get("KIE_API_KEY", "")
    print(f"  Gemini key:  {_mask(gk) if gk else '(not set)'}")
    print(f"  kie.ai key:  {_mask(kk) if kk else '(not set)'}")


def cmd_remove(args):
    settings = load_settings()
    if MCP_SERVER_NAME in settings.get("mcpServers", {}):
        del settings["mcpServers"][MCP_SERVER_NAME]
        save_settings(settings)
        print(f"MCP server '{MCP_SERVER_NAME}' removed.")
    else:
        print(f"MCP server '{MCP_SERVER_NAME}' was not configured.")


def main():
    parser = argparse.ArgumentParser(description="Configure nanobanana MCP for Claude Code")
    parser.add_argument("--key", help="Google AI API key (GOOGLE_AI_API_KEY)")
    parser.add_argument("--kie-key", help="kie.ai API key (KIE_API_KEY)")
    parser.add_argument("--backend", choices=["gemini", "kie"],
                        help=f"Default backend (default: {DEFAULT_BACKEND})")
    parser.add_argument("--check", action="store_true", help="Show current configuration")
    parser.add_argument("--remove", action="store_true", help="Remove MCP configuration")
    args = parser.parse_args()

    if args.check:
        cmd_check(args)
    elif args.remove:
        cmd_remove(args)
    else:
        cmd_setup(args)


if __name__ == "__main__":
    main()
