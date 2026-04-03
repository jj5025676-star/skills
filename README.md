# skills

这个仓库用来存放多个 `Codex / OpenClaw skill`。

每个 skill 都放在自己的子目录里，目录内通常包含：

- `SKILL.md`
- `scripts/`
- `agents/`
- 其他这个 skill 自己需要的辅助文件

当前仓库里的 skill：

- [`add-feishu-bot-agent-skill`](./add-feishu-bot-agent-skill)

## 这个仓库适合做什么

如果你想把常用能力整理成可复用的 skill，并放在一个统一仓库里管理，这个仓库就是干这个的。

典型场景：

- 给 OpenClaw 增加新的自动化能力
- 沉淀团队内部常用技能
- 把多个 skill 统一放到 GitHub 管理
- 以后继续往仓库里追加第二个、第三个 skill

## 当前这个 skill 是做什么的

[`add-feishu-bot-agent-skill`](./add-feishu-bot-agent-skill) 用来解决这个场景：

- 你已经在飞书开放平台新建了一个机器人
- 你想把它接入当前机器上的 OpenClaw
- 并且希望这个机器人有自己独立的：
  - `accountId`
  - `agent`
  - `workspace`
  - 私聊 session

这个 skill 负责的是 `OpenClaw 侧自动化`，不会替你自动点飞书后台。

## 仓库结构

当前结构如下：

```text
skills/
├─ README.md
├─ .gitignore
└─ add-feishu-bot-agent-skill/
   ├─ SKILL.md
   ├─ agents/
   │  └─ openai.yaml
   └─ scripts/
      └─ add_feishu_bot_agent.py
```

后面你要继续加 skill，建议保持同样结构：

```text
skills/
├─ README.md
├─ .gitignore
├─ add-feishu-bot-agent-skill/
└─ another-skill/
```

## 怎么使用这个仓库里的 skill

先分清楚两件事：

- `飞书后台配置`
- `OpenClaw 本地接入`

这两部分不是一回事。

### 1. 飞书后台要你自己配

如果你要新增一个飞书机器人，飞书后台这几步必须先人工完成：

1. 新建飞书自建应用
2. 开启机器人能力
3. 开启长连接事件订阅
4. 添加 `im.message.receive_v1`
5. 开启消息相关权限
6. 把当前账号加入测试人员
7. 发布最新版本

如果这些没做完，OpenClaw 这边配得再好，机器人也可能完全收不到消息。

### 2. OpenClaw 侧可以用 skill 自动化

飞书后台配好以后，再用这个 skill 来自动完成：

- 往 `openclaw.json` 里加入新的飞书账号
- 设置私聊 session 隔离
- 创建新的 agent
- 创建新的 workspace
- 建立 `accountId -> agent` 路由
- 重启 gateway

## add-feishu-bot-agent-skill 怎么用

详细说明看：

- [`add-feishu-bot-agent-skill/SKILL.md`](./add-feishu-bot-agent-skill/SKILL.md)

最推荐的使用方式是：

- 直接在 OpenClaw 聊天里调用

输入格式建议写成这样：

```text
使用 add-feishu-bot-agent 技能新增机器人
accountId=bot3
appId=cli_xxx
appSecret=xxxx
agentId=bot3-agent
workspace=D:\openclaw_workspace_bot3
restart=true
```

最少要提供：

- `accountId`
- `appId`
- `appSecret`
- `agentId`

可选：

- `workspace`
- `restart`

如果你更习惯本机终端，也可以直接执行脚本，具体命令见：

- [`add-feishu-bot-agent-skill/SKILL.md`](./add-feishu-bot-agent-skill/SKILL.md)

## 一个最实用的理解

这个仓库里的 skill，主要是帮你解决：

- “怎么让 OpenClaw 认识这个新机器人”

不是帮你解决：

- “怎么在飞书后台替我点完所有按钮”

所以正确顺序始终是：

1. 先把飞书后台配好
2. 再用 skill 把机器人接进 OpenClaw
3. 最后发消息验证

## 如果你要继续扩展这个仓库

后面继续加 skill，建议遵守这几个规则：

- 一个 skill 一个子目录
- 每个 skill 都有自己的 `SKILL.md`
- 脚本放进 `scripts/`
- agent 相关配置放进 `agents/`
- 不要提交 `__pycache__` 和 `.pyc`

仓库根目录的 `.gitignore` 已经处理了这些 Python 缓存文件。

## 当前状态

这个仓库已经是一个可正常使用的 GitHub 多技能仓库。

你现在可以：

- 继续往里加第二个 skill
- 优化已有 skill 的说明
- 给每个 skill 补更完整的示例和截图
