# skills

这个仓库用来存放多个 `Codex / OpenClaw skill`。

每个 skill 都放在自己的子目录里，目录内通常包含：

- `SKILL.md`
- `scripts/`
- `agents/`

## 当前 skills

- [`add-feishu-bot-agent-skill`](./add-feishu-bot-agent-skill)
  - 给当前机器上的 OpenClaw 新增一个飞书机器人账号，并绑定到独立 agent / workspace
- [`install-openclaw-video-assistant`](./install-openclaw-video-assistant)
  - 一键拉取 `openclaw-video-assistant` 仓库，注册为新的 `video-agent`，并可选绑定到现有飞书机器人

## 使用原则

- 默认安装到当前聊天页面对应的 `workspace/skills`
- 不建议默认全局安装
- 管理类 skill 尽量只给主工作区使用

## 典型场景

### 1. 新增飞书机器人

使用 `add-feishu-bot-agent-skill`：

- 新增 `channels.feishu.accounts.<accountId>`
- 创建独立 agent
- 创建独立 workspace
- 建立 `accountId -> agentId` binding

### 2. 新增视频工作区 agent

使用 `install-openclaw-video-assistant`：

- 从 GitHub 拉取 `openclaw-video-assistant`
- 在 OpenClaw 中创建 `video-agent`
- 让 `video-agent` 的 workspace 指向该仓库
- 可选把某个已有飞书机器人绑定到这个 `video-agent`

## 后续加 skill 的建议结构

```text
skills/
├─ README.md
├─ .gitignore
├─ add-feishu-bot-agent-skill/
└─ install-openclaw-video-assistant/
```
