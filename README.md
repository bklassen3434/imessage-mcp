# imessage-mcp

A read-only MCP server that lets Claude query your local iMessage database
(`~/Library/Messages/chat.db`). Everything runs on your Mac; no messages leave it.

## Setup

```bash
./install.sh
```

This installs `uv` if needed, fetches dependencies, and registers the server with
the Claude desktop app and/or Claude Code — whichever it finds. It is safe to
re-run, and it preserves any other MCP servers already configured.

Then grant Full Disk Access, which macOS requires for `chat.db`:

1. System Settings → Privacy & Security → Full Disk Access
2. Enable **Claude**
3. **Fully quit and reopen Claude** (Cmd-Q — closing the window is not enough)

Without this, every tool returns an access error explaining the fix.

Non-technical users should follow [SETUP.md](SETUP.md) instead, which covers the
same ground step by step and uses the double-clickable `Install.command`.

Keep the folder where it is after installing — the registered path points at it.

## Tools

| Tool | What it does |
| --- | --- |
| `list_chats` | Conversations by recent activity, with per-chat sent/received counts |
| `get_conversation` | Messages from one chat, by `chat_id` or contact name |
| `search_messages` | Substring search across all messages, filterable by contact, recency, and direction |
| `contact_stats` | People ranked by volume, with sent/received balance and days since last contact |

Ask things like "who have I not messaged in over a month?", "show my chat with
Aditya from last week", or "search my messages for 'burnout'".

## Notes

- **Read-only.** The database is opened with `mode=ro`. If Messages holds it in
  WAL mode, the server falls back to a temp-directory snapshot copy. It never writes.
- **Contact names** come from the macOS Contacts database when it is readable;
  otherwise you see raw phone numbers and emails.
- **Reactions and system events** (tapbacks, "X named the conversation") are excluded
  from all results, so counts reflect real messages.
- **Message text on Ventura+** is often stored in a binary `attributedBody` blob
  rather than the `text` column. The server decodes it, which is why
  `search_messages` scans and filters in Python rather than purely in SQL.
  `scan_limit` (default 50000) bounds how far back a search looks.
- **`IMESSAGE_DB`** env var points the server at a copy or backup instead of the
  live database.
