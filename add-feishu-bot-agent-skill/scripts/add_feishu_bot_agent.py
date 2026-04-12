#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DISTRO = "Ubuntu"
DEFAULT_WSL_USER = "z852963"
IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    DEFAULT_CONFIG = Path(r"\\wsl.localhost\Ubuntu\home\z852963\.openclaw\openclaw.json")
    DEFAULT_OPENCLAW_DIR = Path(r"\\wsl.localhost\Ubuntu\home\z852963\.openclaw")
else:
    DEFAULT_CONFIG = Path(f"/home/{DEFAULT_WSL_USER}/.openclaw/openclaw.json")
    DEFAULT_OPENCLAW_DIR = Path(f"/home/{DEFAULT_WSL_USER}/.openclaw")


def windows_to_wsl_path(path: str) -> str:
    if path.startswith("/mnt/"):
        return path
    if len(path) >= 3 and path[1:3] == ":\\":
        drive = path[0].lower()
        rest = path[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    raise ValueError(f"Unsupported path for WSL conversion: {path}")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def atomic_write_json(path: Path, data: dict) -> None:
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def upsert_agent_list(config: dict, agent_id: str, workspace_wsl: str, agent_dir_wsl: str) -> None:
    agents = config.setdefault("agents", {})
    agent_list = agents.setdefault("list", [])
    found = next((item for item in agent_list if item.get("id") == agent_id), None)
    if found is None:
        found = {"id": agent_id}
        agent_list.append(found)
    found["workspace"] = workspace_wsl
    found["agentDir"] = agent_dir_wsl


def upsert_binding(config: dict, agent_id: str, account_id: str) -> None:
    bindings = config.setdefault("bindings", [])
    for item in bindings:
        match = item.get("match", {})
        if match.get("channel") == "feishu" and match.get("accountId") == account_id:
            item["agentId"] = agent_id
            return
    bindings.append(
        {
            "agentId": agent_id,
            "match": {"channel": "feishu", "accountId": account_id},
        }
    )


def validate_config(config: dict, original: dict) -> None:
    gateway = config.get("gateway")
    if not isinstance(gateway, dict):
        raise ValueError("Refusing to write config without gateway section.")
    if gateway.get("mode") != "local":
        raise ValueError("Refusing to write config without gateway.mode=local.")
    if "channels" not in config or not isinstance(config["channels"], dict):
        raise ValueError("Refusing to write config without channels section.")
    if "agents" not in config or not isinstance(config["agents"], dict):
        raise ValueError("Refusing to write config without agents section.")
    if "gateway" in original and "gateway" not in config:
        raise ValueError("Refusing to remove an existing gateway section.")


def safe_write_config(config_path: Path, config: dict) -> Path:
    original = load_json(config_path)
    validate_config(config, original)
    backup_path = config_path.with_name(
        f"{config_path.stem}.before-add-feishu-bot-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{config_path.suffix}"
    )
    shutil.copy2(config_path, backup_path)
    try:
        atomic_write_json(config_path, config)
        reloaded = load_json(config_path)
        validate_config(reloaded, original)
    except Exception:
        shutil.copy2(backup_path, config_path)
        raise
    return backup_path


def restart_gateway(distro: str) -> None:
    if IS_WINDOWS:
        cmd = ["wsl", "-d", distro, "--", "systemctl", "--user", "restart", "openclaw-gateway.service"]
    else:
        cmd = ["systemctl", "--user", "restart", "openclaw-gateway.service"]
    subprocess.run(cmd, check=True)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Safely add a Feishu bot account and bind it to a dedicated OpenClaw agent."
    )
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--app-secret", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--workspace", help=r"Windows path, default: D:\openclaw_workspace_<accountId>")
    parser.add_argument("--distro", default=DEFAULT_DISTRO)
    parser.add_argument("--wsl-user", default=DEFAULT_WSL_USER)
    parser.add_argument("--config")
    parser.add_argument("--restart", action="store_true", help="Restart gateway after a successful write.")
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else DEFAULT_CONFIG
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    workspace_win = args.workspace or fr"D:\openclaw_workspace_{args.account_id}"
    workspace_wsl = windows_to_wsl_path(workspace_win)

    openclaw_dir_wsl = f"/home/{args.wsl_user}/.openclaw"
    agent_dir_wsl = f"{openclaw_dir_wsl}/agents/{args.agent_id}/agent"
    sessions_dir_wsl = f"{openclaw_dir_wsl}/agents/{args.agent_id}/sessions"

    if IS_WINDOWS:
        agent_dir_for_mkdir = DEFAULT_OPENCLAW_DIR / "agents" / args.agent_id / "agent"
        sessions_dir_for_mkdir = DEFAULT_OPENCLAW_DIR / "agents" / args.agent_id / "sessions"
        workspace_for_mkdir = Path(workspace_win)
    else:
        agent_dir_for_mkdir = Path(agent_dir_wsl)
        sessions_dir_for_mkdir = Path(sessions_dir_wsl)
        workspace_for_mkdir = Path(workspace_wsl)

    ensure_dir(agent_dir_for_mkdir)
    ensure_dir(sessions_dir_for_mkdir)
    ensure_dir(workspace_for_mkdir)

    config = load_json(config_path)
    config.setdefault("session", {})["dmScope"] = "per-account-channel-peer"
    feishu = config.setdefault("channels", {}).setdefault("feishu", {})
    accounts = feishu.setdefault("accounts", {})
    accounts[args.account_id] = {
        "appId": args.app_id,
        "appSecret": args.app_secret,
        "dmPolicy": "open",
        "allowFrom": ["*"],
    }
    upsert_agent_list(config, args.agent_id, workspace_wsl, agent_dir_wsl)
    upsert_binding(config, args.agent_id, args.account_id)

    backup_path = safe_write_config(config_path, config)

    print("Updated config:", config_path)
    print("Backup:", backup_path)
    print("Account:", args.account_id)
    print("Agent:", args.agent_id)
    print("Workspace:", workspace_win)
    print("Agent dir:", agent_dir_wsl)
    print("Sessions dir:", sessions_dir_wsl)

    if args.restart:
        restart_gateway(args.distro)
        print("Restarted openclaw-gateway.service")
    else:
        print("Gateway restart skipped. Restart manually after confirming the write.")

    print("Next checks:")
    if IS_WINDOWS:
        print(rf'wsl -d {args.distro} -- systemctl --user status openclaw-gateway.service --no-pager')
        print(rf'wsl -d {args.distro} -- bash -lc "tail -n 80 /tmp/openclaw/openclaw-$(date +%F).log"')
    else:
        print("systemctl --user status openclaw-gateway.service --no-pager")
        print('tail -n 80 /tmp/openclaw/openclaw-$(date +%F).log')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
