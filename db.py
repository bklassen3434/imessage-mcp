"""Read-only access to the macOS iMessage (chat.db) and Contacts databases."""

import glob
import os
import shutil
import sqlite3
import threading
import tempfile

# IMESSAGE_DB lets you point at a copy or backup instead of the live database.
CHAT_DB = os.environ.get(
    "IMESSAGE_DB", os.path.expanduser("~/Library/Messages/chat.db")
)
ADDRESSBOOK_GLOB = os.path.expanduser(
    "~/Library/Application Support/AddressBook/Sources/*/AddressBook-v22.abcddb"
)

# chat.db stores dates as nanoseconds since 2001-01-01 (older rows use seconds).
# This expression normalises either form to a unix timestamp.
UNIXTIME = (
    "(CASE WHEN {col} > 1000000000000 THEN {col}/1000000000 ELSE {col} END + 978307200)"
)


class AccessError(RuntimeError):
    """Raised when the database exists but cannot be read (missing Full Disk Access)."""


def _connect_readonly(path: str) -> sqlite3.Connection:
    """Open a database read-only, falling back to a snapshot copy if it is locked.

    Messages holds chat.db in WAL mode; a plain read-only open fails when the
    -wal file is not readable, so we copy the db and its sidecars to temp.
    """
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True, check_same_thread=False)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        return conn
    except sqlite3.Error:
        pass

    snapshot_dir = os.path.join(tempfile.gettempdir(), "imessage-mcp-snapshot")
    os.makedirs(snapshot_dir, exist_ok=True)
    dest = os.path.join(snapshot_dir, os.path.basename(path))
    try:
        for suffix in ("", "-wal", "-shm"):
            src = path + suffix
            if os.path.exists(src):
                shutil.copy2(src, dest + suffix)
        conn = sqlite3.connect(f"file:{dest}?mode=ro", uri=True, check_same_thread=False)
        conn.execute("SELECT 1 FROM sqlite_master LIMIT 1").fetchall()
        return conn
    except (OSError, sqlite3.Error) as exc:
        raise AccessError(
            f"Cannot read {path}. Grant Full Disk Access to the app running this "
            "server (System Settings > Privacy & Security > Full Disk Access), "
            "then fully quit and reopen it."
        ) from exc


_chat_conn: sqlite3.Connection | None = None
_chat_lock = threading.Lock()


def chat_db() -> sqlite3.Connection:
    global _chat_conn
    if _chat_conn is None:
        if not os.path.exists(CHAT_DB):
            raise AccessError(f"No iMessage database at {CHAT_DB}.")
        _chat_conn = _connect_readonly(CHAT_DB)
        _chat_conn.row_factory = sqlite3.Row
    return _chat_conn


_contacts: dict[str, str] | None = None


def _normalise(handle: str) -> str:
    """Reduce a phone number to its last 10 digits so formats match; emails pass through."""
    if "@" in handle:
        return handle.strip().lower()
    digits = "".join(c for c in handle if c.isdigit())
    return digits[-10:] if len(digits) >= 10 else digits


def run_query(sql: str, params: list | None = None) -> list[sqlite3.Row]:
    """Run a read-only query. Serialised because MCP calls tools from worker threads."""
    conn = chat_db()
    with _chat_lock:
        return conn.execute(sql, params or []).fetchall()


def contacts() -> dict[str, str]:
    """Map normalised handles to display names. Empty if Contacts is unavailable."""
    global _contacts
    if _contacts is not None:
        return _contacts

    _contacts = {}
    for path in glob.glob(ADDRESSBOOK_GLOB):
        try:
            conn = _connect_readonly(path)
        except AccessError:
            continue
        try:
            rows = conn.execute(
                """
                SELECT r.ZFIRSTNAME, r.ZLASTNAME, r.ZORGANIZATION,
                       p.ZFULLNUMBER AS phone, e.ZADDRESS AS email
                  FROM ZABCDRECORD r
                  LEFT JOIN ZABCDPHONENUMBER p ON p.ZOWNER = r.Z_PK
                  LEFT JOIN ZABCDEMAILADDRESS e ON e.ZOWNER = r.Z_PK
                """
            ).fetchall()
        except sqlite3.Error:
            continue
        finally:
            conn.close()

        for first, last, org, phone, email in rows:
            name = " ".join(p for p in (first, last) if p) or org
            if not name:
                continue
            for handle in (phone, email):
                if handle:
                    _contacts.setdefault(_normalise(handle), name)
    return _contacts


def display_name(handle: str | None) -> str:
    if not handle:
        return "Unknown"
    return contacts().get(_normalise(handle), handle)


def decode_attributed_body(blob: bytes | None) -> str | None:
    """Pull plain text out of the NSAttributedString archive newer messages use.

    macOS Ventura+ often leaves message.text NULL and stores the body here.
    """
    if not blob:
        return None
    try:
        chunk = blob.split(b"NSString")[1][5:]
        if chunk[0] == 0x81:
            length = int.from_bytes(chunk[1:3], "little")
            chunk = chunk[3:]
        else:
            length = chunk[0]
            chunk = chunk[1:]
        text = chunk[:length].decode("utf-8", errors="replace").strip()
        return text or None
    except (IndexError, UnicodeDecodeError):
        return None


def message_text(row: sqlite3.Row) -> str:
    text = row["text"] if "text" in row.keys() else None
    if text:
        return text
    if "attributedBody" in row.keys():
        return decode_attributed_body(row["attributedBody"]) or ""
    return ""
