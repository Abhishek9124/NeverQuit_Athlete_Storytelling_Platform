# NeverQuit 🏆

> **AI-automated motivational storytelling platform for athletes, Paralympians, and differently-abled individuals who never gave up.**

NeverQuit is a fully autonomous content platform. The AI researches athletes from the web, writes vivid 10-section stories, translates them into 8 Indian languages, scores each story for confidence, and sends it to you for a single approval tap. After you approve, it auto-publishes to the website, newsletter, WhatsApp, Instagram, and Twitter — simultaneously. **You never write, research, or translate anything.**

---

## Table of Contents

- [What is NeverQuit?](#what-is-neverquit)
- [Key Differentiators](#key-differentiators)
- [Architecture Overview](#architecture-overview)
- [The AI Pipeline](#the-ai-pipeline)
- [Tech Stack](#tech-stack)
- [Story Template](#story-template)
- [Sports Coverage](#sports-coverage)
- [Project Roadmap](#project-roadmap)
- [Budget & Revenue](#budget--revenue)
- [Getting Started](#getting-started)
- [Environment Variables](#environment-variables)
- [Directory Structure](#directory-structure)
- [Deployment](#deployment)
- [Contributing](#contributing)

---

## What is NeverQuit?

NeverQuit is a fully AI-automated motivational storytelling website focused exclusively on athletes, Paralympians, and differently-abled individuals. It covers **34 sports** across **8 Indian languages** (English + Hindi + Tamil + Kannada + Marathi + Bengali + Telugu + Gujarati).

**Your only job:** Approve or reject a story in 2–10 minutes per day.

**Everything else is automated:**
- Research and discovery of athlete stories
- 10-section story writing in vivid prose
- Translation into 7 Indian languages
- Quality scoring and fact-checking
- Publishing to website, newsletter, social media

---

## Key Differentiators

| # | Feature | Description |
|---|---------|-------------|
| 1 | **Fully AI-automated** | AI researches, writes, translates — you only approve. Zero manual writing. |
| 2 | **8 Indian languages** | Every story published in English + Hindi + Tamil + Kannada + Marathi + Bengali + Telugu + Gujarati. |
| 3 | **Comeback timeline** | Visual year-by-year timeline inside every story — makes journeys feel real and mappable. |
| 4 | **AI story matching** | User types their struggle → AI finds the most relevant athlete story for their exact situation. |
| 5 | **Personal goal plan** | After every story, AI generates a 30-day action plan based on that athlete's actual methods. |
| 6 | **Para + Olympic focus** | Covers ALL sports including Paralympics — a massively underserved niche in Indian regional languages. |

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                        NEVERQUIT PLATFORM                           │
│                                                                     │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  Athlete     │    │  Research    │    │   Story Writer       │  │
│  │  Discovery   │───▶│  Agent       │───▶│   Agent              │  │
│  │  Agent       │    │  (web search │    │   (Claude Sonnet 4)  │  │
│  │  (daily)     │    │  + scrape)   │    │   10 sections        │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│                                                   │                 │
│                                                   ▼                 │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────────────┐  │
│  │  Publishing  │    │  OWNER       │    │   Translation +      │  │
│  │  Agent       │◀───│  APPROVAL    │◀───│   Quality Checker    │  │
│  │  (all        │    │  DASHBOARD   │    │   Agent              │  │
│  │  platforms)  │    │  (YOU)       │    │   (confidence score) │  │
│  └──────────────┘    └──────────────┘    └──────────────────────┘  │
│         │                                                           │
│         ▼                                                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Website │ Newsletter │ WhatsApp │ Instagram │ Twitter/X    │   │
│  └─────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## The AI Pipeline

NeverQuit uses **5 fully automated AI agents** and **1 human touchpoint** (you).

### Step 1 — Athlete Discovery Agent
**Runs:** Every day automatically  
**What it does:** Scans sports news APIs, Wikipedia recent updates, Olympics and Paralympic federation pages to identify new athletes with compelling comeback stories. Adds them to the research queue.  
**Tools:** Web Search API, news feeds, sports federation APIs  
**Time:** ~5 min/day  
**Your involvement:** None

---

### Step 2 — Research Agent
**What it does:** Takes each athlete from the queue and searches the web comprehensively — news articles, YouTube interview transcripts, Wikipedia, official sports body pages, social media. Extracts: birth details, disability/injury, when they started, key struggles, coach names, exact quotes, competition results, dates.  
**Tools:** Claude API + `web_search_tool`, Wikipedia API  
**Time:** ~8 min/athlete  
**Your involvement:** None

---

### Step 3 — Story Writer Agent
**What it does:** Takes raw research JSON and fills all 10 sections of the NeverQuit story template. Writes in vivid, emotional, specific prose — not generic motivational language.  
**Model:** `claude-sonnet-4-20250514`  
**Time:** ~3 min/story  
**Your involvement:** None

---

### Step 4 — Translation Agent
**What it does:** Translates the approved English draft into 7 Indian languages (Hindi, Tamil, Kannada, Marathi, Bengali, Telugu, Gujarati). Translations are natural and conversational — not word-for-word literal. Proper nouns and dates are preserved exactly. Each language version is saved separately.  
**Tools:** Claude API with language-specific prompts  
**Time:** ~6 min for all 7 languages  
**Your involvement:** None

---

### Step 5 — Quality Checker Agent
**What it does:** Reviews the story for factual consistency, tone (emotional but not exaggerated), word count (800–1200 words), template completeness, and uncertain facts. Generates a confidence score (0–100%) and flags any facts where sources conflict or are unverified. Low-confidence facts are highlighted in red in the approval dashboard.  
**Tools:** Claude API with fact-checking prompts  
**Time:** ~2 min/story  
**Your involvement:** None

---

### Step 6 — Owner Approval (YOU)
**What you do:**
1. Receive a notification
2. Open the approval dashboard
3. Read the story in English (or switch to any language tab)
4. Check the AI confidence score and any red-flagged facts
5. **Score ≥ 90% and minor flags → approve in 2 minutes**
6. **Score < 75% → verify flagged facts on the official sports federation site or Wikipedia before approving**

**Time:** 2–10 min/story  
**This is your only job.**

---

### Step 7 — Publishing Agent
**Triggered:** Instantly when you tap Approve  
**What it does simultaneously:**
1. Pushes story to website in all 8 languages
2. Sends to Mailchimp newsletter list
3. Posts WhatsApp-optimised message with link
4. Generates and posts Instagram story card with pull quote
5. Posts Twitter/X thread of 5 tweets
6. Saves story to Notion database for records

**Time:** ~30 seconds  
**Your involvement:** None

---

### Step 8 — Social Asset Generator
**What it does:** After publishing, generates: WhatsApp message (2 lines + link), Twitter thread (5 tweets), Instagram caption with hashtags, email subject line (A/B tested), newsletter summary (3 sentences), and a downloadable square image card with the pull quote and athlete name.  
**Tools:** Claude API, image generation API  
**Time:** ~2 min  
**Your involvement:** None

---

## Tech Stack

| Layer | Tool | What it does | Cost | Phase |
|-------|------|-------------|------|-------|
| Website (frontend) | **Webflow** | No-code website builder — homepage, story reader, filters, 8 language tabs | Free → ₹1,400/mo | Launch |
| Content database | **Notion + Webflow CMS** | Stories written in Notion, Webflow CMS pulls automatically | Free | Launch |
| AI engine | **Claude API (Sonnet 4)** | Research, write, translate, score confidence, generate social assets | ~₹350/mo | Launch |
| Web search in AI | **Claude `web_search` tool** | Real-time internet search for athlete news, Wikipedia, interviews | Included in API | Launch |
| Pipeline automation | **Make.com** | Connects everything — triggers AI pipeline daily, routes stories to all platforms | Free → ₹830/mo | Month 2 |
| AI story matching | **Supabase + pgvector** | Semantic vector search — user types struggle, finds closest matching story | Free → ₹830/mo | Month 4 |
| Email newsletter | **Mailchimp** | Weekly story digest every Monday | Free → ₹800/mo | Month 2 |
| Payments | **Razorpay** | UPI, cards, subscriptions — Indian-first payment gateway | ₹0 setup + 2% | Month 6 |
| Analytics | **Google Analytics 4** | Story completion rates, language popularity, traffic sources | Free | Month 2 |
| Heatmaps | **Hotjar** | Where readers scroll — identifies engagement with timeline, goal box | Free tier | Month 2 |
| Domain | **GoDaddy** | Register `.in` domain | ₹800/year | Launch |
| Code editor | **Replit** | Run AI pipeline scripts without local setup | Free | Month 2 |
| Version control | **GitHub** | Store all pipeline scripts, automation configs, custom CSS | Free | Month 2 |
| Social scheduling | **Buffer** | Schedule Instagram, Twitter, LinkedIn posts in advance | Free → ₹830/mo | Month 3 |
| Future frontend | **Next.js + Vercel** | When you outgrow Webflow (Month 6–8), migrate for full control | Free (Vercel hobby) | Month 6+ |

---

## Story Template

Every NeverQuit story follows a fixed 10-section template. The AI fills all sections automatically.

| # | Section | Word Count | Purpose |
|---|---------|-----------|---------|
| 01 | **Hook** — opening 3 sentences | 40–60 | The most vivid, specific, human moment. Makes the reader stop scrolling. |
| 02 | **The world they came from** | 100–150 | Where they grew up, what life was like, who said it was impossible. |
| 03 | **The darkest moment** | 120–180 | The scene where most people would quit. Specific details — the exact day, feeling, person who doubted them. |
| 04 | **The turning point** | 80–120 | One person, one conversation, one piece of information that changed everything. Named and quoted. |
| 05 | **The grind — what they actually did** | 120–160 | The unglamorous daily work. What they ate, how many hours, what they failed at. |
| 06 | **Pull quote** | 15–25 words | One sentence — ideally their own words — that readers will screenshot and share. Becomes the Instagram card. |
| 07 | **Comeback timeline** | 60–80 total | Year-by-year bullet points: the fall, struggle years, turning point, victory. Displayed as a visual widget. |
| 08 | **What you can take from this story** | 60–90 | Three specific, actionable lessons tied to what this person actually did — not generic advice. |
| 09 | **Personal goal box prompt** | 1–2 sentences | Prompts the reader to type their goal. AI generates a 30-day action plan based on the athlete's methods. |
| 10 | **WhatsApp share message** | Under 200 chars | Pre-written 2-line message optimised for WhatsApp sharing. Emotional hook + one specific fact + link. |

**The Golden Rule:** Never say "he was very motivated" — show it. Write "He woke at 4:30 AM, before his family, before his coach, before the neighbours' dogs, and went to the ground alone." Specific details make people feel real. Vague words make people feel nothing.

---

## Sports Coverage

NeverQuit covers **34 sports** across three priority tiers.

### Priority 1 — Launch Sports
Cricket, Wrestling, Shooting, Archery, Boxing, Badminton, Athletics/Track, Weightlifting, Swimming, Para Swimming

### Priority 2 — Growth Sports
Table Tennis, Gymnastics, Football, Tennis, Hockey, Judo, Cycling, Kabaddi, Blind Cricket, Mountaineering, Chess

### Priority 3 — Long-term Coverage
Volleyball, Squash, Rowing, Sailing, Equestrian, Fencing, Taekwondo, Triathlon, Boccia, Goalball, Sitting Volleyball, Wheelchair Basketball, Wheelchair Racing

All sports include their Paralympic equivalent where one exists. Paralympic-only sports (Boccia, Goalball, Sitting Volleyball, Wheelchair Basketball/Racing) are also covered.

---

## Project Roadmap

### Phase 1 — Foundation (Month 0–1)
- [ ] Study 10 top motivational storytelling platforms (Humans of NY, Paralympic.org, Olympics channel)
- [ ] Register domain — `neverquit.in` on GoDaddy (₹800)
- [ ] Create Google Form for athlete story submissions
- [ ] Set up Claude API account and get API key — test pipeline manually first
- [ ] Write first 3 stories manually to understand the format before automating
- [ ] Post in 5 WhatsApp groups + 3 Reddit communities to validate interest

### Phase 2 — Build MVP (Month 1–3)
- [ ] Build website on Webflow — homepage, story reader, filters, 8 language selector
- [ ] Connect Notion as story database — Webflow CMS pulls from Notion
- [ ] Build full agentic AI research pipeline — Claude searches web, drafts story, translates
- [ ] Set up automated daily scheduling — pipeline runs daily to find new athletes
- [ ] Build owner approval dashboard — read stories, approve/reject with one click
- [ ] Set up Mailchimp newsletter — weekly story digest every Monday
- [ ] Set up Google Analytics + Hotjar

**Milestone:** 20 stories published + 500 monthly visitors

### Phase 3 — AI Features (Month 3–6)
- [ ] Build AI story match — user types struggle, Claude finds closest story
- [ ] Build 30-day goal plan box — AI generates plan based on athlete's methods
- [ ] Add Hindi translations to top 20 stories — review for naturalness
- [ ] Build Instagram story card generator from pull quotes
- [ ] Add community comments via Disqus (free)
- [ ] Build India sports map — tap a state, see athletes from that region

**Milestone:** 5,000 monthly readers + 200 email subscribers

### Phase 4 — Revenue (Month 6–12)
- [ ] Pitch JSW Sports, OGQ, GoSports for story sponsorships (₹15K–₹50K/story)
- [ ] Build school programme — assign stories, students write reflections (₹2K/school/mo)
- [ ] Launch Razorpay subscriptions — ₹99/mo for ad-free + regional languages
- [ ] Apply to Startup India, iStart, SINE IIT Bombay for grants (₹2–10 lakh)
- [ ] Hire part-time freelance story editor at ₹8,000–₹12,000/mo
- [ ] Launch audio narration — AI voice reads each story in chosen language

**Milestone:** ₹1,00,000/month revenue by Month 12

---

## Budget & Revenue

### Monthly Operating Costs

| Item | Phase 1 (Mo 0–1) | Phase 2 (Mo 1–3) | Phase 3 (Mo 3–6) | Phase 4 (Mo 6–12) |
|------|------------------|------------------|------------------|------------------|
| Domain (.in/year ÷ 12) | ₹67 | ₹67 | ₹67 | ₹67 |
| Claude API | ₹500 | ₹800 | ₹1,500 | ₹2,500 |
| Webflow hosting | ₹0 | ₹0 | ₹1,400 | ₹1,400 |
| Supabase database | ₹0 | ₹0 | ₹0 | ₹830 |
| Mailchimp newsletter | ₹0 | ₹0 | ₹0 | ₹800 |
| Make.com automation | ₹0 | ₹0 | ₹830 | ₹830 |
| Freelance story editor | ₹0 | ₹0 | ₹0 | ₹10,000 |
| Miscellaneous | ₹200 | ₹200 | ₹500 | ₹1,000 |
| **TOTAL** | **~₹767** | **~₹1,067** | **~₹4,297** | **~₹17,427** |

### Revenue Projections

| Month | Story Sponsors | School Programme | Subscriptions (₹99) | Grants | Total |
|-------|---------------|-----------------|--------------------|----|-------|
| 1–3 | ₹0 | ₹0 | ₹0 | ₹0 | ₹0 |
| 4 | ₹2,000 | ₹0 | ₹0 | ₹0 | ₹2,000 |
| 5 | ₹3,000 | ₹2,000 | ₹990 | ₹0 | ₹6,990 |
| 6 | ₹5,000 | ₹4,000 | ₹1,980 | ₹0 | ₹10,980 |
| 7 | ₹10,000 | ₹6,000 | ₹2,970 | ₹5,000 | ₹23,000 |
| 8 | ₹15,000 | ₹8,000 | ₹4,950 | ₹5,000 | ₹32,950 |
| 9 | ₹20,000 | ₹10,000 | ₹7,920 | ₹10,000 | ₹47,920 |
| 10 | ₹25,000 | ₹12,000 | ₹9,900 | ₹10,000 | ₹56,900 |
| 11 | ₹35,000 | ₹16,000 | ₹14,850 | ₹15,000 | ₹80,850 |
| **12** | **₹45,000** | **₹20,000** | **₹19,800** | **₹15,000** | **₹99,800** |

### Revenue Streams Explained

**Story Sponsorships** — JSW Sports, Olympic Gold Quest, GoSports, PUMA India pay ₹15,000–₹50,000 to co-present a story. Their brand appears as "Presented by." Start pitching at 5,000 monthly readers. Target: ₹45,000/mo by Month 12.

**School Programme** — Teachers assign NeverQuit stories. Students write reflection essays. Sold monthly per school at ₹2,000. 10 schools = ₹20,000/mo. Pitch to CBSE schools with sports programmes first. Target: ₹20,000/mo by Month 12.

**Reader Subscriptions** — ₹99/month via Razorpay. Benefits: ad-free, all regional language versions, weekly PDF digest, early access. Needs ~200 subscribers for ₹20K/mo. Target: ₹19,800/mo by Month 12.

**Government Grants** — Startup India, iStart (Rajasthan), SINE IIT Bombay, CIIE IIM Ahmedabad. NeverQuit qualifies as sports-tech + social impact. Grants are ₹2–10 lakh, non-dilutive. Target: ₹15,000/mo averaged by Month 12.

---

## Getting Started

### Prerequisites

- Node.js 18+ (for any custom scripts)
- Python 3.10+ (for AI pipeline scripts)
- Accounts: Anthropic (Claude API), Webflow, Notion, Make.com, Mailchimp, GitHub

### 1. Clone the repository

```bash
git clone https://github.com/your-username/neverquit.git
cd neverquit
```

### 2. Install Python dependencies

```bash
pip install anthropic requests python-dotenv supabase
```

### 3. Set up environment variables

Copy `.env.example` to `.env` and fill in your keys:

```bash
cp .env.example .env
```

### 4. Test the AI pipeline manually

```bash
python scripts/pipeline/research_agent.py --athlete "Sheetal Devi"
```

### 5. Run the full pipeline on a single athlete

```bash
python scripts/pipeline/run_pipeline.py --athlete "Sheetal Devi" --dry-run
```

---

## Environment Variables

Create a `.env` file at the project root:

```env
# Anthropic
ANTHROPIC_API_KEY=sk-ant-...

# Supabase (for vector search + story database)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-key

# Webflow
WEBFLOW_API_KEY=your-webflow-token
WEBFLOW_COLLECTION_ID=your-cms-collection-id
WEBFLOW_SITE_ID=your-site-id

# Mailchimp
MAILCHIMP_API_KEY=your-mailchimp-key
MAILCHIMP_AUDIENCE_ID=your-list-id
MAILCHIMP_SERVER_PREFIX=us1

# Notion
NOTION_TOKEN=secret_...
NOTION_DATABASE_ID=your-database-id

# Social (via Buffer or direct APIs)
TWITTER_BEARER_TOKEN=your-token
BUFFER_ACCESS_TOKEN=your-token

# Razorpay (Month 6+)
RAZORPAY_KEY_ID=rzp_live_...
RAZORPAY_KEY_SECRET=your-secret

# Pipeline config
DAILY_STORY_QUOTA=1
MIN_CONFIDENCE_SCORE=75
AUTO_APPROVE_THRESHOLD=90
```

---

## Directory Structure

```
neverquit/
├── README.md
├── .env.example
├── .gitignore
│
├── scripts/
│   ├── pipeline/
│   │   ├── discovery_agent.py       # Step 1: Find new athletes daily
│   │   ├── research_agent.py        # Step 2: Deep research per athlete
│   │   ├── story_writer_agent.py    # Step 3: Write 10-section story
│   │   ├── translation_agent.py     # Step 4: Translate to 7 languages
│   │   ├── quality_checker_agent.py # Step 5: Confidence score + fact check
│   │   ├── publishing_agent.py      # Step 7: Publish everywhere
│   │   ├── social_asset_generator.py # Step 8: Social assets
│   │   └── run_pipeline.py          # Full pipeline orchestrator
│   │
│   ├── dashboard/
│   │   ├── app.py                   # Owner approval dashboard (Flask/FastAPI)
│   │   ├── templates/
│   │   │   └── review.html
│   │   └── static/
│   │
│   └── utils/
│       ├── notion_client.py
│       ├── webflow_client.py
│       ├── mailchimp_client.py
│       └── supabase_client.py
│
├── prompts/
│   ├── research_prompt.txt
│   ├── story_writer_prompt.txt
│   ├── translation_prompt_hindi.txt
│   ├── translation_prompt_tamil.txt
│   ├── translation_prompt_kannada.txt
│   ├── translation_prompt_marathi.txt
│   ├── translation_prompt_bengali.txt
│   ├── translation_prompt_telugu.txt
│   ├── translation_prompt_gujarati.txt
│   ├── quality_checker_prompt.txt
│   └── social_assets_prompt.txt
│
├── templates/
│   └── story_template.json          # 10-section template schema
│
├── data/
│   ├── sports_list.json             # 34 sports + athlete seed list
│   └── athlete_queue.json           # Daily discovery queue
│
└── docs/
    ├── pipeline_architecture.md
    ├── approval_dashboard_guide.md
    └── revenue_playbook.md
```

---

## Deployment

### Pipeline (Make.com)
1. Create a Make.com account
2. Import the scenario blueprint from `make_blueprints/daily_pipeline.json`
3. Connect your Anthropic, Notion, Webflow, and Mailchimp modules
4. Set the trigger to run daily at 6:00 AM IST

### Approval Dashboard
Deploy to Replit (free, no local setup needed):
1. Create a new Replit from the `/scripts/dashboard/` folder
2. Add all environment variables in Replit Secrets
3. Run `python app.py`
4. Access your dashboard at the Replit URL

### Website (Webflow)
1. Create a Webflow account
2. Build the site using Webflow University tutorials
3. Connect Webflow CMS to Notion using Make.com
4. Add the 8-language selector component

### Supabase Vector Search (Month 4+)
```sql
-- Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- Create stories table with embeddings
CREATE TABLE stories (
  id UUID DEFAULT gen_random_uuid() PRIMARY KEY,
  athlete_name TEXT NOT NULL,
  sport TEXT,
  hook TEXT,
  full_story_en JSONB,
  embedding VECTOR(1536),
  confidence_score FLOAT,
  published_at TIMESTAMPTZ,
  languages JSONB
);

-- Create index for fast similarity search
CREATE INDEX stories_embedding_idx ON stories
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

---

## Contributing

This is a solo founder project. Contributions are not open at this time, but here's how the codebase is organised if you're reviewing it:

- All AI prompts live in `/prompts/` — tweak these to improve story quality
- Each agent script is independently runnable with `--dry-run` flag for testing
- The approval dashboard is intentionally minimal — your only interface is approve/reject
- All costs and revenue data are tracked in the original `NeverQuit_Startup_Plan.xlsx`

---

## License

Private. All rights reserved.

---

*Built by a solo fresher founder. Start budget: ₹0–₹50,000. Month 12 target: ₹1,00,000/month.*

*"They told Sheetal Devi she had no future without arms. She drew a bow with her feet and won Olympic gold."*
