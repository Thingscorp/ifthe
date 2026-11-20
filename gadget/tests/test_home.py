#!/usr/bin/env python3
"""Behavior tests for gadget/bin/ifthe-home against fixtures.

Run: python3 gadget/tests/test_home.py
Exit 0 means every command printed the JSON the fixtures imply.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
PROG = os.path.join(HERE, "..", "bin", "ifthe-home")
FIXTURES = os.path.join(HERE, "fixtures")


def run(sub, params=None, env_extra=None):
    env = dict(os.environ)
    env["IFTHE_EXPORT_DIR"] = FIXTURES
    env["IFTHE_LEDGER"] = os.path.join(FIXTURES, "ledger.json")
    if env_extra:
        env.update(env_extra)
    p = subprocess.run(
        [sys.executable, PROG, sub],
        input=json.dumps(params or {}),
        capture_output=True, text=True, env=env, timeout=15,
    )
    assert p.returncode == 0, (sub, p.returncode, p.stdout, p.stderr)
    return json.loads(p.stdout)


def main():
    s = run("services")
    assert s["ok"] and s["services_up"] == 10 and s["down"] == [], s

    b = run("backup")
    assert b["ok"] and b["last_ok"] is True and b["last_run"] == "02:15", b

    a = run("agenda")
    assert a["ok"] and len(a["events"]) == 4, a
    assert a["events"][1]["title"] == "School run", a

    bud = run("budget", {"month": "2026-11"})
    assert bud["ok"] and bud["month"] == "2026-11", bud
    assert bud["accounts"] == [{"name": "Checking", "balance": 4210.5}], bud
    assert bud["spend_by_category"] == [
        {"category": "Groceries", "spent": 310.0}], bud
    assert bud["income_total"] == 3000.0, bud
    # October's spend must not leak into November's summary.
    october = run("budget", {"month": "2026-10"})
    assert october["spend_by_category"] == [
        {"category": "Groceries", "spent": 999.0}], october
    # The summary is bounded: no transaction or payee data anywhere.
    blob = json.dumps(bud)
    for forbidden in ("t1", "transactions", "payee"):
        assert forbidden not in blob, (forbidden, blob)

    brief = run("briefing")
    assert brief["ok"] and brief["services"]["ok"] and brief["agenda"]["ok"], brief

    # Missing exports are a calm error, never a crash.
    empty = run("services", env_extra={"IFTHE_EXPORT_DIR": "/nonexistent"})
    assert empty["ok"] is False and empty["stale"] is True, empty

    print("gadget home.* tests: ALL PASS")


if __name__ == "__main__":
    main()
