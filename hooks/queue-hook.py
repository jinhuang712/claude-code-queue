#!/usr/bin/env python3
"""claude-code-queue — FIFO prompt queue for Claude Code.

Gives you Codex-style "queue" semantics: a message typed while Claude is busy
is NOT injected at the next tool-call boundary. Instead it is stored and
delivered only after the current turn finishes.

Wiring (see README / install.sh):
  UserPromptSubmit hook  -> `queue-hook.py enqueue`   (intercept /queue when busy)
  Stop hook              -> `queue-hook.py deliver`   (drain queue at turn end)
  /queue slash command   -> `queue-hook.py add`       (idle fallback / ack)

Manual ops:
  python3 queue-hook.py add "some task"
  python3 queue-hook.py list
  python3 queue-hook.py count
  python3 queue-hook.py clear
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


# --------------------------------------------------------------------------- #
# queue store (one .msg file per entry, FIFO by filename sort)
# --------------------------------------------------------------------------- #
def _ensure_dir():
    os.makedirs(QUEUE_DIR, exist_ok=True)


def _pending():
    _ensure_dir()
    return sorted(glob.glob(os.path.join(QUEUE_DIR, "*.msg")))


def q_add(message):
    message = message.strip()
    if not message:
        return
    _ensure_dir()
    # nanosecond timestamp keeps FIFO order; rand avoids same-ns collisions.
    name = f"{time.time_ns()}-{random.randint(0, 999999):06d}.msg"
    with open(os.path.join(QUEUE_DIR, name), "w", encoding="utf-8") as fh:
        fh.write(message)


def q_pop():
    files = _pending()
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


def q_clear():
    for path in _pending():
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
    # Anything that is not explicitly "idle" is treated as busy. Over-blocking
    # is safe: the item just waits for the Stop hook to drain it.
    return _session_status(session_id) != "idle"


# --------------------------------------------------------------------------- #
# /queue prompt parsing
# --------------------------------------------------------------------------- #
def _parse(prompt):
    """Return (action, arg) for a /queue prompt, or None if it isn't one.

    action ∈ {"add", "list", "clear"}
    """
    text = prompt.strip()
    if text == PREFIX or text.startswith(PREFIX + " "):
        rest = text[len(PREFIX):].strip()
        if rest in ("", "list", "status", "ls"):
            return ("list", None)
        if rest in ("clear", "reset", "purge"):
            return ("clear", None)
        return ("add", rest)
    return None


# --------------------------------------------------------------------------- #
# hook modes
# --------------------------------------------------------------------------- #
def mode_enqueue():
    """UserPromptSubmit: intercept /queue. Block when busy, allow when idle."""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except ValueError:
        sys.exit(0)  # can't parse → never break the user's prompt
    prompt = data.get("prompt", "")
    session_id = data.get("session_id", "")

    parsed = _parse(prompt)
    if parsed is None:
        sys.exit(0)  # not a /queue prompt → pass through untouched

    action, arg = parsed

    if action == "list":
        _emit_queue()
        sys.exit(2)
    if action == "clear":
        q_clear()
        sys.stderr.write("🧹 队列已清空\n")
        sys.exit(2)

    # action == "add"
    if _is_busy(session_id):
        # Busy: enqueue here and block, so the message is NOT injected mid-turn.
        # The Stop hook drains the queue when the current turn finishes.
        q_add(arg)
        pending = len(_pending())
        sys.stderr.write(
            f"📝 已入队（忙时排队，当前 {pending} 条）：{_preview(arg, 40)}\n"
            f"   → 当前任务跑完后自动开始，不会打断。\n"
        )
        sys.exit(2)  # block: do NOT inject mid-turn
    # Idle: don't enqueue here — let the /queue slash command do it (single
    # enqueue). The Stop hook then drains it immediately.
    sys.exit(0)


def mode_deliver():
    """Stop hook: if the queue is non-empty, refuse to stop and feed next item."""
    msg = q_pop()
    if not msg:
        sys.exit(0)  # empty → allow stop
    remaining = len(_pending())
    tail = f"（队列还剩 {remaining} 条）" if remaining else "（队列已空）"
    reason = (
        f"📋 队列里有之前排队的请求 {tail}，请现在处理它：\n\n{msg}"
    )
    sys.stdout.write(
        json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False)
    )
    sys.exit(0)


# --------------------------------------------------------------------------- #
# CLI / slash-command modes
# --------------------------------------------------------------------------- #
def mode_add():
    if len(sys.argv) >= 3:
        message = " ".join(sys.argv[2:])
    else:
        message = sys.stdin.read()
    q_add(message)
    pending = len(_pending())
    sys.stdout.write(f"📝 已入队（当前 {pending} 条）：{_preview(message, 40)}\n")


def mode_list():
    files = _pending()
    if not files:
        print("（队列为空）")
        return
    print(f"队列（{len(files)} 条，按入队顺序）：")
    for idx, path in enumerate(files, 1):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                content = fh.read()
        except OSError:
            content = "<?>"
        print(f"  {idx}. {_preview(content)}")


def mode_clear():
    q_clear()
    print("🧹 队列已清空")


def mode_count():
    print(len(_pending()))


def _emit_queue():
    files = _pending()
    if not files:
        sys.stderr.write("（队列为空）\n")
        return
    sys.stderr.write(f"队列（{len(files)} 条，按入队顺序）：\n")
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
