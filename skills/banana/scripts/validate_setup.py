#!/usr/bin/env python3
"""Validate banana-claude MCP server setup (9 checks)."""

import json
import os
import shutil
import sys
from pathlib import Path

SETTINGS_PATH = Path.home() / ".claude" / "settings.json"
OUTPUT_DIR = Path.home() / "Documents" / "nanobanana_generated"
MCP_SERVER_NAME = "nanobanana-mcp"


def check(label, passed, detail=""):
    status = "PASS" if passed else "FAIL"
    line = f"  [{status}] {label}"
    if detail:
        line += f" — {detail}"
    print(line)
    return passed


def main():
    print("\nbana-claude Setup Validator")
    print("=" * 40)
    results = []

    # 1. Settings file exists
    results.append(check("settings.json exists", SETTINGS_PATH.exists(), str(SETTINGS_PATH)))

    # 2. Valid JSON
    settings = {}
    if SETTINGS_PATH.exists():
        try:
            with open(SETTINGS_PATH) as f:
                settings = json.load(f)
            results.append(check("settings.json valid JSON", True))
        except json.JSONDecodeError as e:
            results.append(check("settings.json valid JSON", False, str(e)))
    else:
        results.append(check("settings.json valid JSON", False, "file missing"))

    # 3. MCP server registered
    servers = settings.get("mcpServers", {})
    has_server = MCP_SERVER_NAME in servers
    results.append(check(f"MCP server '{MCP_SERVER_NAME}' registered", has_server))

    server_cfg = servers.get(MCP_SERVER_NAME, {})

    # 4. Command is npx
    results.append(check("command = 'npx'", server_cfg.get("command") == "npx"))

    # 5. Package @ycse/nanobanana-mcp in args
    args = server_cfg.get("args", [])
    results.append(check("@ycse/nanobanana-mcp in args", "@ycse/nanobanana-mcp" in args))

    # 6. API key configured
    api_key = server_cfg.get("env", {}).get("GOOGLE_AI_API_KEY", "") or os.environ.get("GOOGLE_AI_API_KEY", "")
    if api_key:
        masked = api_key[:4] + "****" + api_key[-4:] if len(api_key) > 8 else "****"
        results.append(check("GOOGLE_AI_API_KEY set", True, masked))
    else:
        results.append(check("GOOGLE_AI_API_KEY set", False, "not found in settings or environment"))

    # 7. Model configured
    model = server_cfg.get("env", {}).get("NANOBANANA_MODEL", "")
    results.append(check("NANOBANANA_MODEL set", bool(model), model or "(not set, will use default)"))

    # 8. npx available
    npx_path = shutil.which("npx")
    results.append(check("npx available in PATH", bool(npx_path), npx_path or "not found"))

    # 9. Output directory
    if not OUTPUT_DIR.exists():
        try:
            OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
            results.append(check("output directory", True, f"created {OUTPUT_DIR}"))
        except Exception as e:
            results.append(check("output directory", False, str(e)))
    else:
        results.append(check("output directory", True, str(OUTPUT_DIR)))

    print()
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} checks passed")

    if passed == total:
        print("\nReady to generate images!")
        print("Try: /banana a sunset over mountains in watercolor style")
    else:
        print("\nIssues found. Run 'python3 skills/banana/scripts/setup_mcp.py' to configure.")
        print("Get a free API key at: https://aistudio.google.com/apikey")
    print()


if __name__ == "__main__":
    main()
