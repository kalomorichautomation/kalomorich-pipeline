# Kalomorich Productions video pipeline

Makes an original 1-hour trippy video (fractal kaleidoscope + psychedelic soundtrack), a thumbnail, title and description, then uploads it to YouTube and schedules it.

- Runs automatically Mon/Wed/Fri (see `.github/workflows/make-video.yml`); each video publishes at 5 PM New York time.
- Run it by hand: **Actions -> Make and schedule video -> Run workflow**. Untick *Upload* and set minutes to 1 for a quick test.
- Each run picks a look (Neon, Ocean, Emerald, Ember, Cosmic, Prism), segment count, key, title and thumbnail text from the date, so every upload is different.

Required repository secrets (Settings -> Secrets and variables -> Actions): `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN`.
