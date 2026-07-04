#!/usr/bin/env python3
"""claude-code-queue — per-session FIFO prompt queue for Claude Code.

Gives queue semantics: a `/queue` message typed while Claude is
busy goes to a waiting area and does NOT interrupt the current turn. When the
turn finishes, the oldest queued item is popped ("queued message popped") and
auto-starts — in the SAME session.

Busy detection = (Claude Code `status` == "busy") AND a self-maintained busy
marker. Each signal alone has a blind spot (stale status after a Stop; marker
stuck after an interrupt/Esc), so both must agree. A non-`/queue`
UserPromptSubmit sets the marker; a Stop with an empty queue clears it. See
references/how-it-works.md.

Wiring (see README / install.sh):
  UserPromptSubmit hook -> `queue-hook.py enqueue`
  Stop hook             -> `queue-hook.py deliver`

Store layout: ~/.claude/queue/<session_id>/*.msg  + `.busy` and `.native`
marker files (.native counts normal prompts pending in Claude Code's own queue;
the Stop hook yields to them so real prompts preempt deferred ones).

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
SESSIONS_DIR = os.path.expanduser(
    os.environ.get("CLAUDE_SESSIONS_DIR", "~/.claude/sessions")
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


def _session_status(session_id):
    """Claude Code's own status for this session, read from sessions/*.json."""
    if not session_id:
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


def _marker_set(session_id):
    """True iff our busy marker exists and is fresh (not a crashed turn)."""
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


def _is_busy(session_id):
    """Both signals must agree a turn is active.

    - status == "busy": Claude Code knows when it's really working (covers
      interrupts and pure generation, which fire no hooks).
    - marker set: we set it on turn start / clear it on a normal Stop (covers
      status staleness right after a Stop fires).

    Either alone has a blind spot; the AND closes both. In particular:
    interrupt leaves the marker stuck, but status flips to idle -> not busy;
    a stale "busy" status after Stop is offset by the cleared marker.
    """
    return _session_status(session_id) == "busy" and _marker_set(session_id)


# --------------------------------------------------------------------------- #
# native-pending counter — normal (non-/queue) prompts submitted while busy
# go to Claude Code's own queue. We count them so the Stop hook can yield
# (let Claude deliver the real prompt) instead of draining our queue, which
# would otherwise cut in front of the user's actual request.
# --------------------------------------------------------------------------- #
def _native_path(session_id):
    return os.path.join(_session_dir(session_id), ".native")


def _native_pending(session_id):
    try:
        with open(_native_path(session_id), "r") as fh:
            return max(0, int(fh.read().strip() or "0"))
    except (OSError, ValueError):
        return 0


def _inc_native(session_id):
    os.makedirs(_session_dir(session_id), exist_ok=True)
    with open(_native_path(session_id), "w") as fh:
        fh.write(str(_native_pending(session_id) + 1))


def _dec_native(session_id):
    n = max(0, _native_pending(session_id) - 1)
    try:
        with open(_native_path(session_id), "w") as fh:
            fh.write(str(n))
    except OSError:
        pass
    return n


def _clear_native(session_id):
    try:
        os.remove(_native_path(session_id))
    except OSError:
        pass


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
        # A real (non-/queue) prompt. If Claude is busy it goes to Claude Code's
        # native queue — remember it so the Stop hook yields to it (real prompts
        # preempt our deferred queue). Only track when our queue actually has
        # something to preempt (otherwise we'd accumulate a stale counter that,
        # if interrupted, never decrements and later blocks drainage).
        if _is_busy(session_id) and _pending(session_id):
            _inc_native(session_id)
        _set_busy(session_id)
        _log(session_id, f"enqueue(non-queue) busy=set prompt={prompt[:50]!r}")
        sys.exit(0)

    action, arg = parsed

    if action == "list":
        _emit_queue(session_id)
        sys.exit(2)
    if action == "clear":
        q_clear(session_id)
        sys.stderr.write("🧹 Queue cleared (this session)\n")
        sys.exit(2)

    # action == "add"
    if _is_busy(session_id):
        # busy → waiting area (zero interruption); Stop pops it when the turn ends
        q_add(arg, session_id)
        pending = len(_pending(session_id))
        _log(session_id, f"enqueue(queue) -> BLOCKED (busy) arg={arg[:40]!r}")
        sys.stderr.write(
            f"📝 Queued (runs after the current turn, {pending} pending): "
            f"{_preview(arg, 40)}\n"
        )
        sys.exit(2)  # block: do NOT interrupt the running turn
    # idle → nothing to wait behind. Don't enqueue (that would cost an extra
    # ack round-trip + an ugly Stop-hook pop). Let the /queue slash command
    # handle the request now, as a normal single turn. Mark busy so a /queue
    # arriving during this turn also waits.
    _set_busy(session_id)
    _log(session_id, f"enqueue(queue) -> ALLOW (idle, handle now) arg={arg[:40]!r}")
    sys.exit(0)


def mode_deliver():
    """Stop hook: pop the next queued item for this session, or go idle."""
    data = _read_stdin_json()
    session_id = data.get("session_id", "")

    # Nothing queued → this session is idle. Clear the marker AND any stale
    # native counter (an interrupt can leave .native set with no Stop to
    # decrement it; without this reset it would block future drainage).
    if not _pending(session_id):
        _clear_busy(session_id)
        _clear_native(session_id)
        _log(session_id, "deliver -> idle (queue empty), markers cleared")
        sys.exit(0)

    # A real (non-/queue) prompt is waiting in Claude Code's native queue —
    # yield so Claude delivers IT before our deferred items.
    if _native_pending(session_id) > 0:
        _dec_native(session_id)
        _log(session_id, "deliver -> YIELD to native prompt")
        sys.exit(0)

    # Drain our queue (FIFO).
    msg = q_pop(session_id)
    _set_busy(session_id)
    remaining = len(_pending(session_id))
    tail = f"{remaining} left" if remaining else "queue empty"
    _log(session_id, f"deliver -> POP busy=set remaining={remaining}")
    sys.stderr.write(
        f"🔔 queued message popped ({tail}): {_preview(msg, 50)}\n"
    )
    sys.stdout.write(
        json.dumps({"decision": "block", "reason": msg}, ensure_ascii=False)
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
    where = "this session" if sid else "_global (won't auto-drain)"
    pending = len(_pending(sid))
    sys.stdout.write(
        f"📝 Queued -> {where} ({pending} pending): {_preview(message, 40)}\n"
    )


def mode_list():
    files = _pending_all()
    if not files:
        print("(queue empty)")
        return
    print(f"Queue ({len(files)} items, across all sessions):")
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
        for marker in (".busy", ".native"):
            try:
                os.remove(os.path.join(d, marker))
            except OSError:
                pass
    q_clear("")
    print("🧹 Cleared all sessions' queues (and busy/native markers)")


def mode_count():
    print(len(_pending_all()))


def _emit_queue(session_id):
    files = _pending(session_id)
    if not files:
        sys.stderr.write("(this session's queue is empty)\n")
        return
    sys.stderr.write(f"This session's queue ({len(files)} items):\n")
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
