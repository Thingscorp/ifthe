---
name: ifthe
description: A home server with a morning briefing.
colors:
  primary: "#5c6650"
  primary-deep: "#48523e"
  ink: "#1c1a17"
  ink-frontdoor: "#1c1c1a"
  paper: "#f7f4ec"
  neutral-bg: "#ffffff"
  frontdoor-bg: "#f6f5f1"
  body: "#333333"
  secondary: "#555555"
  muted: "#666666"
  faint: "#737373"
  hairline: "#eeeeee"
  briefing-label: "#44403a"
  briefing-muted: "#8a8578"
  briefing-rule: "#c9c3b4"
  pure-black: "#000000"
  ok: "#44543c"
  warn: "#8a5a13"
  dark-bg: "#16161a"
  dark-surface: "#202028"
  dark-text: "#ececf0"
  dark-muted: "#9a9aa3"
  dark-accent: "#7d8b6f"
typography:
  display:
    fontFamily: "Inter, sans-serif"
    fontSize: "46px"
    fontWeight: 800
    lineHeight: 1
    letterSpacing: "-2px"
  headline:
    fontFamily: "-apple-system, BlinkMacSystemFont, Segoe UI, Roboto, Helvetica, Arial, sans-serif"
    fontSize: "clamp(22px, 4vw, 30px)"
    fontWeight: 600
    letterSpacing: "-0.01em"
  title:
    fontFamily: "Inter, sans-serif"
    fontSize: "0.95rem"
    fontWeight: 600
  body:
    fontFamily: "Inter, sans-serif"
    fontSize: "1rem"
    fontWeight: 400
    lineHeight: 1.7
  label:
    fontFamily: "Avenir Next, Segoe UI, system-ui, sans-serif"
    fontSize: "13px"
    letterSpacing: "2px"
rounded:
  icon: "11px"
  card: "14px"
  tile: "18px"
spacing:
  gutter: "60px"
  section: "40px"
  panel-x: "34px"
  panel-y: "28px"
components:
  app-card:
    backgroundColor: "{colors.neutral-bg}"
    textColor: "{colors.ink-frontdoor}"
    rounded: "{rounded.card}"
    padding: "14px"
  link:
    textColor: "{colors.primary}"
  section-label:
    typography: "{typography.label}"
    textColor: "{colors.primary}"
---

# Design System: ifthe

## Overview

**Creative North Star: "The Spec Sheet"**

Every surface in ifthe reads like a good spec sheet: named parts, exact values, honest status, nothing decorative that is not information. The system is ink on paper with one sage accent, set in plain type, divided by hairlines instead of boxes. It covers five surfaces that share one discipline: a landing page, a LAN front door with an ambient idle screen, and a morning briefing rendered at three fixed sizes for e-ink and print-like displays.

Density is low and type does the talking. The biggest thing on any screen is the clock or the wordmark; everything else is a labeled list. Color is rationed: the accent marks links, section labels, and focus, and nothing else. Surfaces that print or sit on e-ink drop to pure black on white.

**Key Characteristics:**

- Ink on paper: warm neutrals, one sage accent, no second accent anywhere.
- Hairlines divide; boxes and shadows do not appear.
- Fixed formats: briefing pages are exact pixel sizes and never scroll.
- Tabular figures wherever a number can change: clocks, agenda times, money.
- Honest status in the design itself: coming-soon work is shown faded, not hidden.

## Colors

A warm paper palette with a single muted green accent, extracted from the landing page, the briefing renderer, and the front door. The same sage runs through all three; each surface keeps its own neutrals.

### Primary

- **Sage** (#5c6650): the only accent. Links and their underlines, briefing section labels, the dot on the wordmark's i, front door focus outlines, hover borders, icon backgrounds, and agenda times.
- **Deep Sage** (#48523e): the accent's hover state on the landing page, links and card titles.

### Tertiary

- **Status Green** (#44543c): the briefing's ok state, used for short status lines such as a backup that ran.
- **Status Amber** (#8a5a13): the briefing's warn state, used when a service is down or a backup needs a look. Status colors appear only as text, never as fills.

### Neutral

- **Ink** (#1c1a17): wordmark, briefing text, and header rules on the panel profile.
- **Front Door Ink** (#1c1c1a): text in the front door, a separate token because the front door predates the palette unification.
- **Paper** (#f7f4ec): the panel briefing's background, the warmest surface in the system.
- **White** (#ffffff): landing background, front door cards, and the card and Kindle briefing backgrounds.
- **Front Door Ground** (#f6f5f1): the front door's page background behind its white cards.
- **Body Gray** (#333333): landing body text and card titles.
- **Secondary Gray** (#555555): landing intro and resource descriptions; the Kindle profile's muted text.
- **Muted Gray** (#666666): landing product card descriptions.
- **Faint Gray** (#737373): the landing footer copyright, the lightest text allowed on white (about 4.7:1, WCAG AA).
- **Hairline** (#eeeeee): the landing's divider rules, inset 60px from the column edges.
- **Briefing Label** (#44403a): agenda times and money labels on the panel profile.
- **Briefing Muted** (#8a8578): panel footer text and empty states.
- **Briefing Rule** (#c9c3b4): the panel footer's top border.
- **Pure Black** (#000000): all text and rules on the card and Kindle profiles.
- **Night Ground** (#16161a), **Night Surface** (#202028), **Night Text** (#ececf0), **Night Muted** (#9a9aa3), **Night Sage** (#7d8b6f): the front door ambient screen's dark variant, the only dark surface in the system. Night Sage is a lighter sage so small text keeps AA contrast on the dark ground.

### Named Rules

**The One Accent Rule.** Sage is the only brand accent on every surface. The front door's per-app icon colors are app identity, set per app in its config; they are not brand accents and never spread into chrome, text, or new components.

**The Print Rule.** Profiles that print or sit on e-ink (card, Kindle) use pure black on white. Their only grays are the muted text steps already in the renderer. No sage, no paper tint, no color of any kind.

## Typography

**Display Font:** Inter (with system sans fallback), landing only.
**Body Font:** Inter on the landing; Avenir Next, Segoe UI, system-ui on the briefing; the system stack on the front door.
**Serif:** Georgia, body text on the Kindle profile only.

**Character:** One sans voice at three addresses. The landing loads Inter because it can; the front door uses the system stack because its content security policy is same-origin only, a recorded exception, not drift. The Kindle profile sets its body in Georgia because that is what renders well on its panel; its clock and section labels stay in the sans stack. An open design call, recorded in the chain ledger, is whether the Kindle body joins the sans voice.

### Hierarchy

- **Display** (Inter, 800, 46px, line-height 1, letter-spacing -2px): the landing wordmark only. Its i carries no dot; a sage circle sits in its place.
- **Clock, panel** (sans stack, 600, 64px, letter-spacing -1px): the panel briefing's time. The Kindle clock is the same voice at 150px and weight 700; the card clock at 50px.
- **Headline** (system stack, 600, clamp(22px, 4vw, 30px), letter-spacing -0.01em): the front door's bar title. The ambient clock is the same stack at clamp(48px, 11vw, 92px).
- **Title** (Inter, 600, 0.95rem): landing product names and resource titles.
- **Body** (Inter, 400, 1rem, line-height 1.7): landing intro paragraphs, capped at 700px measure. Briefing lists run 19px at line-height 1.45 on the panel, 16px on the card, 38px on the Kindle.
- **Label** (sans stack, 13px, uppercase, letter-spacing 2px, sage): briefing section labels. The Kindle label is 24px with 4px tracking; the card label is 11px in dark gray.

### Named Rules

**The Tabular Figures Rule.** Every surface that shows a changing number sets font-variant-numeric: tabular-nums: all three briefing profiles, the front door clock, and its agenda times. Digits never shift a column.

## Layout

Three spatial models, one per surface family.

**Landing:** a centered column, max-width 1100px, on white. Sections stack in a fixed order (header, product lineup, intro, resources, footer) separated by 1px hairlines inset 60px. Section padding is 40px by 60px. The lineup is a flex row that becomes a 3-column grid at 900px and a 2-column grid at 600px, where side padding drops to 20px and the hairline inset follows.

**Briefing:** fixed-format pages, exact sizes, no scroll, no responsive behavior: panel 800x480, card 648x480, Kindle 1072x1448 portrait. Landscape profiles use a two-column grid (1.35fr / 1fr, 36px column gap on the panel, 28px on the card) under a header rule; the Kindle is one column. Content that exceeds the frame clips inside the main region; the footer, which carries the updated time, always renders inside the frame.

**Front door:** a centered launcher, max-width 1100px, padding clamp(16px, 4vw, 40px). The app grid is repeat(auto-fill, minmax(190px, 1fr)) with a 12px gap. The ambient screen is a two-tile bento (clock, agenda) at max-width 920px, collapsing to one column at 680px.

## Elevation & Depth

The system is flat. There are no box-shadows in any surface's code, and none may be added. Depth comes from hairline borders, tonal layering (white cards on the front door ground, paper behind ink), and one inset outline: landing product images carry a 1px rgba(0,0,0,0.1) outline at -1px offset so pale product shots read against white.

State, not shadow, signals lift: front door cards rise 1px and take the accent border on hover; landing product cards scale to 1.03. Both movements switch off under prefers-reduced-motion.

**The Flat-By-Default Rule.** Surfaces are flat at rest and stay flat. A hover translation or scale is the strongest depth cue this system uses.

## Shapes

Two form languages by surface family. The front door rounds its corners: app icons at 11px, cards at 14px, ambient tiles at 18px. Everything else is square: the landing and all briefing profiles use radius 0, with one exception, the circular sage dot on the wordmark's i.

Borders carry the structure: 1px hairlines (#eeeeee) on the landing, a 1px border at rgba(0,0,0,0.10) on front door cards, and rules in ink on the briefing (2px under the panel header, 4px on the Kindle, 1px above footers).

## Components

### Wordmark

The product's signature. Lowercase "ifthe" in Inter at weight 800, ink, with the i rendered dotless and a sage circle (.17em) centered above the stem. It appears on the landing header at 46px (36px under 600px) and nowhere else at display size.

### Product Card (landing)

A plain centered block: product image 120px tall (80px on small screens), name in Title style with the soft accent underline, one-line description in Muted Gray. Hover scales the card to 1.03 over .2s. A coming-soon card sits at 60% opacity, takes no hover scale, and its name carries no underline: the fade is the status.

### App Card (front door)

A white card (14px radius, 1px border, 14px padding) with a 42px icon tile (11px radius, accent or per-app color background, white initial) and two text lines: app name at weight 500, description at 12px in muted. Hover lifts it 1px and turns the border sage. Focus shows a 2px sage outline at 2px offset.

### Ambient Tile (front door)

A surface tile (18px radius, 1px border, padding clamp(18px, 3vw, 30px)). The clock tile centers the time at up to 92px with date and greeting beneath; the agenda tile lists today's events with tabular times in the accent. In the dark variant the tiles take Night Surface on Night Ground.

### Briefing Section

The briefing's only component, repeated: a Label in uppercase sage (or black on print profiles), then a list whose rows open with a fixed-width label column (102px for agenda times, 132px for money on the panel; 190px and 300px on the Kindle) so values align down the page. Status lines use the status colors as text. An empty section states its empty state in muted text; it never disappears and never errors.

### Links

Sage text with a 1px underline in sage at 25% alpha, offset 2px. Hover deepens both to Deep Sage (50% alpha underline). Focus draws a 2px sage outline at 3px offset. Footer links trade the underline for larger hit areas built from padding and negative margins.

### Buttons and Inputs

The web surfaces have none, by design: the front door is a launcher of links, the briefing is read-only, and the landing's only action is following a link. Do not invent button styles for these surfaces. Hardware buttons on a future panel are unbuilt and undesigned.

## Do's and Don'ts

### Do:

- **Do** use Sage (#5c6650) as the only accent, and Deep Sage (#48523e) only for its hover state.
- **Do** divide sections with 1px hairlines inset from the column, never with boxes or shadows.
- **Do** set tabular figures on any number that can change.
- **Do** show unbuilt work faded with its status stated, the coming-soon treatment.
- **Do** keep briefing pages at their exact profile sizes, with the footer inside the frame at maximum data.

### Don't:

- **Don't** add a box-shadow to anything. The system has none.
- **Don't** introduce a second accent color, including in new per-app icon colors chosen to match the chrome.
- **Don't** put color on the card or Kindle profiles beyond their muted grays.
- **Don't** round corners on the landing or the briefing; rounding belongs to the front door alone.
- **Don't** load a web font in the front door; its same-origin CSP forbids it, and the system stack is the recorded design.
- **Don't** let a briefing page scroll or push its footer out of frame; clip inside the main region instead.
