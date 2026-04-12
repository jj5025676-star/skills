---
name: add-feishu-bot-agent
description: Safely add another Feishu self-built app robot into the current OpenClaw setup and bind it to a dedicated agent and workspace. Use when the user already has a Feishu App ID and App Secret and wants one more Feishu robot to work independently inside the same OpenClaw instance.
---

# Add Feishu Bot Agent

Use this skill when the user already finished the Feishu backend setup and now wants to add that robot to the current OpenClaw instance.

Install this skill into the current chat page's `workspace/skills` only. Do not assume global installation.

## Use this skill when

- the user provides a new `App ID` and `App Secret`
- the user wants a dedicated Feishu `accountId`
- the user wants a dedicated OpenClaw `agent`
- the user wants a safe config write with backup and rollback

## Do not use this skill when

- the user has not finished the Feishu backend setup
- the user wants to create the Feishu app itself
- the user wants to run raw `openclaw config set` commands in chat
- the user only wants to inspect existing config

## Scope

This skill only automates the OpenClaw side:

- add `channels.feishu.accounts.<accountId>`
- ensure `session.dmScope = "per-account-channel-peer"`
- create or update a dedicated `agent`
- create or update a `binding`
- create missing agent and workspace directories

This skill does not automate the Feishu backend console. The user must still:

- create the self-built app
- enable robot capability
- enable persistent connection events
- add `im.message.receive_v1`
- grant send/receive permissions
- add test members when needed
- publish the latest version

## Safety boundary

This skill must not use `openclaw config set`, `openclaw config apply`, or any direct chat-driven config command.

Always use the bundled script so the write path is:

- full config read
- merge in memory
- backup
- validation
- rollback on failure

Prefer `restart=false` by default. Only restart when the user explicitly asks for it, or when the user is operating from the local OpenClaw control UI and accepts that the current session may be interrupted.

## Machine defaults

- WSL distro: `Ubuntu`
- active config: `/home/z852963/.openclaw/openclaw.json`
- Windows mirror: `\\wsl.localhost\Ubuntu\home\z852963\.openclaw\openclaw.json`
- default workspace: `D:\openclaw_workspace_<accountId>`

## Inputs

Required:

- `accountId`
- `appId`
- `appSecret`
- `agentId`

Optional:

- `workspace`
- `restart`

Defaults:

- `workspace=D:\openclaw_workspace_<accountId>`
- `restart=false`

## Chat input format

```text
Use add-feishu-bot-agent
accountId=bot3
appId=cli_xxx
appSecret=xxxx
agentId=bot3-agent
workspace=D:\openclaw_workspace_bot3
restart=false
```

If a field is missing, ask only for the missing field.

## Script path

`D:\openclaw_workspace\skills\add-feishu-bot-agent\scripts\add_feishu_bot_agent.py`

## Terminal form

```powershell
python "D:\openclaw_workspace\skills\add-feishu-bot-agent\scripts\add_feishu_bot_agent.py" --account-id bot3 --app-id cli_xxx --app-secret your_secret --agent-id bot3-agent
```

Only add `--restart` when explicitly requested.

## Report after execution

- updated config path
- backup path
- account id
- agent id
- workspace path
- whether restart was skipped or executed

## Verify

```powershell
wsl -d Ubuntu -- systemctl --user status openclaw-gateway.service --no-pager
wsl -d Ubuntu -- bash -lc "tail -n 80 /tmp/openclaw/openclaw-$(date +%F).log"
```
