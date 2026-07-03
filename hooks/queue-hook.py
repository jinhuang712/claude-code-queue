#!/usr/bin/env python3
"""claude-code-queue — per-session FIFO prompt queue for Claude Code.

Gives Codex-style "queue" semantics: a message typed while Claude is busy is
NOT injected at the next tool-call boundary. It is stored and delivered only
after the current turn finishes — in the SAME session that queued it.

Wiring (see README / install.sh):
  UserPromptSubmit hook -> `queue-hook.py enqueue`  (intercept /queue, store)
  Stop hook             -> `queue-hook.py deliver`  (drain THIS session's queue)
  /queue slash command  -> just acks (the hook already stored the message)

Store layout: ~/.claude/queue/<session_id>/*.msg  (one file per item, FIFO)

Set CLAUDE_QUEUE_DEBUG=1 to log hook payloads to ~/.claude/queue/.debug.log
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
SESSIONS_DIR = os.path.expanduser("~/.claude/sessions")
PREFIX = "/queue"
GLOBAL = "_global"
DEBUG = os.environ.get("CLAUDE_QUEUE_DEBUG", "") == "1"


# --------------------------------------------------------------------------- #
# debug
# --------------------------------------------------------------------------- #
def _log(msg):
    if not DEBUG:
        return
    try:
        os.makedirs(QUEUE_DIR, exist_ok=True)
        with open(os.path.join(QUEUE_DIR, ".debug.log"), "a") as fh:
            fh.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# store — per-session subdirectory, one .msg file per entry, FIFO by name
# --------------------------------------------------------------------------- #
def _safe(name):
    return "".join(c for c in (name or "") if c.isalnum() or c in "-_") or GLOBAL


def _session_dir(session_id):
    return os.path.join(QUEUE_DIR, _safe(session_id))


def _pending(session_id):
    return sorted(glob.glob(os.path.join(_session_dir(session_id), "*.msg")))


def _pending_all():
    return sorted(glob.glob(os.path.join(QUEUE_DIR, "*", "*.msg")))


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
# busy detection via the session status field written by Claude Code
# --------------------------------------------------------------------------- #
def _session_status(session_id):
    if not session_id or not os.path.isdir(SESSIONS_DIR):
        return "unknown"
    for path in glob.glob(os.path.join(SESSIONS_DIR, "*.json")):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
        except (OSError, ValueError):
            continue
        if data.get("sessionId") == session_id:
            return data.get("status", "unknown")
    return "unknown"


def _is_busy(session_id):
    # Anything not explicitly "idle" is treated as busy (safe over-block).
    return _session_status(session_id) != "idle"


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
    """UserPromptSubmit: store /queue message in THIS session; block if busy."""
    data = _read_stdin_json()
    prompt = data.get("prompt", "")
    session_id = data.get("session_id", "")
    _log(f"enqueue session={session_id} status={_session_status(session_id)} "
         f"prompt={prompt[:60]!r}")

    parsed = _parse(prompt)
    if parsed is None:
        sys.exit(0)  # not a /queue prompt → pass through untouched

    action, arg = parsed

    if action == "list":
        _emit_queue(session_id)
        sys.exit(2)
    if action == "clear":
        q_clear(session_id)
        sys.stderr.write("🧹 已清空本会话队列\n")
        sys.exit(2)

    # action == "add" — store to THIS session, always (busy or idle)
    q_add(arg, session_id)
    pending = len(_pending(session_id))

    if _is_busy(session_id):
        sys.stderr.write(
            f"📝 已入队（本任务跑完后自动开始，当前 {pending} 条）："
            f"{_preview(arg, 40)}\n"
        )
        sys.exit(2)  # block: do NOT inject mid-turn
    # idle: let the /queue slash command ack; its Stop then drains the item.
    sys.exit(0)


def mode_deliver():
    """Stop hook: drain THIS session's queue only (no cross-session theft)."""
    data = _read_stdin_json()
    session_id = data.get("session_id", "")
    _log(f"deliver session={session_id} pending={len(_pending(session_id))}")

    msg = q_pop(session_id)
    if not msg:
        sys.exit(0)  # nothing for this session → allow stop
    remaining = len(_pending(session_id))
    tail = f"还剩 {remaining} 条" if remaining else "队列已空"
    reason = f"📋 [队列任务 · {tail}] 请处理这个之前排队的请求：\n\n{msg}"
    sys.stdout.write(
        json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False)
    )
    sys.exit(0)


# --------------------------------------------------------------------------- #
# CLI / slash-command modes
# --------------------------------------------------------------------------- #
def mode_add():
    """Manual add. Without a session id it lands in _global (won't auto-drain)."""
    if len(sys.argv) >= 3:
        message = " ".join(sys.argv[2:])
    else:
        message = sys.stdin.read()
    sid = os.environ.get("CLAUDE_SESSION_ID", "")
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
    q_clear("")
    print("🧹 已清空所有会话的队列")


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
