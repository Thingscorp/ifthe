#!/usr/bin/env python3
"""Behavior tests for gadget/bin/ifthe-home against fixtures.

Run: python3 gadget/tests/test_home.py
Exit 0 means every command printed the JSON the fixtures imply.
"""
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime

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
    assert s["services_total"] == 10, s

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

    # No month parameter means the current month, same as naming it.
    current = datetime.now().strftime("%Y-%m")
    default = run("budget")
    explicit = run("budget", {"month": current})
    assert default["month"] == current == explicit["month"], (default, explicit)
    assert default["accounts"] == explicit["accounts"], (default, explicit)
    assert default["spend_by_category"] == explicit["spend_by_category"], \
        (default, explicit)
    assert default["income_total"] == explicit["income_total"], (default, explicit)

    # Temporary ledgers in the fixture's shape, for the summary rules the
    # shipped fixture cannot show.
    with open(os.path.join(FIXTURES, "ledger.json"), encoding="utf-8") as f:
        base = json.load(f)

    def temp_budget(ledger, params=None):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "ledger.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump(ledger, f)
            return run("budget", params or {"month": "2026-11"},
                       env_extra={"IFTHE_LEDGER": path})

    def txn(tid, date, cat, amount):
        t = dict(base["transactions"][0])
        t.update({"id": tid, "date": date, "category_id": cat, "amount": amount})
        return t

    # Spend is cut to the top 5 categories, largest first.
    totals = [700, 100, 600, 200, 500, 300, 400]
    many = dict(base)
    many["categories"] = [
        {"id": "k%d" % i, "name": "Cat%d" % i, "group_id": "g",
         "hidden": False, "is_income": False}
        for i in range(1, 8)]
    many["transactions"] = [
        txn("m%d" % i, "2026-11-05", "k%d" % i, -totals[i - 1] * 1000)
        for i in range(1, 8)]
    top = temp_budget(many)
    assert top["spend_by_category"] == [
        {"category": "Cat1", "spent": 700.0},
        {"category": "Cat3", "spent": 600.0},
        {"category": "Cat5", "spent": 500.0},
        {"category": "Cat7", "spent": 400.0},
        {"category": "Cat6", "spent": 300.0}], top

    # A transaction whose category id is unknown lands in Uncategorized.
    unknown = dict(base)
    unknown["transactions"] = [txn("u1", "2026-11-05", "no-such-cat", -42000)]
    unc = temp_budget(unknown)
    assert unc["spend_by_category"] == [
        {"category": "Uncategorized", "spent": 42.0}], unc

    # A closed account is excluded from balances, even with money in it.
    closed = dict(base)
    closed["accounts"] = [
        {"id": "a1", "name": "Checking", "closed": False,
         "balance": 100000, "offbudget": False},
        {"id": "a9", "name": "Closed savings", "closed": True,
         "balance": 555000, "offbudget": False}]
    closed["transactions"] = []
    acc = temp_budget(closed)
    assert acc["accounts"] == [{"name": "Checking", "balance": 100.0}], acc
    assert "Closed savings" not in json.dumps(acc["accounts"]), acc

    brief = run("briefing")
    assert brief["ok"] and brief["services"]["ok"] and brief["agenda"]["ok"], brief
    assert brief["backup"]["ok"] and brief["backup"]["last_ok"] is True, brief
    # The briefing's budget section runs with no month, so it summarises the
    # current month: give it a ledger whose Groceries spend sits there.
    now_ledger = dict(base)
    now_ledger["transactions"] = [
        txn("n1", current + "-10", "c1", -123000)]
    with tempfile.TemporaryDirectory() as td:
        path = os.path.join(td, "ledger.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(now_ledger, f)
        brief_bud = run("briefing", env_extra={"IFTHE_LEDGER": path})["budget"]
    assert brief_bud["ok"] and brief_bud["month"] == current, brief_bud
    assert brief_bud["spend_by_category"] == [
        {"category": "Groceries", "spent": 123.0}], brief_bud

    # Missing exports are a plain error, never a crash.
    empty = run("services", env_extra={"IFTHE_EXPORT_DIR": "/nonexistent"})
    assert empty["ok"] is False and empty["stale"] is True, empty

    print("gadget home.* tests: ALL PASS")


if __name__ == "__main__":
    main()
