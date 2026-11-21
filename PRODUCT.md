# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: a household that runs its own home server, or wants to. One or more adults in the home use it every day; the person who installs it is comfortable cloning a repo, filling in an .env file, and running a deploy script. The job: know what today needs, and where the household's own services and records live, without a vendor cloud holding the family's data.

The reference home is the owner's household, whose private deployment (franklinOS) is where ifthe was extracted from. It is the proof the product works, not the primary user. Confirmed by the owner on 2026-11-21, with a five-judge panel unanimous for this framing.

## Product Purpose

ifthe is a home server with a morning briefing. One small always-on computer in the home runs the household's services. One screen shows the day: today's agenda, service health, whether last night's backup ran, a budget snapshot, and the household's own tracked lists. An AI layer reads exported files and answers questions about the house. Success is a household running its own copy day to day, glancing at one screen in the morning instead of opening feeds and apps.

## Positioning

The AI layer is read-only by construction, and a mechanical guard in the check suite fails the build if an exporter ever gains a money-moving or write call. Neighboring home-server and AI products ask for trust; ifthe removes the capability. The household's data stays on the home network, the repo ships fictional example data only, and the whole product is a template meant to be copied, not a service anyone signs up for.

## Operating Context

- The box sits on the home LAN, always on. Remote access, when wanted, is through the household's own Tailscale tailnet, never a vendor cloud.
- The front door (apps/dashboard/frontdoor/) stays open on a screen the household walks past: a launcher grid for the services, settling after idle minutes into an ambient screen with clock, date, greeting, and today's agenda.
- The same briefing renders to e-ink: a 800x480 panel profile, a 648x480 card profile, and a portrait Kindle profile drawn by a fetch-and-draw loop on a jailbroken Kindle.
- As a Muse Gadget, the Linux box pairs with the owner's Muse and answers five read-only questions (services, backup, agenda, budget, briefing) through drop-in commands.
- Install ritual: clone, copy .env.example to .env, run apps/deploy/deploy.sh in phases, then bash scripts/check.sh and bash tests/run-tests.sh before trusting it.

## Capabilities and Constraints

Capabilities, all in the repo today:

- Four Docker Compose stacks (foundation, docs, family, dashboard) plus Actual Budget as the ledger, deployed by one script; Linux native, macOS via Colima.
- Three read-only exporters (budget snapshot, email bills and receipts into the document archive, daily agenda) writing plain files an assistant can read.
- A household memory layer (ai/memory/) with fictional examples in the shapes a household fills in; real memory files are gitignored.
- The briefing renderer (briefing/), the gadget commands (gadget/), the Kindle package (kindle/), and a landing page (site/).

Constraints:

- Nothing in the product can move money, write to a service, or delete anything. The guard is mechanical, not a promise.
- Every service is LAN-only by default. There is no hosted tier, no account system, and no telemetry.
- The one paid extra in the reference home is bank sync (SimpleFIN Bridge, about $15 per year). Everything else is free and open source.
- Bank and budget answers are summaries with labeled lines, never transactions or payees.

Undecided, recorded as open: the license (not yet picked), the panel hardware (not yet bought), and the gadget pairing (Slice 1 not yet run on a Linux box).

## Brand Commitments

- Name: ifthe. Domain: ifthe.com. The private first deployment keeps its own name, franklinOS.
- Voice: plain functional words, active voice, short sentences. Name what the product does; never describe a mood. The words "quiet" and "calm" are banned from product copy by owner ruling (2026-11-20), and em-dashes are banned in all copy.
- Status is stated honestly everywhere it appears: in the works, built, public. Nothing is described as existing before it does.
- The landing page's design is modeled on repebble.com, credited on the page. Widget modularity takes direct inspiration from pebble-dev: people add their own widgets as data, the system renders.

## Evidence on Hand

- README.md: the product story, quick start, privacy model, and status, all verifiable against the repo.
- The check suite and behavioural tests (scripts/check.sh, tests/run-tests.sh), green on the template.
- site/brand.yml: the brand record, including per-surface tokens and recorded exceptions. .impeccable.md: the design context.
- The extraction itself: a working private deployment sanitized file by file, so every capability above has run in a real home.
- Absences future work must not fabricate: no testimonials, no outside users yet, no hardware photos, no benchmarks, no pricing. The showcase photo does not exist until hardware is built.

## Product Principles

1. Read-only by construction. Safety comes from missing capability, not from policy.
2. Data stays home. The LAN is the boundary; exports are plain files the household owns.
3. One screen, glance first. The morning briefing is the product's center; everything else supports it.
4. The template is the product. Every decision is judged by whether a stranger's household can copy it and run it.
5. Plain words, honest status. Copy names what a thing does and what state it is in, nothing more.
