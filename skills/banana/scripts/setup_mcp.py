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


def get_api_key(args_key):
    if args_key:
        return args_key
    key = os.environ.get("GOOGLE_AI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if key:
        return key
    print("Enter your Google AI API key (get one free at https://aistudio.google.com/apikey):")
    key = input("API key: ").strip()
    if not key:
        print("ERROR: No API key provided.", file=sys.stderr)
        sys.exit(1)
    return key


def cmd_setup(args):
    api_key = get_api_key(args.key)
    settings = load_settings()
    if "mcpServers" not in settings:
        settings["mcpServers"] = {}

    settings["mcpServers"][MCP_SERVER_NAME] = {
        "command": MCP_COMMAND,
        "args": MCP_ARGS,
        "env": {
            "GOOGLE_AI_API_KEY": api_key,
            "NANOBANANA_MODEL": DEFAULT_MODEL,
            "NANOBANANA_OUTPUT_DIR": OUTPUT_DIR,
        },
    }
    save_settings(settings)
    print(f"\nMCP server '{MCP_SERVER_NAME}' configured successfully.")
    print("Restart Claude Code to activate the nanobanana-mcp tools.")


def cmd_check(args):
    settings = load_settings()
    servers = settings.get("mcpServers", {})
    if MCP_SERVER_NAME in servers:
        cfg = servers[MCP_SERVER_NAME]
        key = cfg.get("env", {}).get("GOOGLE_AI_API_KEY", "")
        masked = key[:4] + "****" + key[-4:] if len(key) > 8 else "****"
        print(f"MCP server '{MCP_SERVER_NAME}' is configured.")
        print(f"  Command: {cfg.get('command')} {' '.join(cfg.get('args', []))}")
        print(f"  API key: {masked}")
        print(f"  Model:   {cfg.get('env', {}).get('NANOBANANA_MODEL', DEFAULT_MODEL)}")
    else:
        print(f"MCP server '{MCP_SERVER_NAME}' is NOT configured.")
        print("Run 'python3 setup_mcp.py' to configure it.")


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
    parser.add_argument("--key", help="Google AI API key")
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
