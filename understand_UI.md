# NeverQuit — Complete UI Understanding

> Hand this file to a designer (or to Claude) to fully understand the current
> NeverQuit interface before redesigning. It documents every page, component,
> design token, interaction, and responsive rule as the UI exists today.

---

## 1. What NeverQuit Is

NeverQuit is an AI-assisted storytelling platform that publishes long-form
**comeback stories** of athletes, Paralympians, and differently-abled people.
The UI has **two faces sharing one design system**:

- **Public site** — readers browse, search, and read stories; bookmark them; subscribe to a newsletter; submit athlete suggestions.
- **Admin console** — editors research athletes, review AI-generated drafts, approve/reject/publish, control which sections show publicly, and manage newsletter subscribers.

The whole UI is **server-rendered Jinja2 templates** with **inline `<style>` and `<script>`** — no build step, no framework, no external CSS file. One shared shell (`base.html`) wraps every page.

---

## 2. Design Language (current)

The current style is **warm editorial / minimal magazine**:

- Warm off-white backgrounds, near-black text, a single burnt-orange accent.
- Serif headlines (editorial feel) + sans-serif body and UI (clean, modern).
- Thin `0.5px`–`1px` hairline borders instead of heavy shadows.
- Soft rounded corners (`8px`–`18px`), gentle hover lifts, subtle fade-in animations.
- Generous white space, centered hero, calm rhythm.

It is **light-mode first** with a fully working **dark mode** toggle.

---

## 3. Design Tokens

All tokens are CSS custom properties declared in `base.html` `:root`.

### 3.1 Color — Light theme (default)

| Token | Value | Used for |
|---|---|---|
| `--color-text-primary` / `--ink` | `#1a1a1a` | Headlines, primary text |
| `--color-text-secondary` / `--ink-muted` | `#525252` | Body copy, descriptions |
| `--color-text-tertiary` / `--ink-faint` | `#8a8a8a` | Labels, captions, meta |
| `--color-background-primary` / `--bg` | `#ffffff` | Page background, cards |
| `--color-background-secondary` / `--bg-mute` | `#f7f6f3` | Section bands, boxes, inputs-on-hover |
| `--bg-deep` | `#EBE9DD` | Image placeholders |
| `--color-border-tertiary` / `--line` | `#e8e6e1` | Hairline dividers, card borders |
| `--color-border-secondary` / `--line-strong` | `#d4d4d4` | Input borders, stronger dividers |

### 3.2 Color — Accent & semantic

| Token | Value | Meaning |
|---|---|---|
| `--accent` | `#D85A30` | **Primary brand orange** — buttons, links-on-hover, highlights |
| `--accent-hover` | `#B84A20` | Darker orange for button hover |
| `--accent-soft` | `#FAECE7` | Pale peach — badge/quote/banner backgrounds |
| `--accent-deep` | `#712B13` | Dark brown — text on `--accent-soft` |
| `--green` | `#085041` | Approve actions, high score |
| `--green-soft` | `#E1F5EE` | Pale green — paralympic badge bg |
| `--red` | `#9B1C1C` | Reject/delete actions, low score |
| `--red-soft` | `#FEE2E2` | Pale red — error backgrounds |
| `--gold-soft` | `#FAEEDA` | Pale gold — flash messages, mid score area |
| `--gold-deep` | `#633806` | Text on gold |
| Indigo (literal) | `#EEEDFE` bg / `#3C3489` text | Para-athlete badge |

### 3.3 Color — Dark theme

Toggled by `html[data-theme="dark"]`. Overrides only these:

| Token | Dark value |
|---|---|
| `--color-text-primary` | `#E8E6DD` |
| `--color-text-secondary` | `#A8A69D` |
| `--color-text-tertiary` | `#7A7870` |
| `--color-background-primary` | `#0F0F0E` |
| `--color-background-secondary` | `#1A1A18` |
| `--color-border-secondary` | `#2E2D2A` |
| `--color-border-tertiary` | `#262522` |

The accent orange stays the same in dark mode. Nav gets a translucent blurred
background; inputs/modals go dark; peach surfaces shift to a dark brown `#2A1D17`.

### 3.4 Typography

| Family | Stack | Used for |
|---|---|---|
| **Sans (UI)** | `Inter` → `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial` | All UI, body, nav, buttons |
| **Serif (editorial)** | `Source Serif 4` → `Georgia, "Times New Roman"` | Hero headlines, section titles, card titles, story prose, pull quotes |
| **Mono** | `"SF Mono", Menlo, Consolas` | `<code>` inline only |

- Source Serif 4 + Inter are loaded from Google Fonts on the public home page.
- The story reader (`_story_body.html`) deliberately uses **system fonts + Georgia** (no Google Fonts) for fast first paint — body prose is Georgia serif.
- Base font size: `14px`, line-height `1.55`.
- Headline sizes: hero `64px`, featured title `38px`, section header `24px`, card title `20px`, story title `22px`.
- Letter-spacing on big serif headings is slightly negative (`-0.02em` to `-0.025em`).

### 3.5 Spacing, Radius, Shadow

| Token | Value |
|---|---|
| Radius | `--r-sm 6px`, `--r-md / --border-radius-md 8px`, `--r-lg / --border-radius-lg 12px`, `--r-xl 16px`; cards use `16px`, featured `18px`, pills `20–30px` |
| Shadow | `--shadow-sm 0 1px 2px rgba(0,0,0,.04)`, `--shadow-md 0 4px 12px rgba(0,0,0,.06)`; hover cards lift with `0 12px 32px rgba(0,0,0,.07)` |
| Section padding | Hero `88px 24px 64px`; content sections `48px 24px`; max content width `1200px` |
| Borders | Hairlines are `0.5px` (nav, dividers) or `1px` (cards) |

---

## 4. The Shared Shell — `base.html`

Every page extends this. It provides:

### 4.1 Top Navigation (`.nav`)
- Sticky, `z-index:20`, full-width, `12px 20px` padding, hairline bottom border.
- **Left:** logo — a `28px` rounded-square orange tile with a white location-pin SVG, then the site name. In admin mode, small dark "Admin" pill + orange "✍ model" pill + indigo "🔎 model" pill appear.
- **Right:** `.nav-tabs` — a pill-group container (`bg #f7f6f3`, radius `10px`, `3px` padding) holding tab links. Tabs: **Home · 🔖 Saved · 💡 Submit**, then if admin: **Admin · 📨 Subs · Sign out**, else a plain **Admin** button. Last item is a **🌙 theme toggle** button.
- Active tab: white background, dark text, hairline border, weight 500.

### 4.2 Flash messages (`.flash`)
Gold band (`#FAEEDA` bg, `#633806` text), full-width, shown after redirects.

### 4.3 Admin login modal
Hidden `.modal-bg` overlay (dark 40% scrim, centered). White `.modal` card, `340px` wide, password field + Cancel/Sign-in buttons. Opened by the public "Admin" tab.

### 4.4 Persistent newsletter pill (public only)
- Fixed bottom-right (`bottom:18px; right:18px`), orange rounded pill with envelope icon + "Get one story every Monday", glowing shadow.
- Clicking opens a centered modal with a serif headline, short copy, email input, "Maybe later" / "Subscribe" buttons.
- POSTs to `/api/subscribe`. On success, sets `localStorage.nq_subscribed=1` and the pill hides permanently.

### 4.5 Footer
Defined per-page (public home has one): centered, `12px` tertiary text, hairline top border.

### 4.6 Theme system
- `<style id="theme-dark" media="not all">` — dark overrides; the media attribute is flipped to `all` to activate.
- On load: reads `localStorage.nq_theme`, else falls back to `prefers-color-scheme`.
- `toggleTheme()` swaps `data-theme` on `<html>`, flips the style's media, persists choice, swaps the toggle glyph (🌙 ↔ ☀).

---

## 5. Components

### 5.1 Buttons (`.btn`)
Base: `32px` tall, `12px` font, weight 500, `8px` radius, inline-flex, `6px` gap for icon.

| Variant | Look |
|---|---|
| `.btn-orange` / `.btn-primary` | Orange `#D85A30` bg, white text → hover darker orange |
| `.btn-ghost` | White bg, dark text, `0.5px` grey border → hover grey bg |
| `.btn-green` | `#085041` bg, white — approve |
| `.btn-red` | `#9B1C1C` bg, white — reject/delete |

### 5.2 Badges & chips
- `.badge` — `10px`, pill (`20px` radius). Variants: `.b-athlete` (peach), `.b-para` (indigo), `.b-paralympic` (green).
- `.score` — small square-ish chip; `.score-high` green, `.score-mid` `#9A6D00`, `.score-low` red.
- `.fchip` (filter chip) — `13px` pill with border; `.active` = dark fill, white text.
- `.admin-pill` — tiny dark uppercase pill in the nav.

### 5.3 Inputs
`34px` tall, `0.5px` grey border, `8px` radius, `13px` text. Focus → orange border.
Hero search input is larger (`52px`, `14px` radius, orange focus ring).

### 5.4 Cards (public story card)
- White, `1px` border, `16px` radius, clip overflow.
- Top: `.card-img-shell` — `16:10` aspect ratio image area with a **shimmer skeleton** loading animation; image fades in on load; fallback is a peach gradient with a big serif initial.
- Body: sport label (uppercase, tracked), serif title (`20px`), 3-line clamped excerpt, footer row with country + orange "Read →".
- Hover: lifts `-3px`, soft shadow, image scales `1.04`.
- Cards fade-up into view (`opacity/translateY` via `.in` class added by IntersectionObserver).

### 5.5 Featured card (`.featured`)
Two-column grid (`1.1fr` image / `1fr` body), `18px` radius. Image side min-height `380px` (or peach fallback with `120px` initial). Body side: orange eyebrow, `38px` serif title, serif excerpt, "Read the full story →" CTA (arrow slides on hover). Collapses to single column under `820px`.

### 5.6 Modal
`.modal-bg` full-screen dark scrim + centered white `.modal` card (`340–380px`, `12px` radius, `0 12px 40px` shadow).

---

## 6. Pages

### 6.1 Public Home — `public_home.html`
Top-to-bottom:
1. **Preview banner** (conditional) — peach strip when only demo stories exist.
2. **Hero band** — centered, white→cream gradient bg, floating radial-glow accent. Contents: pulsing-dot orange eyebrow ("True comebacks · told well"), `64px` serif H1 with orange `<em>` ("They were told *it's over.*"), `18px` subtitle, search bar (`52px` input + dark "Search" button).
3. **Stats band** — auto-fit grid of 5 cells (Stories, Sports, Countries, Athletes, Para athletes). Numbers are serif `34px` and **count up** from 0 on scroll-in. Hover tints number orange.
4. **Filter bar** — sticky (`top:53px`) centered row of `.fchip` filter pills: All / Athletes / Para athletes / one per sport.
5. **Featured story** — section header "This week's story / Featured", then one big `.featured` card.
6. **Story grid** — section header "More comebacks", responsive `auto-fit minmax(310px)` grid of `.card`s, a "Show more stories" pill button, and an empty-state.
7. **Newsletter band** — full-width **dark** (`#1a1a1a`) section, radial orange glow, `42px` serif headline with orange `<em>`, email form (dark inputs).
8. **Footer**.

Data is loaded dynamically via `fetch('/api/stories.json')` with query params for search/filter/pagination. Cards are rendered client-side.

### 6.2 Story Reader — `_story_body.html` (wrapped by `public_story.html`)
A centered single column, `max-width:780px`, `24px 20px` padding. System-font UI + **Georgia serif body**.

Top-to-bottom (each section is admin-toggleable for visibility):
1. **Reading progress bar** — fixed `3px` orange bar at the very top, fills with scroll.
2. **Back link** — "← Back to stories".
3. **Country flag block** — peach-bordered box with a real flag image (`56×42`, from flagcdn.com) + country name + sport.
4. **Tag row** (`.r-tags`) — badges: Demo (if seed), Athlete/Para badge, sport, country, reading-time, "🔖 Save" bookmark toggle.
5. **Title** (`.r-title`, `22px`).
6. **Byline** — small round initials avatar + name + country + sport.
7. **Hairline divider**.
8. **Key facts** — optional grid of up to 3 peach fact tiles with orange left border.
9. **Prose blocks** (`.r-body`) — Georgia serif, `15px`, line-height `1.85`. Intro block, then mid block.
10. **Pull quote** (`.pullquote`) — peach box, orange `3px` left border, italic serif quote.
11. **Comeback timeline** (`.tl-box`) — boxed; rows of colored dot + year + event text.
12. **Takeaways** (`.takeaway-box`) — boxed list with orange dots; optional inline goal-input box.
13. **Inner reframe / Why this works** — optional boxed blocks.
14. **Share box** (`.share-box`) — pill share buttons (WhatsApp, Twitter/X, Copy link, Instagram).
15. **Inline newsletter CTA** — dark gradient box with email form.
16. **"More comebacks"** — `.mgrid` of small related-story cards (`.mcard`, `96px` thumb).
17. **Continue-reading rail** — populated from localStorage history.

Behaviors: scroll-progress bar; prose blocks fade-up via IntersectionObserver; bookmark toggle persists to `localStorage.nq_bookmarks_v1`; reading history saved to `localStorage`.

### 6.3 Saved — `saved.html`
Public page. Reads bookmarked IDs from `localStorage`, fetches each via `/api/story/<id>.json`, renders a card grid. Peach eyebrow, serif H1 "Saved *stories*", empty-state nudging the user to bookmark. Each card has a "Remove" action.

### 6.4 Submit — `submit.html`
Public page. Peach eyebrow, serif H1 "Know an athlete *worth covering?*", a form in a `#FAF9F5` rounded panel: athlete name, sport + country (2-col), a textarea ("why is this story worth telling"), optional email, dark submit button. Success state replaces the form with a green confirmation panel. POSTs to `/api/submit`.

### 6.5 Admin Home — `admin_home.html`
Admin dashboard. A page header, an **active-model card**, an **analytics row** (Subscribers / Total visits / Today / Unique visitors / Pending — clickable stat tiles), a **tools grid** (Research athlete / Run pipeline / Discover / Process queue — each a bordered card with a form), a **live-jobs panel** (progress bars + step lists, polls `/admin/jobs.json`, auto-refreshes every 15s while a job runs), a **pending-review table** (bulk-select checkboxes, sticky bulk-action bar, sort dropdown, per-row 👁 preview / ✏ edit / Review / Approve / Reject / 🗑 delete), a **saved-dossiers** section, and **recently-published** rows. Includes an inline metadata-edit modal.

### 6.6 Admin Review — `admin_review.html`
Single story review. QA banner (confidence circle, verdict badge, score bars for factual/tone/etc., red-flag list, uncertain facts), a **public-visibility control panel** (21 section checkboxes + presets: Show all / Story only / Minimal + "Preview as visitor"), then the embedded `_story_body.html` preview, then a footer with Approve / Reject.

### 6.7 Admin Research — `admin_research.html`
Research dossier viewer. Athlete photo, head row with name/sport/country/flag/model badge, a **coverage bar** (X/11 fields, % colored), action buttons (Edit photo / Re-research with a model dropdown / Write full story / Discard). Below: stacked `.dossier-card`s for birth, disability, early life, key struggles, turning point + quote, training habits, competitions, sources (with credibility chips), uncertain facts.

### 6.8 Admin Subscribers — `admin_subscribers.html`
Newsletter management — stat tiles, subscriber table (email, source, joined date, resend / unsubscribe), CSV export, a broadcast composer (subject + body), and broadcast history.

### 6.9 Admin Login — `admin_login.html`
Minimal centered card: "Admin sign-in required", password field, orange "Sign in" button.

---

## 7. Interaction & Motion

| Pattern | Where | Detail |
|---|---|---|
| Fade-up entrance | Hero text, stats, chips, cards | `@keyframes fadeUp` — opacity + `translateY(14px→0)`, staggered delays |
| Count-up | Home stats | Numbers animate 0→value on scroll-into-view |
| Shimmer skeleton | Card images | Diagonal moving gradient until image loads |
| Hover lift | Cards, buttons | `translateY(-2/-3px)` + shadow |
| Image zoom | Card / featured image | `scale(1.04–1.05)` on hover |
| Scroll progress | Story reader | Fixed `3px` orange bar |
| Section reveal | Story prose | IntersectionObserver adds `.in` class |
| Floating glow | Hero background | Slow `float` animation on a radial-gradient blob |
| Spinner | Load-more button | Rotating orange ring |
| Dark-mode toggle | Nav | Instant theme swap, persisted |

All transitions are short (`.15s`–`.25s`, ease). Nothing flashy — the motion is calm and editorial.

---

## 8. Responsive Behavior

- Single fluid layout; no separate mobile templates.
- Key breakpoint: **`max-width:680px`** — hero shrinks (`64px→38px` headline), hero search stacks vertically.
- **`max-width:820px`** — featured card collapses from 2-column to 1-column.
- Grids use `repeat(auto-fit, minmax(...))` so cards reflow naturally (cards `310px` min, stats `160px` min, related `180px` min).
- Filter bar and tag rows wrap with `flex-wrap`.

---

## 9. File Map (UI)

```
scripts/dashboard/templates/
├── base.html            # shared shell: nav, theme, modals, newsletter pill
├── public_home.html     # landing: hero, stats, filters, featured, grid, newsletter
├── public_story.html    # thin wrapper → includes _story_body.html
├── _story_body.html     # the story reader (also embedded in admin review)
├── saved.html           # bookmarked stories (localStorage-driven)
├── submit.html          # community athlete-submission form
├── admin_home.html      # admin dashboard
├── admin_review.html    # single-story QA + visibility + approve/reject
├── admin_research.html  # research dossier viewer
├── admin_subscribers.html  # newsletter list + broadcasts
└── admin_login.html     # admin sign-in
site/index.html          # standalone static mockup (design reference, not served)
```

> Note: there is **no external CSS file**. Each template carries its own
> `<style>` block; shared tokens & components live in `base.html`.

---

## 10. Notes for a Redesign

If redesigning, preserve these so the app keeps working:

1. **Keep the CSS-variable token names** in `base.html` `:root` (and the `--ink/--bg/--line/--accent` aliases) — many templates reference them directly.
2. **Keep the dark-theme mechanism** — `html[data-theme="dark"]` overrides + the `#theme-dark` style-tag media flip.
3. **Keep class names** used by JavaScript: `.card`, `.card-img`, `.card-img-shell`, `.fchip`, `.stat-n`, `.read-progress`, `#cards-grid`, `#nl-pill`, `#nl-modal`, `#admin-login`, `#theme-toggle`, `.in` (fade-in state).
4. **Keep the Jinja blocks**: `{% block content %}`, `{% block title %}`, `tab_home/tab_saved/tab_submit/tab_admin/tab_subs`.
5. **Keep template-injected globals**: `flag()`, `country_iso()`, `vis()`, `is_admin`, `site`, `story_model`, `research_model`, `SECTION_KEYS`.
6. The story reader's **21 toggleable sections** are gated by `vis(s, 'section_key')` — don't remove that wrapper logic.
7. Endpoints the UI calls: `/api/stories.json`, `/api/story/<id>.json`, `/api/subscribe`, `/api/submit`, `/admin/jobs.json`.

### Current design summary (one line)
> Warm editorial minimalism — cream/white surfaces, near-black ink, a single
> burnt-orange accent (`#D85A30`), serif headlines + sans body, hairline borders,
> soft corners, calm fade-in motion, light-first with full dark mode.
