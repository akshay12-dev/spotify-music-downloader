"""
Spotify → YouTube Downloader (V2 Final)
---------------------------------------
✔ No Spotify API
✔ Track scrape (fast)
✔ Playlist via Selenium (auto driver)
✔ Ask user where to save files
✔ Parallel downloads
✔ MP3 / MP4

Install:
    pip install pytubefix moviepy requests beautifulsoup4 selenium
"""

import os, re, shutil, json, requests, time
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
from pytubefix import YouTube, Search
from moviepy import VideoFileClip, AudioFileClip

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
# ⬇ DOWNLOAD
# ══════════════════════════════════════════════

def sanitize(name):
    return re.sub(r'[\\/:*?"<>|]', '', name)


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
        yt = YouTube(yt_url)

        if fmt == "MP3":
            stream = yt.streams.filter(only_audio=True).first()
            temp = stream.download(DOWNLOAD_PATH, filename=label + "_tmp")
            shutil.move(temp, os.path.join(DOWNLOAD_PATH, label + ".mp3"))

        else:
            stream = yt.streams.get_highest_resolution()
            stream.download(DOWNLOAD_PATH, filename=label + ".mp4")

        print("✅ Downloaded")

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

    with ThreadPoolExecutor(max_workers=3) as executor:
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
