Spotify → YouTube Downloader (V2 Final - pytubefix updated)
-------------------------------------------------------------
✔ No Spotify API
✔ Track scrape (fast)
✔ Playlist via Selenium (auto driver)
✔ Ask user where to save files
✔ Parallel downloads
✔ MP3 / MP4
✔ Updated to current pytubefix API (on_progress callback, get_audio_only(),
  PO Token support for YouTube's newer bot-detection requirements)

Install:
    pip install pytubefix moviepy requests beautifulsoup4 selenium
    Also requires Node.js installed on the machine (for automatic PoToken
    generation via pytubefix's bundled BotGuard script — see the WEB
    client note in download()).
