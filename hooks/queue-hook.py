#!/usr/bin/env python3
"""claude-code-queue — per-session FIFO prompt queue for Claude Code.

Gives Codex-style "queue" semantics: a `/queue` message typed while Claude is
busy goes to a waiting area and does NOT interrupt the current turn. When the
turn finishes, the oldest queued item is popped ("queued message popped") and
auto-starts — in the SAME session.

Busy detection uses a self-maintained marker (not Claude Code's `status` field,
which can be stale): a non-`/queue` UserPromptSubmit sets it (a turn started),
and a Stop with an empty queue clears it. A `/queue` while the marker is fresh
is blocked; otherwise it's allowed through so it pops immediately.

Wiring (see README / install.sh):
  UserPromptSubmit hook -> `queue-hook.py enqueue`
  Stop hook             -> `queue-hook.py deliver`

Store layout: ~/.claude/queue/<session_id>/*.msg  + a `.busy` marker file.

Set CLAUDE_QUEUE_DEBUG=1 to log hook payloads to ~/.claude/queue/<sid>/.debug
"""

import glob
import json
import os
import random
import sys
import time

QUEUE_DIR = os.path.expanduser(
    os.environ.get("CLAUDE_QUEUE_DIR", "~/.claude/queue")
)
PREFIX = "/queue"
GLOBAL = "_global"
DEBUG = os.environ.get("CLAUDE_QUEUE_DEBUG", "") == "1"
# A busy marker older than this is treated as stale (crashed/abandoned turn).
BUSY_STALE_SECONDS = 3600


# --------------------------------------------------------------------------- #
# debug
# --------------------------------------------------------------------------- #
def _log(session_id, msg):
    if not DEBUG:
        return
    try:
        d = _session_dir(session_id)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, ".debug"), "a") as fh:
            fh.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# store — per-session subdirectory
# --------------------------------------------------------------------------- #
def _safe(name):
    return "".join(c for c in (name or "") if c.isalnum() or c in "-_") or GLOBAL


def _session_dir(session_id):
    return os.path.join(QUEUE_DIR, _safe(session_id))


def _pending(session_id):
    return sorted(glob.glob(os.path.join(_session_dir(session_id), "*.msg")))


def _pending_all():
    return sorted(glob.glob(os.path.join(QUEUE_DIR, "*", "*.msg")))


def _busy_path(session_id):
    return os.path.join(_session_dir(session_id), ".busy")


def q_add(message, session_id):
    message = message.strip()
    if not message:
        return
    d = _session_dir(session_id)
    os.makedirs(d, exist_ok=True)
    name = f"{time.time_ns()}-{random.randint(0, 999999):06d}.msg"
    with open(os.path.join(d, name), "w", encoding="utf-8") as fh:
        fh.write(message)


def q_pop(session_id):
    files = _pending(session_id)
    if not files:
        return None
    path = files[0]
    try:
        with open(path, "r", encoding="utf-8") as fh:
            msg = fh.read()
    finally:
        try:
            os.remove(path)
        except OSError:
            pass
    return msg


def q_clear(session_id):
    targets = _pending(session_id) if session_id else _pending_all()
    for path in targets:
        try:
            os.remove(path)
        except OSError:
            pass


def _preview(text, width=60):
    flat = " ".join(text.split())
    return flat if len(flat) <= width else flat[: width - 1] + "…"


# --------------------------------------------------------------------------- #
# busy marker — self-maintained, more reliable than the status field
# --------------------------------------------------------------------------- #
def _set_busy(session_id):
    os.makedirs(_session_dir(session_id), exist_ok=True)
    # touch: create if absent, update mtime either way
    path = _busy_path(session_id)
    with open(path, "a"):
        pass
    os.utime(path, None)


def _clear_busy(session_id):
    try:
        os.remove(_busy_path(session_id))
    except OSError:
        pass


def _is_busy(session_id):
    """True iff a turn appears to be active right now (marker fresh)."""
    path = _busy_path(session_id)
    try:
        age = time.time() - os.path.getmtime(path)
    except OSError:
        return False
    if age > BUSY_STALE_SECONDS:
        try:
            os.remove(path)
        except OSError:
            pass
        return False
    return True


# --------------------------------------------------------------------------- #
# /queue prompt parsing
# --------------------------------------------------------------------------- #
def _parse(prompt):
    """Return (action, arg) for a /queue prompt, or None if it isn't one."""
    text = prompt.strip()
    if text == PREFIX or text.startswith(PREFIX + " "):
        rest = text[len(PREFIX):].strip()
        if rest in ("", "list", "status", "ls"):
            return ("list", None)
        if rest in ("clear", "reset", "purge"):
            return ("clear", None)
        return ("add", rest)
    return None


def _read_stdin_json():
    try:
        raw = sys.stdin.read()
        return json.loads(raw) if raw.strip() else {}
    except ValueError:
        return {}


# --------------------------------------------------------------------------- #
# hook modes
# --------------------------------------------------------------------------- #
def mode_enqueue():
    """UserPromptSubmit: mark turns busy, route /queue to the waiting area."""
    data = _read_stdin_json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id", "")

    parsed = _parse(prompt)
    if parsed is None:
        # A real (non-/queue) turn is starting → mark this session busy.
        _set_busy(session_id)
        _log(session_id, f"enqueue(non-queue) busy=set prompt={prompt[:50]!r}")
        sys.exit(0)

    action, arg = parsed

    if action == "list":
        _emit_queue(session_id)
        sys.exit(2)
    if action == "clear":
        q_clear(session_id)
        sys.stderr.write("🧹 已清空本会话队列\n")
        sys.exit(2)

    # action == "add" → waiting area
    q_add(arg, session_id)
    pending = len(_pending(session_id))
    if _is_busy(session_id):
        _log(session_id, f"enqueue(queue) -> BLOCKED (busy) arg={arg[:40]!r}")
        sys.stderr.write(
            f"📝 已入队·等候区（前一条跑完后自动开始，当前 {pending} 条）："
            f"{_preview(arg, 40)}\n"
        )
        sys.exit(2)  # block: do NOT interrupt the running turn
    # idle → let the /queue slash command ack; its Stop pops the item right away
    _log(session_id, f"enqueue(queue) -> ALLOW (idle) arg={arg[:40]!r}")
    sys.exit(0)


def mode_deliver():
    """Stop hook: pop the next queued item for this session, or go idle."""
    data = _read_stdin_json()
    session_id = data.get("session_id", "")

    msg = q_pop(session_id)
    if not msg:
        _clear_busy(session_id)  # nothing queued → this session is now idle
        _log(session_id, "deliver -> idle (queue empty), busy=cleared")
        sys.exit(0)

    # A queued item is starting its own turn → mark busy again so a further
    # /queue during it also waits.
    _set_busy(session_id)
    remaining = len(_pending(session_id))
    tail = f"还剩 {remaining} 条" if remaining else "队列已空"
    _log(session_id, f"deliver -> POP busy=set remaining={remaining}")
    sys.stderr.write(
        f"🔔 queued message popped（{tail}）：{_preview(msg, 50)}\n"
    )
    reason = f"（这是之前排队等候的请求，现在自动开始处理。）\n\n{msg}"
    sys.stdout.write(
        json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False)
    )
    sys.exit(0)


# --------------------------------------------------------------------------- #
# CLI / slash-command modes
# --------------------------------------------------------------------------- #
def mode_add():
    """Manual add (testing). Without a session id it lands in _global."""
    if len(sys.argv) >= 3:
        message = " ".join(sys.argv[3:]) if sys.argv[2] == "--session" else " ".join(sys.argv[2:])
    else:
        message = sys.stdin.read()
    sid = ""
    if len(sys.argv) >= 4 and sys.argv[2] == "--session":
        sid = sys.argv[3]
    q_add(message, sid)
    where = "本会话" if sid else "全局(_global，不会自动投递)"
    pending = len(_pending(sid))
    sys.stdout.write(
        f"📝 已入队 → {where}（当前 {pending} 条）：{_preview(message, 40)}\n"
    )


def mode_list():
    files = _pending_all()
    if not files:
        print("（队列为空）")
        return
    print(f"队列（{len(files)} 条，跨所有会话）：")
    for idx, path in enumerate(files, 1):
        sess = os.path.basename(os.path.dirname(path))[:8]
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            content = "<?>"
        print(f"  {idx}. [{sess}] {_preview(content)}")


def mode_clear():
    # also clear busy markers
    for d in glob.glob(os.path.join(QUEUE_DIR, "*")):
        try:
            os.remove(os.path.join(d, ".busy"))
        except OSError:
            pass
    q_clear("")
    print("🧹 已清空所有会话的队列（及忙标记）")


def mode_count():
    print(len(_pending_all()))


def _emit_queue(session_id):
    files = _pending(session_id)
    if not files:
        sys.stderr.write("（本会话队列为空）\n")
        return
    sys.stderr.write(f"本会话队列（{len(files)} 条）：\n")
    for idx, path in enumerate(files, 1):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            content = "<?>"
        sys.stderr.write(f"  {idx}. {_preview(content)}\n")


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "help"
    handlers = {
        "enqueue": mode_enqueue,
        "deliver": mode_deliver,
        "add": mode_add,
        "list": mode_list,
        "clear": mode_clear,
        "count": mode_count,
    }
    handler = handlers.get(mode)
    if handler is None:
        print(__doc__)
        sys.exit(0)
    handler()


if __name__ == "__main__":
    main()
