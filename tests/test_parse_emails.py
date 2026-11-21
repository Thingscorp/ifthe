#!/usr/bin/env python3
"""Hermetic tests for scripts/email-ingester/parse_emails.py.

No external deps: `mailparser` is stubbed and `ocrmypdf` is expected absent (so the
copy-fallback path is exercised). Runs with plain `python3 tests/test_parse_emails.py`.
"""
import os, sys, json, base64, types, tempfile, importlib.util
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
MOD = REPO / "scripts" / "email-ingester" / "parse_emails.py"

# ---- stub mailparser BEFORE importing the module under test ----
mailparser_stub = types.ModuleType("mailparser")
mailparser_stub.parse_from_file = lambda p: (_ for _ in ()).throw(RuntimeError("set per test"))
sys.modules["mailparser"] = mailparser_stub

# point all runtime paths at a temp tree, set BEFORE import (module reads env at load)
TMP = Path(tempfile.mkdtemp(prefix="pe-test-"))
os.environ["DATA_ROOT"] = str(TMP)
os.environ["MAILDIR"] = str(TMP / "mail" / "inbox")
(TMP / "mail" / "inbox" / "new").mkdir(parents=True, exist_ok=True)
(TMP / "mail" / "inbox" / "cur").mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("parse_emails", MOD)
pe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pe)

results = []
def check(name, cond, detail=""):
    results.append((name, bool(cond), detail))

class FakeMail:
    def __init__(self, subject="", text_plain=None, from_=None, date=None, attachments=None):
        self.subject = subject
        self.text_plain = text_plain or []
        self.from_ = from_ or []
        self.date = date
        self.attachments = attachments or []

# ---------- decode_attachment ----------
pdf = b"%PDF-1.7\n\xde\xad\xbe\xef binary body\n%%EOF"
b64 = base64.b64encode(pdf).decode()
check("decode:base64(binary flag)", pe.decode_attachment({"payload": b64, "binary": True}) == pdf)
check("decode:base64(cte)", pe.decode_attachment({"payload": b64, "content_transfer_encoding": "base64"}) == pdf)
check("decode:raw bytes passthrough", pe.decode_attachment({"payload": pdf}) == pdf)
import quopri
qp = quopri.encodestring(b"hello=world\n").decode()
check("decode:quoted-printable", pe.decode_attachment({"payload": qp, "content_transfer_encoding": "quoted-printable"}) == b"hello=world\n")
check("decode:plain text utf-8", pe.decode_attachment({"payload": "plain text"}) == b"plain text")

# ---------- is_bill ----------
check("is_bill:subject keyword", pe.is_bill(FakeMail(subject="Your INVOICE is ready")) is True)
check("is_bill:body keyword", pe.is_bill(FakeMail(subject="hi", text_plain=["amount due soon"])) is True)
check("is_bill:non-bill", pe.is_bill(FakeMail(subject="lunch plans", text_plain=["see you at noon"])) is False)
check("is_bill:case-insensitive", pe.is_bill(FakeMail(subject="STATEMENT AVAILABLE")) is True)

# ---------- extract_amount ----------
check("amount:simple", pe.extract_amount(FakeMail(text_plain=["Total: $142.87"])) == 142.87)
check("amount:thousands comma", pe.extract_amount(FakeMail(text_plain=["Balance $1,234.56 due"])) == 1234.56)
check("amount:none", pe.extract_amount(FakeMail(subject="no money here", text_plain=["nada"])) is None)
check("amount:first-match (documents current behaviour)", pe.extract_amount(FakeMail(text_plain=["was $9.99 now $4.50"])) == 9.99)

# ---------- extract_due_date ----------
check("due:month name -> exact value", pe.extract_due_date(FakeMail(text_plain=["Payment due by February 1, 2025"])) == "February 1, 2025")
check("due:numeric -> exact value", pe.extract_due_date(FakeMail(text_plain=["due 02/01/2025"])) == "02/01/2025")
check("due:none", pe.extract_due_date(FakeMail(text_plain=["thanks for your order"])) is None)

# ---------- msg_id stability ----------
f = TMP / "mail" / "inbox" / "new" / "m1"
f.write_bytes(b"raw message bytes")
check("msg_id:stable sha1", pe.msg_id(f) == pe.msg_id(f) and len(pe.msg_id(f)) == 40)

# ---------- end-to-end main(): bill w/ base64 PDF -> record + consumed PDF, dedup, DRY_RUN ----------
def make_msg(name):
    (TMP / "mail" / "inbox" / "new" / name).write_bytes(b"placeholder-" + name.encode())

def fake_parse(path):
    return FakeMail(
        subject="Your bill is ready: amount due",
        text_plain=["Verizon Wireless. Total: $142.87. Payment due by February 1, 2025."],
        from_=[("Verizon Wireless", "no-reply@verizon.com")],
        date=None,
        attachments=[{"mail_content_type": "application/pdf", "filename": "bill.pdf",
                      "payload": b64, "binary": True}],
    )
mailparser_stub.parse_from_file = fake_parse

# clean slate
for p in (TMP / "mail" / "inbox" / "new").glob("*"):
    p.unlink()
make_msg("bill1")
pe.main()

parsed = Path(pe.PARSED_OUT)
recs = json.loads(parsed.read_text()) if parsed.exists() else []
check("e2e:record written", len(recs) == 1 and recs[0]["vendor"] == "Verizon Wireless")
check("e2e:amount parsed", recs and recs[0]["amount"] == 142.87)
check("e2e:due date parsed exactly", recs and recs[0]["due_date"] == "February 1, 2025")
consume = Path(pe.CONSUME_DIR)
pdfs = list(consume.glob("*.pdf")) if consume.exists() else []
check("e2e:PDF delivered to consume (ocrmypdf absent -> must still copy)", len(pdfs) == 1, f"found {len(pdfs)} pdfs in {consume}")
if pdfs:
    check("e2e:delivered PDF is the DECODED bytes (not base64 text)", pdfs[0].read_bytes() == pdf)

# dedup: second run with same message adds nothing new
pe.main()
recs2 = json.loads(parsed.read_text())
check("e2e:dedup on rerun (no duplicate record)", len(recs2) == 1, f"got {len(recs2)}")

# DRY_RUN: a new bill must NOT be written when DRY_RUN is on
pe.DRY_RUN = True
make_msg("bill2")
before = parsed.read_text()
pe.main()
check("e2e:DRY_RUN writes nothing", parsed.read_text() == before)

# ---------- report ----------
passed = sum(1 for _, ok, _ in results if ok)
failed = [(n, d) for n, ok, d in results if not ok]
print(f"\nparse_emails: {passed}/{len(results)} checks passed")
for n, ok, d in results:
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"   [{d}]" if (not ok and d) else ""))
import shutil; shutil.rmtree(TMP, ignore_errors=True)
sys.exit(1 if failed else 0)
