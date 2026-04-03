---
name: install-openclaw-video-assistant
description: Install the openclaw-video-assistant GitHub repo as a new OpenClaw workspace-backed agent on this machine. Use when the user wants a simple chat-driven way to create or update a dedicated video-agent, optionally bind an existing Feishu robot account to it, and avoid manual openclaw.json edits.
---

# Install OpenClaw Video Assistant

Use this skill when the user wants to install `openclaw-video-assistant` into the current OpenClaw setup as a dedicated agent.

This is a standard installer skill. It does **not** treat the whole repo as a normal `workspace/skills` package. Instead, it:

1. clones or updates the `openclaw-video-assistant` GitHub repo to a local workspace path
2. creates or updates a dedicated OpenClaw agent
3. points that agent's `workspace` to the cloned repo
4. optionally binds an existing Feishu `accountId` to that agent
5. restarts the WSL gateway

## What this skill installs

Source repo:

- `https://github.com/jj5025676-star/openclaw-video-assistant.git`

Default local install path:

- `D:\openclaw_workspaces\openclaw-video-assistant`

Default agent:

- `video-agent`

## Current machine assumptions

This installer is tailored to the current machine:

- active OpenClaw config: `/home/z852963/.openclaw/openclaw.json`
- Windows mirror: `\\wsl.localhost\Ubuntu\home\z852963\.openclaw\openclaw.json`
- active WSL distro: `Ubuntu`
- gateway service: `openclaw-gateway.service`

## Installation scope

Install this skill into the current OpenClaw chat workspace only. Do not assume global installation.

This skill is administrative, so workspace-local installation is safer in multi-agent setups.

## When to use

Use this skill when the user asks things like:

- "安装 openclaw-video-assistant"
- "给我创建一个 video-agent"
- "把 openclaw-video-assistant 绑定到 bot3"
- "从 GitHub 安装视频助手 agent"

## Inputs to gather

Minimum useful fields:

- `agentId`
  - default: `video-agent`
- optional `accountId`
  - example: `bot3`

Optional fields:

- `targetPath`
  - default: `D:\openclaw_workspaces\openclaw-video-assistant`
- `repoUrl`
  - default: `https://github.com/jj5025676-star/openclaw-video-assistant.git`
- `restart`
  - default: `true`

## Chat-first input format

Prefer asking the user to send parameters in this exact shape:

```text
使用 install-openclaw-video-assistant 技能
agentId=video-agent
accountId=bot3
targetPath=D:\openclaw_workspaces\openclaw-video-assistant
restart=true
```

If the user only says "安装 openclaw-video-assistant", assume:

- `agentId=video-agent`
- no `accountId`
- `targetPath=D:\openclaw_workspaces\openclaw-video-assistant`
- `restart=true`

## Execution behavior

When triggered from chat:

1. Parse user fields.
2. Use defaults for omitted optional fields.
3. Run the bundled installer script.
4. If `accountId` is provided, ensure that account already exists in `channels.feishu.accounts`.
5. Restart gateway unless the user explicitly sets `restart=false`.
6. Report:
   - local repo path
   - created/updated `agentId`
   - whether binding was created/updated
   - whether gateway restart succeeded

## Important boundary

This skill only automates the OpenClaw side.

It does **not**:

- create a new Feishu app
- configure Feishu permissions
- configure Feishu events
- publish a Feishu app version

If the user wants to create a **new** Feishu robot, first use the Feishu backend and then use [`add-feishu-bot-agent-skill`](../add-feishu-bot-agent-skill/SKILL.md).

## Script path

Use this script:

`scripts/install_openclaw_video_assistant.py`

## Terminal form

If you must show the terminal command, use:

```powershell
python "D:\openclaw_workspace\skills\install-openclaw-video-assistant\scripts\install_openclaw_video_assistant.py" --agent-id video-agent --account-id bot3 --restart
```
