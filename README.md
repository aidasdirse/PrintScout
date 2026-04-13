# PrintScout — 3D Market Intelligence

Auto-scanning pipeline that monitors Reddit, eBay, Etsy, and Google Trends to surface 3D printing product opportunities. Runs every 6 hours and scores each niche with AI.

## What it does
1. Scrapes trending posts from r/3Dprinting, r/Etsy, r/smallbusiness, and more
2. Uses Claude AI to extract product keyword opportunities
3. Fetches real market data: eBay sold prices, Etsy listing counts, Google Trends scores
4. Scores and ranks every keyword by opportunity, demand, and competition
5. Refreshes every 6 hours automatically

---

## Setup — API Keys Needed

### 1. Anthropic API Key (required)
- Go to https://console.anthropic.com
- Create an API key

### 2. eBay App ID (recommended — free)
- Go to https://developer.ebay.com
- Create an account → My Account → Application Keys
- Copy your "App ID (Client ID)"

### 3. Etsy API Key (recommended — free)
- Go to https://www.etsy.com/developers/register
- Create an app → copy your Keystring

---

## Deploy to Railway (free tier, ~10 min)

### Step 1 — Push to GitHub
1. Create a new repo on github.com
2. Upload all these files (drag & drop works)
3. Commit

### Step 2 — Deploy on Railway
1. Go to https://railway.app and sign in with GitHub
2. Click "New Project" → "Deploy from GitHub repo"
3. Select your repo
4. Railway auto-detects Python and deploys

### Step 3 — Add environment variables
In Railway → your project → Variables tab, add:
```
ANTHROPIC_API_KEY=sk-ant-...
EBAY_APP_ID=YourApp-...
ETSY_API_KEY=your_etsy_key
```

### Step 4 — Done!
Railway gives you a public URL like `https://printscout-production.up.railway.app`
Open it — the pipeline runs immediately on startup, then every 6 hours.

---

## Run locally
```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
uvicorn main:app --reload
# Open http://localhost:8000
```

---

## Pipeline schedule
Default: every 6 hours. To change, edit `main.py`:
```python
IntervalTrigger(hours=6)  # change 6 to whatever you want
```

## Notes
- Reddit: no API key needed, uses public JSON endpoints
- Google Trends: may occasionally rate-limit; results show as "—" when blocked
- eBay/Etsy: without keys, those columns show "—" but everything else works
- SQLite database persists on Railway's filesystem (consider adding a Postgres volume for production)
