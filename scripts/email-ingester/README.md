# Email Ingester

Two-part pipeline that pulls bills and receipts out of Gmail and feeds them
into both Paperless-ngx and the AI analysis layer.

```
Gmail (IMAP, read-only)
  └─ getmail6  →  Maildir
       └─ parse_emails.py
            ├─ $DATA_ROOT/ai/parsed_emails.json    ← Claude reads this
            └─ $DATA_ROOT/paperless/consume/        ← Paperless OCRs PDFs here
```

## Two ways to run it

- **Containerized (recommended):** `docker compose -f "apps/deploy/docker-compose.ai.yml" up -d --build`.
  Point `EMAIL_CONFIG_DIR` (in the deploy `.env`) at a host dir holding your
  `getmailrc`. Start from [`getmail.conf.docker.example`](getmail.conf.docker.example),
  which is already wired for the container: copy it to `$EMAIL_CONFIG_DIR/getmailrc`
  and fill in your Gmail address + App Password. **The container's getmailrc
  `[destination] path` must be `/getmail/inbox/`** — that's where both getmail
  delivers and the parser reads inside the container. Everything else is wired
  automatically.
- **Directly (cron):** the steps below.

---

## Part 1 — getmail6 (fetch from Gmail)

### Install

```bash
pip install getmail6
# or: brew install getmail
```

### Configure

```bash
mkdir -p ~/.getmail ~/Mail/inbox/{new,cur,tmp}
cp getmail.conf.example ~/.getmail/getmailrc
# Edit ~/.getmail/getmailrc:
#   - Set your Gmail address
#   - Set your App Password (Google Account → Security → 2-Step → App passwords)
```

### Run

```bash
getmail --getmaildir ~/.getmail
```

### Cron (every 30 minutes on your home server)

```
*/30 * * * * getmail --getmaildir ~/.getmail --quiet >> /tmp/getmail.log 2>&1
```

---

## Part 2 — parse_emails.py (extract + route)

### Install

```bash
pip install mail-parser ocrmypdf
# Tesseract (OCR engine):
brew install tesseract          # macOS
# apt install tesseract-ocr     # Debian/Ubuntu
```

### Environment variables (defaults shown)

```bash
export DATA_ROOT="/Users/Shared/ifthe"     # macOS; /srv/ifthe on Linux
export MAILDIR="$DATA_ROOT/getmail/inbox"      # where getmail6 delivers
export DRY_RUN=""                              # set to "1" to parse without writing
# These default to DATA_ROOT-derived paths — override only if you must:
#   PARSED_OUT   -> $DATA_ROOT/ai/parsed_emails.json
#   CONSUME_DIR  -> $DATA_ROOT/paperless/consume   (the dir Paperless watches)
#   STATE_FILE   -> $DATA_ROOT/ai/.seen_messages
```

### Run

```bash
python3 parse_emails.py
```

### Cron (runs shortly after getmail fetch)

```
# cron has no profile env — set DATA_ROOT inline so the defaults resolve
5,35 * * * * cd /Users/Shared/scripts/email-ingester && DATA_ROOT=/Users/Shared/ifthe MAILDIR=/Users/Shared/ifthe/getmail/inbox python3 parse_emails.py >> /tmp/email-ingester.log 2>&1
```

---

## Output format (parsed_emails.json)

```json
[
  {
    "message_id":      "sha1 of raw message",
    "date":            "2025-01-15T10:30:00+00:00",
    "vendor":          "Verizon Wireless",
    "subject":         "Your bill is ready",
    "amount":          142.87,
    "due_date":        "February 1, 2025",
    "doc_refs":        ["/Users/Shared/ifthe/paperless/consume/20250115-Verizon-bill.pdf"],
    "match_status":    "unmatched",
    "matched_txn_ids": []
  }
]
```

`match_status` and `matched_txn_ids` are updated by Claude's reconciliation
analysis — the script never writes those fields, Claude does (in the JSON file
only, never in Actual).

---

## What this does NOT do

- Never modifies or deletes Gmail messages (getmail6 runs with `delete=false`)
- Never writes to Actual Budget
- Never initiates payments
- PDF attachments are **copied** into Paperless consume — originals stay in Maildir
