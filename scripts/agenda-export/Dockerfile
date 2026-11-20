# Read-only agenda exporter: Nextcloud CalDAV -> agenda.json for the sleep screen.
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY agenda_export.py ./
# The compose `command` wraps this in a sleep-loop schedule.
CMD ["python3", "agenda_export.py"]
