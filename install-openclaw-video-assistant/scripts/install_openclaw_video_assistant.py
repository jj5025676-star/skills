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


DEFAULT_WSL_DISTRO = "Ubuntu"
DEFAULT_AGENT_ID = "video-agent"
DEFAULT_REPO_URL = "https://github.com/jj5025676-star/openclaw-video-assistant.git"
DEFAULT_TARGET_PATH = Path(r"D:\openclaw_workspaces\openclaw-video-assistant")
DEFAULT_CONFIG_WIN = Path(r"\\wsl.localhost\Ubuntu\home\z852963\.openclaw\openclaw.json")
DEFAULT_CONFIG_WSL = Path("/home/z852963/.openclaw/openclaw.json")


def is_windows() -> bool:
    return os.name == "nt"


def to_wsl_path(path: Path) -> str:
    text = str(path)
    prefix = "\\\\wsl.localhost\\Ubuntu\\"
    if text.startswith(prefix):
        rest = text[len(prefix):].replace("\\", "/")
        return "/" + rest
    if len(text) >= 2 and text[1] == ":":
        drive = text[0].lower()
        rest = text[2:].replace("\\", "/")
        return f"/mnt/{drive}{rest}"
    return text.replace("\\", "/")


def detect_default_config() -> Path:
    if is_windows() and DEFAULT_CONFIG_WIN.exists():
        return DEFAULT_CONFIG_WIN
    if DEFAULT_CONFIG_WSL.exists():
        return DEFAULT_CONFIG_WSL
    raise FileNotFoundError("找不到 OpenClaw 生效配置文件 openclaw.json")


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def run(cmd: list[str]) -> None:
    subprocess.run(cmd, check=True)


def clone_or_update_repo(repo_url: str, target_path: Path) -> str:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if (target_path / ".git").exists():
        run(["git", "-C", str(target_path), "pull", "--ff-only"])
        return "updated"
    if target_path.exists() and any(target_path.iterdir()):
        raise RuntimeError(f"目标目录已存在且非空：{target_path}")
    if target_path.exists():
        shutil.rmtree(target_path)
    run(["git", "clone", repo_url, str(target_path)])
    return "cloned"


def ensure_agent(config: dict, agent_id: str, workspace_wsl: str, agent_dir_wsl: str) -> str:
    agents = config.setdefault("agents", {})
    agent_list = agents.setdefault("list", [])
    for agent in agent_list:
        if agent.get("id") == agent_id:
            agent["workspace"] = workspace_wsl
            agent["agentDir"] = agent_dir_wsl
            return "updated"
    agent_list.append(
        {
            "id": agent_id,
            "workspace": workspace_wsl,
            "agentDir": agent_dir_wsl,
        }
    )
    return "created"


def ensure_binding(config: dict, agent_id: str, account_id: str) -> str:
    feishu = config.get("channels", {}).get("feishu", {})
    accounts = feishu.get("accounts", {})
    if account_id not in accounts:
        raise ValueError(f"当前配置里不存在飞书 accountId={account_id}")

    if config.get("session", {}).get("dmScope") in (None, ""):
        config.setdefault("session", {})["dmScope"] = "per-account-channel-peer"

    bindings = config.setdefault("bindings", [])
    for binding in bindings:
        match = binding.get("match", {})
        if match.get("channel") == "feishu" and match.get("accountId") == account_id:
            binding["agentId"] = agent_id
            return "updated"

    bindings.append(
        {
            "agentId": agent_id,
            "match": {
                "channel": "feishu",
                "accountId": account_id,
            },
        }
    )
    return "created"


def restart_gateway() -> None:
    if is_windows():
        run(["wsl", "-d", DEFAULT_WSL_DISTRO, "--", "systemctl", "--user", "restart", "openclaw-gateway.service"])
    else:
        run(["systemctl", "--user", "restart", "openclaw-gateway.service"])


def main() -> int:
    parser = argparse.ArgumentParser(description="安装 openclaw-video-assistant，并注册为新的 OpenClaw agent")
    parser.add_argument("--agent-id", default=DEFAULT_AGENT_ID)
    parser.add_argument("--account-id")
    parser.add_argument("--target-path", default=str(DEFAULT_TARGET_PATH))
    parser.add_argument("--repo-url", default=DEFAULT_REPO_URL)
    parser.add_argument("--config")
    parser.add_argument("--restart", dest="restart", action="store_true")
    parser.add_argument("--no-restart", dest="restart", action="store_false")
    parser.set_defaults(restart=True)
    args = parser.parse_args()

    config_path = Path(args.config) if args.config else detect_default_config()
    target_path = Path(args.target_path)
    repo_status = clone_or_update_repo(args.repo_url, target_path)

    config = load_json(config_path)
    backup_path = config_path.with_name(
        f"{config_path.stem}.before-video-assistant-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}{config_path.suffix}"
    )
    shutil.copy2(config_path, backup_path)

    workspace_wsl = to_wsl_path(target_path)
    config_dir_local = config_path.parent
    config_dir_wsl = to_wsl_path(config_dir_local)
    agent_dir_wsl = f"{config_dir_wsl}/agents/{args.agent_id}/agent"
    agent_dir_local = config_dir_local / "agents" / args.agent_id / "agent"
    agent_dir_local.mkdir(parents=True, exist_ok=True)

    agent_status = ensure_agent(config, args.agent_id, workspace_wsl, agent_dir_wsl)
    binding_status = None
    if args.account_id:
        binding_status = ensure_binding(config, args.agent_id, args.account_id)

    meta = config.setdefault("meta", {})
    meta["lastTouchedAt"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

    write_json(config_path, config)

    if args.restart:
        restart_gateway()

    print("安装完成")
    print(f"repo: {args.repo_url}")
    print(f"repo status: {repo_status}")
    print(f"target path: {target_path}")
    print(f"agent: {args.agent_id} ({agent_status})")
    print(f"workspace: {workspace_wsl}")
    print(f"config: {config_path}")
    print(f"backup: {backup_path}")
    if args.account_id:
        print(f"binding: feishu/{args.account_id} -> {args.agent_id} ({binding_status})")
    print(f"gateway restarted: {'yes' if args.restart else 'no'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
