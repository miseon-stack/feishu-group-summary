# lark-cli 命令速查与踩坑记录

本文件为 `feishu-group-summary` skill 的参考手册。命令均在**用户身份**（`--as user`）下验证通过。

## 1. 授权与身份

```bash
lark-cli auth status          # 查看身份；注意：该命令不接受 --format
```

- 读群消息必须 `--as user`（bot 身份读用户资源会「空成功」而不是报错）。
- 关注 `identities.user.status == "ready"` 与 `tokenStatus == "valid"`。
- 未授权 / 过期 → `lark-cli auth login`，把 `verification_url` 用
  `lark-cli auth qrcode --output qr.png "<url>"` 生成二维码给用户扫码。

## 2. 找群

```bash
lark-cli im +chat-search --query "项目名关键词" --as user
```

返回 `data.chats[]`，每项含 `chat_id`(oc_xxx)、`name`、`external`(是否外部群)、`owner_id`。

## 3. 拉群消息

```bash
lark-cli im +chat-messages-list \
  --chat-id oc_xxx \
  --as user \
  --order asc \
  --page-size 50 \
  --page-all \
  --page-limit 25 \
  --no-reactions
```

要点：
- 消息在 `data.messages[]`，另有 `data.has_more` / `data.page_token`。
- **单次调用有上限**（`--page-all --page-limit N` 最多 N 页）。`has_more=true` 时，
  把 `data.page_token` 传给下一次 `--page-token` 继续拉，直到 `has_more=false`。
- `--order asc` 便于按时间线性阅读；`--no-reactions` 跳过表情富化（更快、更省）。
- 常用时间过滤：`--start "2026-09-01T00:00:00+08:00" --end "..."`。
- 加 `--concise` 可得到精简 Markdown（但会丢失部分结构，本 skill 不用）。

### 消息字段

| 字段 | 说明 |
|-|-|
| `msg_type` | `text` / `post` / `image` / `file` / `system` / `interactive` / `share_calendar_event` / `video_chat` / `todo` / `nonsupport` / `sticker` 等 |
| `content` | 已渲染的字符串。文件为 `<file key="..." name="..."/>`；图片为 `[Image: img_xxx]`；`post` 内可能有 `![Image](img_xxx)` |
| `sender.name` | 发言人名（服务端提供，无需额外权限；系统消息无） |
| `create_time` | `YYYY-MM-DD HH:MM` |
| `message_position` | 排序用序号 |
| `reply_to` | 被回复消息的 message_id |

### 下载图片 / 附件（按需）

```bash
lark-cli im +messages-resources-download --message-id om_xxx --file-key <key> --type image --output-dir ./res --as user
```
文件夹类资源需先展开：`lark-cli im files folder --recursive --file-key <key> --srctype message --srcid <om_xxx>`。

## 4. 读群内共享文档

```bash
lark-cli docs +fetch --doc "<url 或 token>" --doc-format markdown --as user
```

- `data.document.content` 即正文（markdown 或 xml）。
- 也支持 `--scope outline|section|keyword`、`--keyword "词1|词2"` 做局部读取（大文档省 token）。

**失败兜底**：
- `code 3380002 Unsupported document type 'bitable'` → 该 wiki/链接实际指向**多维表格**，`docs +fetch` 不支持。改走 `lark-base` / `lark-sheets` 相关 skill，或跳过并在报告中标注。
- 跨租户文档（客户自己云盘里的 `xxx.feishu.cn/docx/...`）若无权限会报权限错误 → 跳过，不要卡住。
- 链接尾巴常粘上 `@某人`（如 `...from_copylink@林极铮`），拉取前先截断。

## 5. 输出契约（重要）

- 成功判定用 **`ok == true`**（或进程退出码 0），**不要用 `code == 0`**。
  成功信封里没有顶层 `code`/`msg`；`code` 只出现在 `error` 内。
- 文件路径类参数（`--file`/`--output`/`--output-dir`/`@file`）**只接受 cwd 下的相对路径**，绝对路径会报 `unsafe file path`。
- 退出码 `10` = 高风险写操作确认门禁（读操作不会遇到）；遇到时向用户确认后，把提示的确认 flag 追加到原命令末尾重试。

## 6. 已知踩坑

| 现象 | 处理 |
|-|-|
| `auth status --format json` 报 unknown flag | `auth status` 不接受 `--format`，直接裸跑 |
| 群搜索结果里有多条同名/近名 | 用 chat_id 精确定位 |
| 消息条数卡在整百附近 | 是分页上限，继续传 `page_token` |
| `content` 为 `[Invalid text JSON]` | 少数消息内容解析失败，属正常，跳过即可 |
| `content` 为 `(系统) ... invited ...` | 入群/改名等系统消息，可按需过滤 |
| 外部群读不到 | 确认当前用户是该群成员；非成员无法读取 |
| 消息里有 `@_user_1` 占位 | 是 @提及的内部占位符，可对照 `mentions[]` 还原人名 |
