#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path


DEFAULT_DISTRO = "Ubuntu"
DEFAULT_WSL_USER = "z852963"
DEFAULT_CONFIG_WIN = Path(r"\\wsl.localhost\Ubuntu\home\z852963\.openclaw\openclaw.json")
DEFAULT_OPENCLAW_DIR_WIN = Path(r"\\wsl.localhost\Ubuntu\home\z852963\.openclaw")


def windows_to_wsl_path(path: str) -> str:
    if len(path) >= 3 and path[1:3] == ":\\":
        drive = path[0].lower()
        rest = path[3:].replace("\\", "/")
        return f"/mnt/{drive}/{rest}"
    raise ValueError(f"Unsupported Windows path for WSL conversion: {path}")


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def upsert_agent_list(config: dict, agent_id: str, workspace_wsl: str, agent_dir_wsl: str) -> None:
    agents = config.setdefault("agents", {})
    agent_list = agents.setdefault("list", [])
    found = None
    for item in agent_list:
        if item.get("id") == agent_id:
            found = item
            break
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


def main() -> int:
    parser = argparse.ArgumentParser(description="Add a Feishu bot account and bind it to its own OpenClaw agent.")
    parser.add_argument("--account-id", required=True)
    parser.add_argument("--app-id", required=True)
    parser.add_argument("--app-secret", required=True)
    parser.add_argument("--agent-id", required=True)
    parser.add_argument("--workspace", help=r'Windows path, default: D:\openclaw_workspace_<accountId>')
    parser.add_argument("--distro", default=DEFAULT_DISTRO)
    parser.add_argument("--wsl-user", default=DEFAULT_WSL_USER)
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_WIN))
    parser.add_argument("--restart", action="store_true")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}", file=sys.stderr)
        return 1

    workspace_win = args.workspace or fr"D:\openclaw_workspace_{args.account_id}"
    workspace_wsl = windows_to_wsl_path(workspace_win)

    openclaw_dir_wsl = f"/home/{args.wsl_user}/.openclaw"
    agent_dir_wsl = f"{openclaw_dir_wsl}/agents/{args.agent_id}/agent"
    sessions_dir_wsl = f"{openclaw_dir_wsl}/agents/{args.agent_id}/sessions"

    agent_dir_win = DEFAULT_OPENCLAW_DIR_WIN / "agents" / args.agent_id / "agent"
    sessions_dir_win = DEFAULT_OPENCLAW_DIR_WIN / "agents" / args.agent_id / "sessions"
    workspace_win_path = Path(workspace_win)

    ensure_dir(agent_dir_win)
    ensure_dir(sessions_dir_win)
    ensure_dir(workspace_win_path)

    config = json.loads(config_path.read_text(encoding="utf-8"))

    session = config.setdefault("session", {})
    session["dmScope"] = "per-account-channel-peer"

    feishu = config.setdefault("channels", {}).setdefault("feishu", {})
    feishu.setdefault("accounts", {})
    feishu["accounts"][args.account_id] = {
        "appId": args.app_id,
        "appSecret": args.app_secret,
        "dmPolicy": "open",
        "allowFrom": ["*"],
    }

    upsert_agent_list(config, args.agent_id, workspace_wsl, agent_dir_wsl)
    upsert_binding(config, args.agent_id, args.account_id)

    config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("Updated config:", config_path)
    print("Account:", args.account_id)
    print("Agent:", args.agent_id)
    print("Workspace:", workspace_win)
    print("Agent dir:", agent_dir_wsl)
    print("Sessions dir:", sessions_dir_wsl)

    if args.restart:
        result = subprocess.run(
            ["wsl", "-d", args.distro, "--", "systemctl", "--user", "restart", "openclaw-gateway.service"],
            capture_output=True,
            text=True,
        )
        print(result.stdout, end="")
        if result.returncode != 0:
            print(result.stderr, file=sys.stderr, end="")
            return result.returncode
        print("Restarted openclaw-gateway.service")

    print("Next checks:")
    print(rf'wsl -d {args.distro} -- systemctl --user status openclaw-gateway.service --no-pager')
    print(rf'wsl -d {args.distro} -- bash -lc "tail -n 80 /tmp/openclaw/openclaw-$(date +%F).log"')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
