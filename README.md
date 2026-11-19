# Movie Roulette for macOS

**500 great films. One spin. Your next movie night, sorted.**

A macOS desktop app that picks a random film from [Letterboxd’s official Top 500 Films](https://letterboxd.com/official/list/letterboxds-top-500-films/). Spin the wheel, hear the roulette clicks slow down, and discover what to watch next.

## Features

- **Animated roulette wheel** with a dark cinema theme and 500 rank slots.
- **Equal odds** for every film: a 1-in-500 chance on every spin.
- **Spinning sound** that slows with the wheel, plus a mute button.
- **Film details** showing the selected rank, title, and a link to Letterboxd.
- **Automatic updates** from public Letterboxd pages in the background.
- **Offline support** using a saved cache or the included 500-film snapshot.
- **No API key required.**

## Quick start

### Requirements

- macOS 12 or later, on Apple Silicon or Intel.
- Python 3.10–3.14. Download it from [python.org](https://www.python.org/downloads/macos/) if needed.
- An internet connection for the initial dependency installation.

### Launch from Finder

Keep the downloaded files together in the `MovieRoulette` folder, then double-click **Launch Movie Roulette.command**.

The launcher creates a local Python environment and installs dependencies on its first run. Later launches reuse that environment. Once setup is complete, the app can run offline.

### Launch from Terminal

Replace the example path with your folder’s location:

```sh
cd "/path/to/MovieRoulette"
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python app.py
```

For subsequent launches, run:

```sh
.venv/bin/python app.py
```

Activating the environment is optional. If you prefer to activate it, use `source`:

```sh
source .venv/bin/activate
python app.py
```

## Using the app

1. Press **Spin for a film** to start the wheel.
2. Wait for it to land on your selected film. Its rank and title appear below the wheel.
3. Click **Open film on Letterboxd** to view the film’s page.

Use **Sound: On** to mute immediately. Turning sound back on takes effect on the next spin. Playback stops when the spin finishes or the window closes, and volume follows your Mac’s system volume.

The app refreshes the list on every launch. You can spin while it fetches; an update received during a spin is applied afterward. Use **Refresh list** to try again manually. The status area shows the snapshot date and any fetching errors.

Every spin samples all 500 films independently, so repeats are possible. All 500 slots appear on the wheel, with a rank label every 25 slots for readability.

## Data and offline support

The source is Letterboxd’s official **Top 500 Films**, the continuation of its former **Official Top 250 Narrative Feature Films** list. The app uses all 500 films in the list’s own order.

It scrapes five public HTML pages with `requests` and Beautiful Soup. Each page gets up to three attempts, increasing retry delays, and connection/read timeouts. A short pause separates successful page requests.

Before saving an update, the app checks for exactly 500 films, ranks 1–500, and unique valid Letterboxd film links. Only a complete, validated update replaces the cache.

### Snapshot fallback

The app loads the first valid snapshot available:

1. Your saved cache at `~/Library/Application Support/Movie Roulette/top500.json`.
2. The bundled `snapshot.json` file.

If a refresh fails, the current snapshot stays available. Offline rankings may become stale; check the date shown in the app. If neither snapshot is valid, spinning stays disabled until a refresh succeeds.

To update the bundled snapshot while online:

```sh
.venv/bin/python data.py
```

Letterboxd can change its page structure or restrict requests. The app reports these failures and falls back to its snapshot; it does not bypass access controls. Parser changes belong in `parse_page()` and `fetch()` in `data.py`.

## Build a standalone Mac app

Run these commands from the project folder on the Mac architecture you want to support:

```sh
.venv/bin/python -m pip install 'pyinstaller>=6.11,<7'
.venv/bin/python -m PyInstaller \
  --noconfirm \
  --windowed \
  --name "Movie Roulette" \
  --add-data "snapshot.json:." \
  --add-data "spin.wav:." \
  app.py

open "dist/Movie Roulette.app"
```

The resulting `.app` includes Python, Qt, the offline snapshot, and the spinning sound. Users of that bundle do not need a separate Python installation.

This creates an unsigned local application. Signing and notarization for distribution are separate steps; this project does not include a signed installer.

## Project files

| File | Purpose |
| --- | --- |
| `app.py` | Desktop interface, wheel animation, random selection, and sound playback |
| `data.py` | Letterboxd fetching, HTML parsing, validation, and caching |
| `snapshot.json` | Bundled offline list of 500 films |
| `spin.wav` | Original roulette ticking sound |
| `requirements.txt` | Python dependencies |
| `Launch Movie Roulette.command` | Mac launcher and first-run setup |
| `tests/test_data.py` | Data validation, retry, fallback, and wheel landing checks |

Sound uses macOS’s built-in `/usr/bin/afplay`; no extra audio dependency is required. Film selection uses Python’s `secrets.randbelow(500)` before the animation begins.

## Tests

```sh
.venv/bin/python -m unittest discover -s tests -v
```

The tests cover both supported HTML layouts, snapshot validation, corrupt-cache fallback, bounded retries, and correct wheel landing for every rank.

## Troubleshooting

**“Permission denied” when running `.venv/bin/activate`**  
Use `source .venv/bin/activate`, or run `.venv/bin/python app.py` directly.

**Dependency setup was interrupted**  
Rerun `.venv/bin/python -m pip install -r requirements.txt`, then launch the app again.

**The Finder launcher will not open**  
Use the Terminal instructions above. If the launcher’s executable permission is missing, restore it with:

```sh
chmod +x "Launch Movie Roulette.command"
```

**No sound**  
Check that the app shows **Sound: On** and your Mac’s volume is audible, then start a new spin.

**The list will not refresh**  
Check your connection and try **Refresh list**. The bundled or cached snapshot remains usable while Letterboxd is unavailable.

## Acknowledgments

Film rankings and links come from [Letterboxd](https://letterboxd.com/official/list/letterboxds-top-500-films/). Movie Roulette is an independent project and is not affiliated with or endorsed by Letterboxd.
