# feishu-group-summary

> 一个 WorkBuddy / Claude Code **Skill**：用飞书 CLI（`lark-cli`）把一个飞书群的全部聊天记录、共享文档和附件拉下来，自动整理成一份结构化的项目总结报告。

一句话：**对 AI 说"总结 XX 群的所有信息"，它就真的把那个群从第一条翻到最后一条，然后给你一份报告。**

---

## 它解决什么问题

飞书群聊是很多项目事实上的"事实来源"——需求、决策、争议、结论都散在几千条消息里。
要做项目复盘、工作交接、入职了解背景、尽调，人工翻群几乎不可行。

这个 Skill 把整套流程固化成可复用的工作流 + 脚本：

- **全量**：自动分页拉取，不漏消息（解决单次 API 调用的分页上限问题）
- **可读**：把 10+ 种消息类型（文本、富文本、图片、文件、日程、任务卡…）统一渲染成一行一条的纯文本
- **带资料**：顺带产出群内**文件附件清单**和**链接清单**
- **成报告**：按固定结构输出总结（概览 / 人物 / 时间线 / 主线 / 遗留问题 / 资料清单 / 风险）

## 特性

| 特性 | 说明 |
|-|-|
| 🔍 按群名搜索 | 不用记 `chat_id`，直接给群名关键词 |
| 📥 全量分页抓取 | 自动循环 `page_token`，直到没有更多消息 |
| 🧹 自动去重排序 | 按 `message_id` 去重、按时间升序 |
| 📝 三种产物 | `messages.json`（原始）+ `transcript.txt`（可读）+ `assets.md`（资料清单） |
| 📄 文档联动 | 自动识别群内共享的飞书文档并用 `docs +fetch` 拉取正文 |
| ⚡ 多群并行 | 多个群的抓取互不依赖，可并行执行 |
| 🛡️ 容错记录 | 常见报错与踩坑已写进参考手册 |

## 环境要求

1. **`lark-cli`**：飞书官方 CLI，需在 PATH 中可用
2. **已用「用户身份」完成授权**（只有用户身份能读到自己所在群的消息）

```bash
lark-cli auth status
# 关注 identities.user.status == "ready" 且 tokenStatus == "valid"
```

未授权 / 已过期：

```bash
lark-cli auth login
# 把返回的 verification_url 生成二维码，扫码完成授权
lark-cli auth qrcode --output qr.png "<verification_url>"
```

3. **Python 3**（脚本仅用标准库，无第三方依赖）

## 安装

把本仓库整个目录放到你的 skills 目录下即可：

```bash
# 用户级（所有项目可用）
git clone https://github.com/<your-name>/feishu-group-summary.git \
  ~/.workbuddy/skills/feishu-group-summary

# 或项目级（仅当前项目可用）
git clone https://github.com/<your-name>/feishu-group-summary.git \
  .workbuddy/skills/feishu-group-summary
```

> 若你使用的是 Claude Code，对应目录为 `~/.claude/skills/`（视版本而定）。

## 使用

对 AI 说任意一句触发语即可，例如：

- 「总结一下 XX 群的所有信息」
- 「看看 XX 群这个项目都聊了什么」
- 「把 XX 群的聊天记录整理成一份报告」

AI 会按下面的工作流执行。

### 工作流

```
第 1 步  定位群        lark_group.py find "<群名关键词>"
第 2 步  抓取全量消息  lark_group.py fetch --chat "<群名或 chat_id>" --out <目录>
第 3 步  阅读聊天记录  （分段读完 transcript.txt）
第 4 步  拉取共享文档  lark-cli docs +fetch --doc "<url>" --doc-format markdown --as user
第 5 步  产出总结报告  （固定 7 章结构）
第 6 步  交付          （呈现报告 + 文字要点摘要）
```

### 直接使用脚本

```bash
# 1) 找群
python3 scripts/lark_group.py find "项目名"

# 输出：
# oc_xxxxxxxxxxxxxxxx  项目A沟通群      external=False
# oc_yyyyyyyyyyyyyyyy  项目A服务群      external=True

# 2) 抓取（会自动生成三份产物）
python3 scripts/lark_group.py fetch \
  --chat "项目A沟通群" \
  --out ./lark-research/project-a \
  --prefix project_a

# 可选：限定时间范围
python3 scripts/lark_group.py fetch \
  --chat oc_xxxxxxxxxxxxxxxx \
  --out ./out \
  --start "2026-09-01T00:00:00+08:00" \
  --end   "2026-09-30T23:59:59+08:00"
```

**产物示例**：

```
lark-research/project-a/
├── project_a_messages.json    # 原始消息（去重、升序）
├── project_a_transcript.txt   # [时间] 发言人: 内容
└── project_a_assets.md        # 文件附件 + 链接清单
```

`transcript.txt` 片段：

```
[2026-09-07 10:01] (系统) 李四 invited 张三, 王五 to the chat.
[2026-09-07 10:03] 张三: @李四 这个需求也记录下
[2026-09-09 10:46] 李四: <file key="file_v3_xxx" name="需求说明.docx"/>
[2026-09-09 17:39] 王五: https://example.feishu.cn/base/xxxx 这是初版，看下呈现形式
```

## 报告结构

生成的总结报告固定为以下结构（无内容的章节可省略）：

```
# <群名/项目名> · 资料总结
> 资料范围：群名 + 消息条数 + 时间跨度 + 已读文档数
## 一、一句话概览
## 二、关键人物（阵营 | 姓名 | 角色职责）
## 三、时间线（大事记）
## 四、主要脉络（按主题分节）
## 五、当前状态与遗留问题
## 六、群内共享的关键资料清单（含链接）
## 七、风险与建议
```

## 适用 / 不适用

**适用**：项目复盘、工作交接、入职了解背景、跨部门信息对齐、尽调。

**不适用**：只查某一条消息（用 `lark-cli im +messages-search`）；只读单篇文档（用 `lark-cli docs +fetch`）。

## 已知限制

- 图片 / 视频消息在文本里只是占位符（`[图片]`），**不会自动识别内容**；需要时可用 `lark-cli im +messages-resources-download` 单独下载
- 群内共享的**多维表格**无法用 `docs +fetch` 读取（会报 `Unsupported document type 'bitable'`）
- 跨租户文档若无权限会失败，属预期行为
- 只能读取**当前用户有权限访问**的群

更多命令细节、输出契约与踩坑记录见 [`references/lark-cli-recipes.md`](references/lark-cli-recipes.md)。

## 目录结构

```
feishu-group-summary/
├── SKILL.md                        # Skill 定义与工作流
├── scripts/
│   └── lark_group.py               # 抓取 + 渲染主脚本（find / fetch）
├── references/
│   └── lark-cli-recipes.md         # lark-cli 命令速查与踩坑
├── README.md
└── LICENSE
```

## 贡献

欢迎提 Issue / PR。特别欢迎补充：

- 新的消息类型渲染支持
- 文档自动筛选的启发式规则
- 其他 IM 平台（企业微信、钉钉）的适配

## License

[MIT](LICENSE)
