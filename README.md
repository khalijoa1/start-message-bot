# Start Message Bot

A standalone Telegram bot that sends a fully configurable welcome message
the moment someone presses /start: text, one optional photo or video, and
inline buttons - each button either opens a link (channel, website,
WhatsApp, another bot, whatever) or reveals another screen of content.
Everything is editable from inside Telegram, no redeploy required.

## How it works

Content is organised as **screens**. The root screen (shown on `/start`)
is always there; any other screen only exists because a button somewhere
points at it, so screens form a simple tree the operator builds entirely
by tapping buttons in the bot's own admin menu.

Each screen has:
- **Text** (HTML formatting supported - `<b>bold</b>`, `<i>italic</i>`, `<a href="...">links</a>`)
- **Media** - one optional photo or video
- **Buttons** - each one either opens a URL directly, or shows another screen when tapped

## Setup

1. Create a bot: message `@BotFather`, `/newbot`, copy the token.
2. Find your Telegram user id (message `@userinfobot`).
3. Copy `.env.example` to `.env` and fill in `BOT_TOKEN` and `ALLOWED_USER_IDS`
   (your id; comma-separate for more than one admin).
4. Install dependencies and run:
   ```
   python -m venv .venv
   .venv\Scripts\python.exe -m pip install -e .
   .venv\Scripts\python.exe bot.py
   ```

## Usage

- `/start` - shows the root screen to anyone.
- `/admin` - operator-only admin menu:
  - **Edit Start Message** - jumps straight into editing the root screen.
  - **List Screens** - see every screen, tap one to edit it.
  - **Add Screen** - create a new screen (name it, then it isn't reachable
    by anyone until a button somewhere points at it).
  - Inside a screen's edit menu: **Edit Text**, **Set Photo/Video** (or
    type "remove" to clear it), **Manage Buttons** (add a button that
    opens a link or jumps to another screen; the "New Screen" option in
    the button-target picker creates and links a screen in one step).
- `/cancel` - clears whatever admin step you're in the middle of.

## Data safety

Screens and buttons live in SQLite. On Railway this MUST be on an
attached persistent volume (see Deploying below) - otherwise every edit
is wiped on the next redeploy, since the container filesystem is
otherwise ephemeral.

## Deploying to Railway

1. Push this repo to GitHub, connect it as a Railway service.
2. Attach a persistent volume mounted at `/data`.
3. Set `DATABASE_URL=sqlite+aiosqlite:////data/start_message_bot.db`
   (four slashes) in the service's Variables tab, along with `BOT_TOKEN`
   and `ALLOWED_USER_IDS`.
4. Railway auto-detects the Dockerfile and redeploys on every push to `main`.

## Limitations (v1)

- Buttons can't be reordered or edited in place once created - delete and
  re-add if you need to change a button's label, URL, or target.
- No support for multiple media items (albums) on one screen - one photo
  or one video per screen.
- Deleting a screen doesn't clean up buttons elsewhere that pointed at
  it - a leftover button just shows "This button no longer leads
  anywhere" if tapped, which is safe but a little untidy; delete such
  buttons manually via Manage Buttons on whichever screen has them.
