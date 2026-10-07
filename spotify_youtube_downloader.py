import os, re, json, requests, time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from pytubefix import YouTube, Search
from pytubefix.cli import on_progress
from pytubefix.exceptions import VideoUnavailable
from moviepy import AudioFileClip

try:
    from pytubefix.exceptions import SABRError
    SABR_EXCEPTIONS = (SABRError,)
except ImportError:
    SABR_EXCEPTIONS = ()  # older pytubefix versions don't have this exception yet

# Selenium
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options

# ─────────────────────────────────────────────
# 📁 DEFAULT PATH
# ─────────────────────────────────────────────
DOWNLOAD_PATH = os.path.join(os.path.expanduser("~"), "Spotify_Downloads")

HEADERS = {"User-Agent": "Mozilla/5.0"}


# ══════════════════════════════════════════════
# 🎧 TRACK SCRAPER
# ══════════════════════════════════════════════

def scrape_track(url):
    try:
        r = requests.get(url, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")

        for tag in soup.find_all("script", type="application/ld+json"):
            data = json.loads(tag.string or "{}")
            name = data.get("name")
            artist = ""
            by = data.get("byArtist")

            if isinstance(by, list) and by:
                artist = by[0].get("name", "")
            elif isinstance(by, dict):
                artist = by.get("name", "")

            if name:
                return {"title": name, "artist": artist}
    except:
        pass

    return None


# ══════════════════════════════════════════════
# 🌐 PLAYLIST SCRAPER (SELENIUM AUTO)
# ══════════════════════════════════════════════

def scrape_playlist_browser(url):
    print("🌐 Using browser for playlist extraction...")

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-blink-features=AutomationControlled")

    driver = webdriver.Chrome(options=options)

    driver.get(url)
    time.sleep(6)

    # Scroll to load tracks
    for _ in range(20):
        driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
        time.sleep(1.5)

    tracks = []
    rows = driver.find_elements(By.CSS_SELECTOR, "div[role='row']")

    for row in rows:
        try:
            data = row.text.split("\n")
            if len(data) >= 3:
                tracks.append({
                    "title": data[1],
                    "artist": data[2]
                })
        except:
            continue

    driver.quit()
    return tracks


# ══════════════════════════════════════════════
# 🎯 YOUTUBE SEARCH
# ══════════════════════════════════════════════

def find_youtube(title, artist):
    query = f"{artist} {title} official audio"
    print(f"🔍 {query}")

    try:
        results = Search(query).videos
        if results:
            return results[0].watch_url
    except:
        pass

    return None


# ══════════════════════════════════════════════
# ⬇ DOWNLOAD  (updated for current pytubefix API)
# ══════════════════════════════════════════════

def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', '', name)


def get_progressive_stream(yt_url):
    """
    Try a handful of pytubefix client identities until one returns a
    progressive (non-SABR) stream. Different clients get different sets of
    available formats per video from YouTube, so a single client (e.g. WEB)
    frequently comes back empty even when another client works fine.
    Returns (yt, stream) or (None, None) if nothing worked.
    """
    candidate_clients = ["WEB", "MWEB", "ANDROID", "IOS", "TV_EMBED", "ANDROID_VR"]

    for client in candidate_clients:
        try:
            yt = YouTube(
                yt_url,
                client=client,
                on_progress_callback=on_progress,
            )
            stream = yt.streams.get_highest_resolution()
            if stream:
                return yt, stream
        except Exception:
            continue

    return None, None


def download(track, fmt):
    title = track["title"]
    artist = track["artist"]
    label = sanitize(f"{artist} - {title}")

    print(f"\n🎵 {label}")

    yt_url = find_youtube(title, artist)
    if not yt_url:
        print("❌ No match")
        return

    try:
        # Progressive streams (audio+video combined in one file, e.g. itag
        # 18/22) are served over plain HTTPS and do NOT require SABR/PoToken.
        # Only the separate high-res video-only and audio-only DASH streams
        # do — which is what was triggering the "SABR Maximum reload
        # attempts reached" errors. Try several client identities since
        # availability of the progressive stream varies per video/client.
        yt, stream = get_progressive_stream(yt_url)
        if not stream:
            print("❌ No progressive (non-SABR) stream available for this video on any client")
            return

        if fmt == "MP3":
            temp_video = stream.download(
                output_path=DOWNLOAD_PATH,
                filename=label + "_tmp.mp4",
                skip_existing=False,
            )
            mp3_path = os.path.join(DOWNLOAD_PATH, label + ".mp3")
            clip = AudioFileClip(temp_video)
            clip.write_audiofile(mp3_path, logger=None)
            clip.close()
            os.remove(temp_video)

        else:
            stream.download(
                output_path=DOWNLOAD_PATH,
                filename=label + ".mp4",
                skip_existing=False,
            )

        print("✅ Downloaded")

    except SABR_EXCEPTIONS as e:
        # YouTube's SABR stream-protection layer is currently a known,
        # unresolved pain point for pytubefix (ongoing as of mid-2026) —
        # it can lock out a video mid-download even after a valid PoToken.
        # Skip and move on rather than killing the whole batch.
        print(f"❌ SABR protection blocked this stream, skipping: {e}")

    except VideoUnavailable as e:
        print(f"❌ Video unavailable, skipping: {e}")

    except Exception as e:
        print("❌ Error:", e)


# ══════════════════════════════════════════════
# 🚀 PROCESS
# ══════════════════════════════════════════════

def process(url, fmt):
    print("\n📡 Processing...")

    tracks = []

    if "/track/" in url:
        t = scrape_track(url)
        if t:
            tracks = [t]

    elif "/playlist/" in url or "/album/" in url:
        tracks = scrape_playlist_browser(url)

    if not tracks:
        print("❌ No tracks found")
        return

    print(f"✅ Found {len(tracks)} tracks")

    # NOTE: max_workers is set to 1, not 3. Running downloads in parallel
    # means multiple simultaneous PoToken/session requests hit YouTube at
    # once, which looks bot-like and appears to trigger the SABR lockout
    # faster (see the download() function for details). Sequential is
    # slower but noticeably more reliable right now.
    with ThreadPoolExecutor(max_workers=1) as executor:
        for t in tracks:
            executor.submit(download, t, fmt)

    print(f"\n📁 Files saved to: {DOWNLOAD_PATH}")


# ══════════════════════════════════════════════
# 🧠 MAIN (ASK PATH ADDED)
# ══════════════════════════════════════════════

def main():
    print("\n🎧 Spotify → YouTube Downloader (V2 Final)\n")

    # 🔽 Ask user for download location
    path = input("📁 Enter download folder (leave blank for default):\n> ").strip()

    global DOWNLOAD_PATH

    if path:
        DOWNLOAD_PATH = path
    else:
        DOWNLOAD_PATH = os.path.join(os.path.expanduser("~"), "Spotify_Downloads")

    os.makedirs(DOWNLOAD_PATH, exist_ok=True)

    print(f"\n📂 Files will be saved to:\n{DOWNLOAD_PATH}\n")

    while True:
        try:
            url = input("Paste Spotify link (Ctrl+C to exit):\n> ").strip()
        except KeyboardInterrupt:
            print("\nGoodbye 👋")
            break

        if not url:
            continue

        fmt = input("Format (MP3 / MP4): ").upper()
        if fmt not in ("MP3", "MP4"):
            print("❌ Invalid format")
            continue

        process(url, fmt)


if __name__ == "__main__":
    main()
