"""MCP server exposing read-only queries over the local macOS iMessage database."""

import functools
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta

from mcp.server.mcpserver import MCPServer

from db import UNIXTIME, AccessError, display_name, message_text, run_query

mcp = MCPServer("imessage")

# Real messages only: excludes tapbacks/reactions and system events like
# "X named the conversation" or someone joining a group.
REAL_MESSAGE = "m.item_type = 0 AND m.associated_message_type = 0"

SENT_AT = UNIXTIME.format(col="m.date")


def reports_access_errors(fn: Callable) -> Callable:
    """Return the access problem as tool output instead of crashing the server.

    The server must stay up when Full Disk Access is missing, otherwise the client
    only reports a closed connection and the user never sees how to fix it.
    """

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except AccessError as exc:
            return f"Cannot read the iMessage database.\n\n{exc}"

    return wrapper


def _iso(unixtime: float | None) -> str | None:
    if unixtime is None:
        return None
    return datetime.fromtimestamp(unixtime).isoformat(sep=" ", timespec="seconds")


def _cutoff(days: int | None) -> float | None:
    if not days:
        return None
    return (datetime.now() - timedelta(days=days)).timestamp()


def _chat_label(row: sqlite3.Row) -> str:
    """Prefer a group's set name, else the contact name, else the raw handle."""
    if row["display_name"]:
        return row["display_name"]
    return display_name(row["chat_identifier"])


@mcp.tool()
@reports_access_errors
def list_chats(limit: int = 30, days: int | None = None) -> str:
    """List conversations ordered by most recent activity.

    Args:
        limit: Maximum number of conversations to return.
        days: Only include conversations active in the last N days. Omit for all time.
    """
    cutoff = _cutoff(days)
    sql = f"""
        SELECT c.ROWID AS chat_id,
               c.chat_identifier,
               c.display_name,
               c.style,
               COUNT(m.ROWID) AS message_count,
               SUM(m.is_from_me) AS sent_count,
               MAX({SENT_AT}) AS last_at
          FROM chat c
          JOIN chat_message_join cmj ON cmj.chat_id = c.ROWID
          JOIN message m ON m.ROWID = cmj.message_id
         WHERE {REAL_MESSAGE}
           {"AND " + SENT_AT + " >= ?" if cutoff else ""}
         GROUP BY c.ROWID
         ORDER BY last_at DESC
         LIMIT ?
    """
    params = ([cutoff] if cutoff else []) + [limit]
    rows = run_query(sql, params)
    if not rows:
        return "No conversations found."

    lines = []
    for r in rows:
        kind = "group" if r["style"] == 43 else "direct"
        received = r["message_count"] - (r["sent_count"] or 0)
        lines.append(
            f"[chat_id={r['chat_id']}] {_chat_label(r)} ({kind}) — "
            f"{r['message_count']} messages ({r['sent_count'] or 0} sent / {received} received), "
            f"last {_iso(r['last_at'])}"
        )
    return "\n".join(lines)


@mcp.tool()
@reports_access_errors
def get_conversation(
    chat_id: int | None = None,
    contact: str | None = None,
    limit: int = 100,
    days: int | None = None,
) -> str:
    """Read messages from one conversation, oldest to newest.

    Args:
        chat_id: Conversation id from list_chats. Preferred, and required for group chats.
        contact: Phone number, email, or contact name to match instead of chat_id.
        limit: Maximum number of messages to return (the most recent ones).
        days: Only include messages from the last N days.
    """
    if chat_id is None and not contact:
        return "Provide either chat_id or contact."

    where = [REAL_MESSAGE]
    params: list = []
    if chat_id is not None:
        where.append("cmj.chat_id = ?")
        params.append(chat_id)
    if contact:
        where.append("(h.id LIKE ? OR c.display_name LIKE ? OR c.chat_identifier LIKE ?)")
        params += [f"%{contact}%"] * 3
    cutoff = _cutoff(days)
    if cutoff:
        where.append(f"{SENT_AT} >= ?")
        params.append(cutoff)

    sql = f"""
        SELECT m.text, m.attributedBody, m.is_from_me, m.cache_has_attachments,
               h.id AS handle, {SENT_AT} AS sent_at
          FROM message m
          JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
          JOIN chat c ON c.ROWID = cmj.chat_id
          LEFT JOIN handle h ON h.ROWID = m.handle_id
         WHERE {" AND ".join(where)}
         ORDER BY m.date DESC, m.ROWID DESC
         LIMIT ?
    """
    rows = run_query(sql, params + [limit])
    if not rows:
        return "No messages found."

    lines = []
    for r in reversed(rows):
        who = "Me" if r["is_from_me"] else display_name(r["handle"])
        body = message_text(r)
        if not body and r["cache_has_attachments"]:
            body = "[attachment]"
        lines.append(f"[{_iso(r['sent_at'])}] {who}: {body}")
    return "\n".join(lines)


@mcp.tool()
@reports_access_errors
def search_messages(
    query: str,
    contact: str | None = None,
    days: int | None = None,
    from_me: bool | None = None,
    limit: int = 50,
    scan_limit: int = 50000,
) -> str:
    """Search message text across all conversations.

    Args:
        query: Text to search for (case-insensitive substring match).
        contact: Restrict to conversations with this phone, email, or contact name.
        days: Only search messages from the last N days.
        from_me: True for only your messages, False for only received ones.
        limit: Maximum number of matches to return.
        scan_limit: Most recent N messages to examine. Raise it to search further back.
    """
    # Messages on Ventura+ leave `text` NULL and store the body in attributedBody.
    # That blob cannot be matched in SQL (embedded NULs truncate CAST(... AS TEXT)),
    # so SQL narrows to candidates and the real matching happens in Python.
    where = [REAL_MESSAGE, "(m.text LIKE ? OR m.text IS NULL)"]
    params: list = [f"%{query}%"]
    if contact:
        where.append("(h.id LIKE ? OR c.display_name LIKE ? OR c.chat_identifier LIKE ?)")
        params += [f"%{contact}%"] * 3
    cutoff = _cutoff(days)
    if cutoff:
        where.append(f"{SENT_AT} >= ?")
        params.append(cutoff)
    if from_me is not None:
        where.append("m.is_from_me = ?")
        params.append(1 if from_me else 0)

    sql = f"""
        SELECT m.text, m.attributedBody, m.is_from_me,
               h.id AS handle, c.ROWID AS chat_id,
               c.display_name, c.chat_identifier, {SENT_AT} AS sent_at
          FROM message m
          JOIN chat_message_join cmj ON cmj.message_id = m.ROWID
          JOIN chat c ON c.ROWID = cmj.chat_id
          LEFT JOIN handle h ON h.ROWID = m.handle_id
         WHERE {" AND ".join(where)}
         ORDER BY m.date DESC, m.ROWID DESC
         LIMIT ?
    """
    rows = run_query(sql, params + [scan_limit])

    needle = query.lower()
    lines = []
    for r in rows:
        body = message_text(r)
        if needle not in body.lower():
            continue
        who = "Me" if r["is_from_me"] else display_name(r["handle"])
        lines.append(
            f"[{_iso(r['sent_at'])}] {_chat_label(r)} (chat_id={r['chat_id']}) — {who}: {body}"
        )
        if len(lines) >= limit:
            break
    if not lines:
        return f"No messages matching {query!r}."
    note = ""
    if len(rows) >= scan_limit:
        note = f"\n\n(Searched the {scan_limit} most recent messages; raise scan_limit to go further back.)"
    return "\n".join(lines) + note


@mcp.tool()
@reports_access_errors
def contact_stats(days: int | None = 365, limit: int = 25) -> str:
    """Rank the people you message most, with volume, balance, and time since last contact.

    Args:
        days: Window to analyse, in days. Omit for all time.
        limit: Maximum number of people to return.
    """
    cutoff = _cutoff(days)
    sql = f"""
        SELECT h.id AS handle,
               COUNT(m.ROWID) AS total,
               SUM(m.is_from_me) AS sent,
               MIN({SENT_AT}) AS first_at,
               MAX({SENT_AT}) AS last_at
          FROM message m
          JOIN handle h ON h.ROWID = m.handle_id
         WHERE {REAL_MESSAGE}
           {"AND " + SENT_AT + " >= ?" if cutoff else ""}
         GROUP BY h.id
    """
    params = [cutoff] if cutoff else []
    rows = run_query(sql, params)
    if not rows:
        return "No messages found in that window."

    # One person often has several handles (phone + email); merge them by name.
    people: dict[str, dict] = {}
    for r in rows:
        name = display_name(r["handle"])
        p = people.setdefault(name, {"total": 0, "sent": 0, "last_at": 0.0})
        p["total"] += r["total"]
        p["sent"] += r["sent"] or 0
        p["last_at"] = max(p["last_at"], r["last_at"])

    ranked = sorted(people.items(), key=lambda kv: kv[1]["total"], reverse=True)[:limit]
    now = datetime.now().timestamp()
    window = f"last {days} days" if days else "all time"
    lines = [f"Top {len(ranked)} contacts by message volume ({window}):"]
    for name, p in ranked:
        received = p["total"] - p["sent"]
        silent_days = int((now - p["last_at"]) / 86400)
        lines.append(
            f"{name}: {p['total']} messages "
            f"(sent/received {p['sent']}/{received}), last contact {silent_days}d ago "
            f"({_iso(p['last_at'])})"
        )
    return "\n".join(lines)


def main() -> None:
    # Deliberately no database preflight: starting successfully lets the tools
    # explain a missing-permission problem in a reply the user can actually read.
    mcp.run()


if __name__ == "__main__":
    main()
