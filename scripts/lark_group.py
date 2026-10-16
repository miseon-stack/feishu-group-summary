#!/usr/bin/env python3
"""飞书群聊全量抓取 + 可读化渲染工具（基于 lark-cli）。

用法：
  # 1) 只搜索群，拿到 chat_id
  python3 lark_group.py find "项目名关键词"

  # 2) 抓取某个群的全部消息，并自动渲染成可读文本 + 资料清单
  python3 lark_group.py fetch --chat "项目A沟通群" --out ./lark-research/group1
  python3 lark_group.py fetch --chat oc_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx --out ./out --prefix group1

产物（--out 目录下）：
  <prefix>_messages.json    原始消息（已去重、按时间升序）
  <prefix>_transcript.txt   可读聊天记录，一行一条
  <prefix>_assets.md        群内分享的文件附件 + 链接清单

依赖：lark-cli（已登录，user 身份可用）。
"""
import argparse
import json
import os
import re
import subprocess
import sys

IDENTITY = "user"


def run_cli(args):
    """执行 lark-cli 并解析 JSON 输出。"""
    proc = subprocess.run(["lark-cli"] + args, capture_output=True, text=True)
    out = (proc.stdout or "").strip()
    if not out:
        sys.stderr.write("[lark-cli 无输出]\n" + (proc.stderr or "") + "\n")
        sys.exit(1)
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        sys.stderr.write("无法解析 lark-cli 输出（非 JSON）：\n" + out[:2000] + "\n")
        sys.exit(1)


def resolve_chat(query, identity):
    """query 可以是 oc_xxx 或群名。群名走 chat-search，返回候选列表。"""
    if query.startswith("oc_"):
        return [{"chat_id": query, "name": query}]
    resp = run_cli(["im", "+chat-search", "--query", query, "--as", identity])
    if not resp.get("ok"):
        sys.stderr.write("群搜索失败：" + json.dumps(resp.get("error"), ensure_ascii=False) + "\n")
        sys.exit(1)
    return resp.get("data", {}).get("chats") or []


def fetch_all(chat_id, identity, start=None, end=None, page_limit=25, max_rounds=200):
    """分轮拉取直到 has_more=false，累积所有消息。"""
    msgs, token, seen, rounds = [], None, set(), 0
    while rounds < max_rounds:
        args = [
            "im", "+chat-messages-list",
            "--chat-id", chat_id,
            "--as", identity,
            "--order", "asc",
            "--page-size", "50",
            "--page-all",
            "--page-limit", str(page_limit),
            "--no-reactions",
        ]
        if start:
            args += ["--start", start]
        if end:
            args += ["--end", end]
        if token:
            args += ["--page-token", token]
        resp = run_cli(args)
        if not resp.get("ok"):
            sys.stderr.write("消息拉取失败：" + json.dumps(resp.get("error"), ensure_ascii=False) + "\n")
            break
        data = resp.get("data", {})
        batch = data.get("messages") or []
        before = len(msgs)
        for m in batch:
            mid = m.get("message_id")
            if mid and mid not in seen:
                seen.add(mid)
                msgs.append(m)
        token = data.get("page_token")
        has_more = data.get("has_more")
        rounds += 1
        if len(msgs) == before:  # 没有新消息，避免死循环
            break
        if not has_more or not token:
            break
    msgs.sort(key=lambda m: (m.get("create_time", ""), int(m.get("message_position") or 0)))
    return msgs


def render_line(m):
    t = m.get("msg_type")
    name = (m.get("sender") or {}).get("name") or ""
    ct = m.get("create_time", "")
    c = (m.get("content") or "").strip()
    if t == "system":
        return f"[{ct}] (系统) {c}"
    if t == "image":
        return f"[{ct}] {name}: [图片]"
    if t == "video_chat":
        return f"[{ct}] {name}: [视频会议]"
    if t == "nonsupport":
        return f"[{ct}] {name}: [不支持的消息类型]"
    if t == "sticker":
        return f"[{ct}] {name}: [表情]"
    c = re.sub(r"!\[[^\]]*\]\([^)]*\)", "[图片]", c)
    c = re.sub(r"<img[^>]*>", "[图片]", c)
    c = c.replace("\n", " / ")
    return f"[{ct}] {name}: {c}".rstrip()


URL_RE = re.compile(r"https?://[^\s\)\]\"<>]*")
MENTION_TAIL = re.compile(r"@[^\s@]*$")


def render_assets(msgs):
    files, links = [], {}
    for m in msgs:
        c = m.get("content") or ""
        t = m.get("create_time", "")
        who = (m.get("sender") or {}).get("name") or ""
        for nm in re.findall(r"<file [^>]*name=\"([^\"]+)\"", c):
            files.append((t, who, nm))
        for u in URL_RE.findall(c):
            u = MENTION_TAIL.sub("", u)  # 去掉链接后面粘上的 @某人
            u = u.rstrip(".,;，。；")
            links.setdefault(u, []).append(t)
    lines = ["# 群内资料清单\n", "## 文件附件\n"]
    if files:
        for t, who, nm in files:
            lines.append(f"- [{t}] {who} — {nm}")
    else:
        lines.append("- （无）")
    lines += ["\n## 链接\n"]
    for u, ts in links.items():
        lines.append(f"- ({len(ts)}次) {u}")
    return "\n".join(lines) + "\n"


def cmd_find(args):
    chats = resolve_chat(args.query, args.as_identity)
    if not chats:
        print("未找到匹配的群。")
        return
    for c in chats:
        print(f"{c.get('chat_id')}\t{c.get('name')}\t"
              f"external={c.get('external')}\tmember_count={c.get('member_count', '-')}")


def cmd_fetch(args):
    os.makedirs(args.out, exist_ok=True)
    chats = resolve_chat(args.chat, args.as_identity)
    if not chats:
        sys.stderr.write("未找到匹配的群，请先用 find 子命令确认群名。\n")
        sys.exit(1)
    if len(chats) > 1:
        exact = [c for c in chats if c.get("name") == args.chat]
        if len(exact) == 1:
            chats = exact
        else:
            print("匹配到多个群，请指定 chat_id：")
            for c in chats:
                print(f"  {c.get('chat_id')}\t{c.get('name')}")
            sys.exit(2)
    chat = chats[0]
    chat_id, name = chat["chat_id"], chat.get("name") or chat_id
    prefix = args.prefix or "group"
    print(f"→ 群：{name} ({chat_id})")

    msgs = fetch_all(chat_id, args.as_identity, args.start, args.end)
    print(f"→ 共拉取 {len(msgs)} 条消息")

    json_path = os.path.join(args.out, f"{prefix}_messages.json")
    with open(json_path, "w") as f:
        json.dump({"chat_id": chat_id, "name": name, "messages": msgs}, f, ensure_ascii=False, indent=1)

    txt_path = os.path.join(args.out, f"{prefix}_transcript.txt")
    with open(txt_path, "w") as f:
        f.write("\n".join(render_line(m) for m in msgs) + "\n")

    asset_path = os.path.join(args.out, f"{prefix}_assets.md")
    with open(asset_path, "w") as f:
        f.write(render_assets(msgs))

    print(f"→ 已写出：\n   {json_path}\n   {txt_path}\n   {asset_path}")


def main():
    ap = argparse.ArgumentParser(description="飞书群聊抓取与渲染")
    ap.add_argument("--as-identity", default=IDENTITY, choices=["user", "bot"])
    sub = ap.add_subparsers(dest="cmd", required=True)

    p1 = sub.add_parser("find", help="按群名搜索群，输出 chat_id")
    p1.add_argument("query")
    p1.set_defaults(func=cmd_find)

    p2 = sub.add_parser("fetch", help="抓取群全量消息并渲染")
    p2.add_argument("--chat", required=True, help="oc_xxx 或群名")
    p2.add_argument("--out", required=True, help="输出目录")
    p2.add_argument("--prefix", default="group", help="输出文件名前缀")
    p2.add_argument("--start", help="起始时间 ISO8601")
    p2.add_argument("--end", help="结束时间 ISO8601")
    p2.set_defaults(func=cmd_fetch)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
