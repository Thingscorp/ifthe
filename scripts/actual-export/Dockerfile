# Read-only Actual Budget exporter.
# node:22-slim (glibc) so better-sqlite3's prebuilt binary resolves; build tools
# are included as a fallback in case it has to compile for this Node ABI.
FROM node:22-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
      python3 build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY package.json ./
RUN npm install --omit=dev
COPY export.js ./

# The compose `command` wraps this in a sleep-loop schedule.
CMD ["node", "export.js"]
