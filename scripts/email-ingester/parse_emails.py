#!/usr/bin/env python3
"""
Email ingester for ifthe.

Walks a Maildir, extracts bills / receipts / renewals, and:
  1. Writes a summary to PARSED_OUT  (/srv/parsed/parsed_emails.json)
  2. Copies (not moves) PDF attachments into CONSUME_DIR
     (/srv/ifthe/paperless/consume/) so Paperless-ngx OCRs them

Read-only toward Gmail — getmail6 delivers messages to Maildir with delete=false.
Never writes back to the mail server.

Requirements:  pip install mail-parser ocrmypdf
               Tesseract must be installed on the host.
"""

import os
import sys
import json
import base64
import quopri
import hashlib
import mailparser
import subprocess
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone

# ---- configuration ----------------------------------------------------------

# All runtime paths derive from DATA_ROOT so the ingester always writes to the
# same tree Paperless watches and the AI reads. Override any path individually.
DATA_ROOT    = os.environ.get("DATA_ROOT", "/Users/Shared/ifthe")
MAILDIR      = Path(os.environ.get("MAILDIR",      os.path.expanduser("~/Mail/inbox")))
PARSED_OUT   = Path(os.environ.get("PARSED_OUT",   os.path.join(DATA_ROOT, "ai/parsed_emails.json")))
CONSUME_DIR  = Path(os.environ.get("CONSUME_DIR",  os.path.join(DATA_ROOT, "paperless/consume")))
STATE_FILE   = Path(os.environ.get("STATE_FILE",   os.path.join(DATA_ROOT, "ai/.seen_messages")))
DRY_RUN      = os.environ.get("DRY_RUN", "").lower() in ("1", "true", "yes")

# Keywords that flag an email as a bill/receipt/renewal.
BILL_KEYWORDS = [
    "invoice", "receipt", "payment due", "statement", "billing",
    "subscription", "renewal", "amount due", "pay now", "past due",
    "your order", "order confirmation", "auto-pay", "autopay",
]

# ---- helpers ----------------------------------------------------------------

def load_seen() -> set:
    if STATE_FILE.exists():
        return set(STATE_FILE.read_text().splitlines())
    return set()

def save_seen(seen: set):
    if not DRY_RUN:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text("\n".join(sorted(seen)))

def msg_id(path: Path) -> str:
    """Stable ID: SHA-1 of the file content (handles missing Message-ID headers)."""
    return hashlib.sha1(path.read_bytes()).hexdigest()

def is_bill(mail) -> bool:
    subject = (mail.subject or "").lower()
    body    = " ".join((mail.text_plain or [])).lower()
    combined = subject + " " + body
    return any(kw in combined for kw in BILL_KEYWORDS)

def extract_amount(mail) -> float | None:
    """Very basic dollar-amount extraction from subject + body."""
    import re
    text = (mail.subject or "") + " ".join((mail.text_plain or []))
    # Match $X,XXX.XX or $X.XX — take the first match as the "primary" amount
    amounts = re.findall(r"\$\s?([\d,]+\.\d{2})", text)
    if amounts:
        return float(amounts[0].replace(",", ""))
    return None

def extract_due_date(mail) -> str | None:
    """Pull the first date-like string that appears near "due" or "by"."""
    import re
    text = " ".join((mail.text_plain or []))
    # Look for "due on/by/: Month DD, YYYY" or "MM/DD/YYYY" near "due"
    # Lazy gap (so the month name isn't eaten) + an alphabetic month token.
    pattern = r"(?:due|by|pay\s+by)[^\d]{0,20}?(\d{1,2}[/\-]\d{1,2}[/\-]\d{2,4}|[A-Za-z]+ \d{1,2},? \d{4})"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return None

def decode_attachment(att) -> bytes:
    """Return the raw bytes of a mail-parser attachment.

    mail-parser stores binary parts (e.g. PDFs) as the base64-ENCODED text via
    get_payload(decode=False), so they must be base64-decoded. The old
    `.encode('latin1')` path only re-bytes the base64 ASCII and produces a
    corrupt, non-PDF file."""
    payload = att.get("payload")
    cte = (att.get("content_transfer_encoding") or "").lower()
    if isinstance(payload, bytes):
        return payload
    if att.get("binary") or cte == "base64":
        return base64.b64decode(payload)
    if cte == "quoted-printable":
        return quopri.decodestring(payload)
    # Already-decoded text part.
    return payload.encode("utf-8", errors="surrogateescape")

def ocr_and_copy_pdf(src_path: Path, dest_dir: Path, label: str):
    """Run OCRmyPDF on src_path and drop the result in dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    safe_label = "".join(c if c.isalnum() or c in "-_." else "_" for c in label)
    dest_path = dest_dir / f"{safe_label}.pdf"
    if dest_path.exists():
        return str(dest_path)
    try:
        subprocess.run(
            ["ocrmypdf", "--skip-text", "--quiet", str(src_path), str(dest_path)],
            check=True, capture_output=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        # OCR failed (already OCR'd / encrypted, etc.) OR ocrmypdf isn't installed
        # on this host — deliver the original so Paperless still ingests it.
        shutil.copy2(src_path, dest_path)
    return str(dest_path)

# ---- main -------------------------------------------------------------------

def main():
    if not MAILDIR.exists():
        sys.exit(f"MAILDIR not found: {MAILDIR}  (has getmail6 run yet?)")

    PARSED_OUT.parent.mkdir(parents=True, exist_ok=True)

    seen = load_seen()
    existing: list[dict] = []
    if PARSED_OUT.exists():
        try:
            existing = json.loads(PARSED_OUT.read_text())
        except json.JSONDecodeError:
            existing = []

    # Maildir new/ and cur/ subdirs both hold messages
    msg_files = sorted(
        list((MAILDIR / "new").glob("*")) + list((MAILDIR / "cur").glob("*"))
    )

    new_records = []
    for path in msg_files:
        if not path.is_file():
            continue
        mid = msg_id(path)
        if mid in seen:
            continue

        try:
            mail = mailparser.parse_from_file(str(path))
        except Exception as e:
            print(f"  skip (parse error): {path.name} — {e}")
            continue

        if not is_bill(mail):
            seen.add(mid)
            continue

        amount   = extract_amount(mail)
        due_date = extract_due_date(mail)

        # Derive a vendor name from the From header
        from_addr = mail.from_[0] if mail.from_ else ("", "")
        vendor = from_addr[0] or from_addr[1] or "Unknown"

        doc_refs = []
        # Drop PDF attachments into Paperless consume dir
        for att in (mail.attachments or []):
            if att.get("mail_content_type", "").lower() == "application/pdf":
                filename = att.get("filename") or f"{mid[:8]}.pdf"
                with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
                    tmp.write(decode_attachment(att))
                    tmp_path = Path(tmp.name)
                if not DRY_RUN:
                    label = f"{datetime.now(timezone.utc).strftime('%Y%m%d')}-{vendor[:30]}-{filename}"
                    doc_path = ocr_and_copy_pdf(tmp_path, CONSUME_DIR, label)
                    doc_refs.append(doc_path)
                tmp_path.unlink(missing_ok=True)

        record = {
            "message_id":       mid,
            "date":             mail.date.isoformat() if mail.date else None,
            "vendor":           vendor,
            "subject":          mail.subject,
            "amount":           amount,
            "due_date":         due_date,
            "doc_refs":         doc_refs,
            "match_status":     "unmatched",   # updated by reconciliation step
            "matched_txn_ids":  [],
        }
        new_records.append(record)
        seen.add(mid)

        amount_str = f"{amount:.2f}" if amount is not None else "?"
        print(f"  + {vendor:40s}  ${amount_str:>10}  due: {due_date or '?'}")

    if new_records or not PARSED_OUT.exists():
        all_records = existing + new_records
        if not DRY_RUN:
            PARSED_OUT.write_text(json.dumps(all_records, indent=2, default=str))
        print(f"\n{'[DRY RUN] ' if DRY_RUN else ''}Wrote {len(all_records)} records "
              f"({len(new_records)} new) → {PARSED_OUT}")
    else:
        print("No new bill/receipt emails found.")

    save_seen(seen)

if __name__ == "__main__":
    main()
