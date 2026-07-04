"""Tests for queue-hook.py.

The hook file is `queue-hook.py` (hyphenated), so it can't be imported as a
module — we drive it via subprocess with isolated CLAUDE_QUEUE_DIR and
CLAUDE_SESSIONS_DIR so nothing touches the real ~/.claude.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

HOOK = Path(__file__).resolve().parent.parent / "hooks" / "queue-hook.py"


def run(mode, stdin_data=None, env=None, args=None):
    proc_env = os.environ.copy()
    if env:
        proc_env.update({k: str(v) for k, v in env.items()})
    cmd = [sys.executable, str(HOOK), mode, *(args or [])]
    proc = subprocess.run(
        cmd, input=stdin_data, capture_output=True, text=True, env=proc_env
    )
    return proc.returncode, proc.stdout, proc.stderr


def make_env(tmp_path, session_statuses):
    qdir = tmp_path / "queue"
    sdir = tmp_path / "sessions"
    qdir.mkdir()
    sdir.mkdir()
    for sid, status in session_statuses.items():
        (sdir / f"{sid}.json").write_text(
            json.dumps({"sessionId": sid, "status": status})
        )
    return {"CLAUDE_QUEUE_DIR": str(qdir), "CLAUDE_SESSIONS_DIR": str(sdir)}


def enqueue(prompt, sid, env):
    return run("enqueue", json.dumps({"prompt": prompt, "session_id": sid}), env)


def deliver(sid, env):
    return run("deliver", json.dumps({"session_id": sid}), env)


def msgs(tmp_path, sid):
    return sorted(p.read_text() for p in (tmp_path / "queue" / sid).glob("*.msg"))


# -- parsing / routing ----------------------------------------------------- #
def test_non_queue_prompt_sets_busy_and_allows(tmp_path):
    env = make_env(tmp_path, {"s1": "idle"})
    rc, out, err = enqueue("just chatting", "s1", env)
    assert rc == 0
    assert (tmp_path / "queue" / "s1" / ".busy").exists()


def test_queue_list_blocks(tmp_path):
    env = make_env(tmp_path, {"s1": "idle"})
    rc, out, err = enqueue("/queue list", "s1", env)
    assert rc == 2  # blocked, info-only


def test_queue_clear_blocks(tmp_path):
    env = make_env(tmp_path, {"s1": "busy"})
    enqueue("working", "s1", env)
    enqueue("/queue task", "s1", env)
    rc, out, err = enqueue("/queue clear", "s1", env)
    assert rc == 2
    assert msgs(tmp_path, "s1") == []


# -- idle vs busy ---------------------------------------------------------- #
def test_idle_queue_allowed_not_enqueued(tmp_path):
    env = make_env(tmp_path, {"s1": "idle"})
    rc, out, err = enqueue("/queue do X", "s1", env)
    assert rc == 0  # allowed
    assert msgs(tmp_path, "s1") == []  # not enqueued
    assert (tmp_path / "queue" / "s1" / ".busy").exists()  # marker set


def test_busy_queue_blocked_and_enqueued(tmp_path):
    env = make_env(tmp_path, {"s1": "busy"})
    enqueue("working", "s1", env)  # non-/queue → set marker
    rc, out, err = enqueue("/queue do X", "s1", env)
    assert rc == 2  # blocked
    assert msgs(tmp_path, "s1") == ["do X"]


# -- FIFO ------------------------------------------------------------------ #
def test_fifo_drain_then_idle(tmp_path):
    env = make_env(tmp_path, {"s1": "busy"})
    enqueue("working", "s1", env)
    enqueue("/queue first", "s1", env)
    enqueue("/queue second", "s1", env)

    rc, out, err = deliver("s1", env)
    assert json.loads(out) == {"decision": "block", "reason": "first"}
    rc, out, err = deliver("s1", env)
    assert json.loads(out)["reason"] == "second"

    # drained → allow stop, marker cleared
    rc, out, err = deliver("s1", env)
    assert out == ""
    assert not (tmp_path / "queue" / "s1" / ".busy").exists()


# -- session isolation ----------------------------------------------------- #
def test_no_cross_session_theft(tmp_path):
    env = make_env(tmp_path, {"s1": "busy", "s2": "busy"})
    enqueue("working", "s1", env)
    enqueue("/queue A-task", "s1", env)
    enqueue("working", "s2", env)
    enqueue("/queue B-task", "s2", env)

    # s2 must not pop s1's item
    _, out, _ = deliver("s2", env)
    assert json.loads(out)["reason"] == "B-task"
    _, out, _ = deliver("s1", env)
    assert json.loads(out)["reason"] == "A-task"


# -- the AND of status + marker ------------------------------------------- #
def test_interrupt_idle_status_overrides_stuck_marker(tmp_path):
    """Esc leaves the marker set, but status flips to idle → /queue allowed."""
    env = make_env(tmp_path, {"s1": "idle"})
    (tmp_path / "queue" / "s1").mkdir(parents=True, exist_ok=True)
    (tmp_path / "queue" / "s1" / ".busy").touch()  # stuck marker
    rc, out, err = enqueue("/queue after-interrupt", "s1", env)
    assert rc == 0  # not busy, no dead message


def test_stale_busy_status_without_marker(tmp_path):
    """Status briefly reads busy after a Stop, but marker is cleared → allowed."""
    env = make_env(tmp_path, {"s1": "busy"})
    # no marker (a normal Stop cleared it)
    rc, out, err = enqueue("/queue X", "s1", env)
    assert rc == 0


# -- normal prompts preempt the queue -------------------------------------- #
def test_normal_prompt_while_busy_increments_native_pending(tmp_path):
    """A non-/queue prompt submitted while busy goes to Claude Code's native
    queue. We must remember it exists so the Stop hook can yield to it."""
    env = make_env(tmp_path, {"s1": "busy"})
    enqueue("working", "s1", env)            # sets marker
    enqueue("a real prompt", "s1", env)      # non-/queue, busy -> native pending
    assert (tmp_path / "queue" / "s1" / ".native").read_text() == "1"


def test_stop_yields_to_native_prompt_before_draining(tmp_path):
    """If a native (non-/queue) prompt is pending, the Stop hook must NOT pop
    our queue — let Claude Code deliver the real prompt first."""
    env = make_env(tmp_path, {"s1": "busy"})
    enqueue("working", "s1", env)
    enqueue("/queue deferred", "s1", env)    # our queue: [deferred]
    enqueue("real prompt", "s1", env)        # native pending: 1

    rc, out, err = deliver("s1", env)
    assert rc == 0 and out == ""              # yield (allow stop), no pop
    # our item is still queued, native counter decremented
    assert msgs(tmp_path, "s1") == ["deferred"]
    assert (tmp_path / "queue" / "s1" / ".native").read_text() == "0"

    # now the native prompt would run; after it, Stop drains our queue
    rc, out, err = deliver("s1", env)
    assert json.loads(out)["reason"] == "deferred"

