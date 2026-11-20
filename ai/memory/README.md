# The memory layer

These files are the household's own context for the AI analyst: who lives
here, what is owed, what the goals are, which rules the budget follows.

**Your real files never leave your home and are never committed.** This
directory ships with fictional examples only. To set yours up:

1. Copy each `*.example.json` / `*.example.md` file to the same name without
   `.example` (for example `debts.example.json` becomes `debts.json`).
2. Replace the fictional data with your own.
3. The real filenames are covered by `.gitignore`, so a stray commit cannot
   publish them.

`ai/load_context.sh` concatenates the system prompt, these memory files, and
the latest read-only exports into one context you can hand to a local or
cloud assistant session. What you share is always your choice, made file by
file, on your machine.
