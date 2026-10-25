# YouTube Automator

A fully automated, **zero-cost** YouTube Shorts pipeline for `@tech_yatra`: picks a
topic, writes a script, generates voice, renders a vertical video from
HTML/CSS/JS scenes, generates a thumbnail, runs an automated safety check, and
uploads — on a daily schedule, with no human in the loop, via GitHub Actions.

**Niche:** .NET/C#, software development, and practical AI engineering tips.

## Why this is actually free

| Piece | Tool | Cost |
|---|---|---|
| Script/topic writing | Gemini free tier | Free |
| Voice | [`edge-tts`](https://github.com/rany2/edge-tts) (unofficial Microsoft Edge TTS) | Free, no API key |
| Visuals | HTML/CSS/JS rendered with Playwright + ffmpeg | Free |
| Upload | YouTube Data API v3 | Free (quota-limited — see below) |
| Scheduling | GitHub Actions cron | Free (public repo) / free tier minutes (private) |
| State | A committed `data/state.json` | Free |

No ElevenLabs, no paid image-gen, no server to rent.

## How it works

```
topic_generator.py --> script_writer.py --> voice_generator.py --> scene_renderer.py --> thumbnail_generator.py --> content_safety_check.py --> youtube_uploader.py
     (Gemini)             (Gemini)             (edge-tts)        (Playwright+ffmpeg)        (Playwright)              (Gemini)                 (YouTube API)
```

`main.py` runs all of these in order. `.github/workflows/daily-short.yml` runs
`main.py` once a day and commits the updated `data/state.json` (so future runs
know which topics were already covered).

### The one automated safety net

Since there is **zero human review**, `content_safety_check.py` asks Gemini to
flag copyright, misinformation, impersonation, or clickbait problems in the
script *before* upload. If it flags anything, the video still uploads — just
as `private` instead of `public` — so nothing is lost, but nothing bad goes
live unattended either. Check `data/state.json` periodically for any `"safe":
false` entries and decide whether to publish them manually.

## First-time setup

### 1. Get a Gemini API key (free)

1. Go to https://aistudio.google.com
2. Sign in with Google → Get API Key → Create API Key
3. No credit card required

### 2. Enable the YouTube Data API

1. Go to https://console.cloud.google.com → create a new project (or reuse one)
2. APIs & Services → Library → search **YouTube Data API v3** → Enable
3. APIs & Services → OAuth consent screen:
   - User type: **External**
   - Fill in app name/contact, add scope `.../auth/youtube.upload`
   - Add your own Google account as a **Test user**
   - **Important:** while the app is in "Testing" status, Google expires the
     refresh token after 7 days of the pipeline NOT running. Since this runs
     daily, that's never a problem — but if you ever pause it for over a
     week, you'll need to redo step 3 below. To avoid this entirely, submit
     the app for verification and set it to **Production** (takes Google a
     few days to review; not required to get started).
4. APIs & Services → Credentials → Create Credentials → OAuth client ID:
   - Application type: **Desktop app**
   - Download the `client_secret.json` file

### 3. Mint your refresh token (run once, locally — not in CI)

```bash
pip install google-auth-oauthlib
python scripts/youtube_oauth_setup.py path/to/client_secret.json
```

This opens a browser once for you to sign in and grant access, then prints:
```
YOUTUBE_CLIENT_ID=...
YOUTUBE_CLIENT_SECRET=...
YOUTUBE_REFRESH_TOKEN=...
```

### 4. Add GitHub Secrets

In your repo: Settings → Secrets and variables → Actions → New repository secret.
Add all four:
- `GEMINI_API_KEY`
- `YOUTUBE_CLIENT_ID`
- `YOUTUBE_CLIENT_SECRET`
- `YOUTUBE_REFRESH_TOKEN`

### 5. Configure your channel settings

```bash
cp config/settings.example.json config/settings.json
```
Edit niche, video length, voice, and upload privacy defaults as you like.
`config/niches.json` has the full topic pool and tone for the `dev` niche —
edit it any time to steer content.

### 6. Test it

Local dry run (does everything except the real upload):
```bash
pip install -r requirements.txt
playwright install chromium
export GEMINI_API_KEY=...  YOUTUBE_CLIENT_ID=...  YOUTUBE_CLIENT_SECRET=...  YOUTUBE_REFRESH_TOKEN=...
python main.py --dry-run
```
Check `output/<run_id>/final.mp4` before trusting it with a real upload.

Or trigger the real GitHub Actions workflow manually once (Actions tab →
"Generate and publish a YouTube Short" → Run workflow → tick "Dry run" first).

### 7. Turn it on

Once you're happy with the output, leave `dry_run` unchecked and the
`daily-short.yml` cron schedule takes over — nothing more to do.

## YouTube API quota

The free default quota is 10,000 units/day; one video upload costs ~1,600
units, so you can comfortably upload several videos a day without asking
Google for a quota increase (one video/day uses a small fraction of it).

## Project layout

```
engine/
  topic_generator.py       Gemini picks the next topic, avoiding recent repeats
  script_writer.py         Gemini writes the scene-by-scene script
  voice_generator.py       edge-tts voice + word-level timing per scene
  scene_renderer.py        HTML/CSS/JS scenes -> Playwright frames -> ffmpeg -> MP4
  thumbnail_generator.py   HTML thumbnail template -> Playwright screenshot
  content_safety_check.py  Gemini pre-publish policy check (the safety net)
  youtube_uploader.py      Refresh-token-based unattended upload
templates/
  scene.html                Video scene template (6 scene types, kinetic text, captions)
  thumbnail.html             Thumbnail template
config/
  settings.example.json     Copy to settings.json and edit
  niches.json                Topic pools / tone per niche
data/
  state.json                 Run history (committed by the workflow each day)
main.py                      Orchestrator: python main.py [--dry-run] [--topic "..."]
.github/workflows/
  daily-short.yml             The scheduler
```

## Adding a new scene type

Add a case to `renderContentForType()` in `templates/scene.html` (CSS/JS,
no build step), add it to the `SCENE_TYPES` list in
`engine/script_writer.py` so Gemini knows it exists, done.
