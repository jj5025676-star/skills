---
name: add-feishu-bot-agent
description: Add another Feishu self-built app robot into the current OpenClaw WSL setup and bind it to a dedicated agent, workspace, and private-message session scope. Use when the user provides a new Feishu App ID and App Secret and wants one more Feishu robot to work independently inside the same OpenClaw instance on this machine.
---

# Add Feishu Bot Agent

Use this skill when adding a new Feishu robot to the current machine's OpenClaw setup.

Prefer using this skill directly from chat. When the user provides the required fields in chat, run the bundled script instead of asking them to copy a terminal command unless they explicitly want to run it themselves.

Install this skill into the current OpenClaw chat workspace only. Do not assume global installation.

This skill only automates the OpenClaw side:

- add `channels.feishu.accounts.<accountId>`
- ensure `session.dmScope = "per-account-channel-peer"`
- add a dedicated `agent`
- add a `binding` from `accountId` to that `agent`
- create the new agent directories
- create the new workspace directory
- optionally restart the WSL gateway

This skill does not automate the Feishu backend console. The user must manually complete:

- create the self-built app
- enable robot capability
- enable event subscription via long connection
- add `im.message.receive_v1`
- grant message send/receive permissions
- add the current account to test members if the app is still in test mode
- publish the latest version

## Current machine defaults

This skill is tailored to the current machine:

- WSL distro: `Ubuntu`
- active OpenClaw config: `/home/z852963/.openclaw/openclaw.json`
- Windows mirror of config: `\\wsl.localhost\Ubuntu\home\z852963\.openclaw\openclaw.json`
- default workspace pattern: `D:\openclaw_workspace_<accountId>`

## Installation scope

Recommended installation scope:

- install into the current chat page's OpenClaw `workspace/skills`
- do not install globally by default

Examples on this machine:

- `main` chat page:
  - `D:\openclaw_workspace\skills`
- `bot2-agent` chat page:
  - `D:\openclaw_workspace_bot2\skills`
- `bot3-agent` chat page:
  - `D:\openclaw_workspace_bot3\skills`

This skill is administrative. Keeping it workspace-local is safer and easier to reason about in multi-agent setups.

## Inputs to gather

Before running the script, gather these fields from the chat message:

- `accountId`
  - example: `bot3`
- `appId`
  - example: `cli_xxx`
- `appSecret`
- `agentId`
  - example: `bot3-agent`
- optional `workspace`
  - default: `D:\openclaw_workspace_<accountId>`

## Chat-first input format

When the user wants to do this directly in chat, ask them to send the parameters in this exact shape:

```text
使用 add-feishu-bot-agent 技能新增机器人
accountId=bot3
appId=cli_xxx
appSecret=xxxx
agentId=bot3-agent
workspace=D:\openclaw_workspace_bot3
restart=true
```

Minimum required fields:

- `accountId`
- `appId`
- `appSecret`
- `agentId`

Optional fields:

- `workspace`
- `restart`

Defaults:

- if `workspace` is omitted, use `D:\openclaw_workspace_<accountId>`
- if `restart` is omitted, treat it as `true`

## How to execute from chat

When the user provides the fields in chat:

1. Parse the fields exactly.
2. Validate that `accountId`, `appId`, `appSecret`, and `agentId` are present.
3. Run the bundled script with the parsed values.
4. Restart the WSL gateway unless the user explicitly sets `restart=false`.
5. Report:
   - which config file was updated
   - which agent was created
   - which workspace was created
   - whether gateway restart succeeded
6. Tell the user what still must be done manually in Feishu backend if the robot has not been configured there yet.

If a field is missing, ask only for the missing field and do not ask the user to re-send everything.

## Script path for execution

Use this script:

`D:\openclaw_workspace\skills\add-feishu-bot-agent\scripts\add_feishu_bot_agent.py`

## Run

If you must show the terminal command, use:

```powershell
python "D:\openclaw_workspace\skills\add-feishu-bot-agent\scripts\add_feishu_bot_agent.py" --account-id bot3 --app-id cli_xxx --app-secret your_secret --agent-id bot3-agent --restart
```

If the workspace should be custom:

```powershell
python "D:\openclaw_workspace\skills\add-feishu-bot-agent\scripts\add_feishu_bot_agent.py" --account-id bot3 --app-id cli_xxx --app-secret your_secret --agent-id bot3-agent --workspace "D:\custom_bot3_workspace" --restart
```

## Verify

After the restart, verify with:

```powershell
wsl -d Ubuntu -- systemctl --user status openclaw-gateway.service --no-pager
wsl -d Ubuntu -- bash -lc "tail -n 80 /tmp/openclaw/openclaw-$(date +%F).log"
```

Look for a line like:

```text
feishu[bot3]: dispatching to agent (session=agent:bot3-agent:feishu:bot3:direct:ou_xxx)
```

If the robot receives the message but does not reply, check Feishu backend manually:

- event subscription
- message permissions
- test members
- version publish
