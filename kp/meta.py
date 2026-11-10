"""Title, description, tags and thumbnail text for each video, rotated by seed.
Titles follow the pattern that ranks in this niche and stay under YouTube's 60-character desktop cut."""

TITLES = [
    "Trippy {pal} Mandala | 1 Hour Psychedelic Visuals & Music",
    "{pal} Fractal Kaleidoscope | 1 Hour Trippy Visuals",
    "Psychedelic {pal} Mandala Trip | 1 Hour Trippy Visuals",
    "1 Hour Trippy {pal} Kaleidoscope | Psychedelic Music",
    "Hypnotic {pal} Fractals | 1 Hour Trippy Kaleidoscope",
]

THUMB_TEXT = ["LOOK CLOSER", "DON'T BLINK", "ENTER", "GO DEEPER", "FALL IN", None]

DESCRIPTION = """1 hour of trippy kaleidoscope visuals and psychedelic music. A {pal_l} fractal mandala that never stops shifting, with an original psy soundtrack built to match. Headphones recommended.

Perfect as a background screen, for a party, for zoning out, or just to get lost in.

All visuals and music are original, created by Kalomorich Productions.

New trippy visuals and ambient videos every week. Subscribe to keep the journey going.

#trippy #psychedelic #kaleidoscope"""

TAGS = ["trippy visuals", "psychedelic visuals", "kaleidoscope", "fractal mandala", "trippy video 1 hour",
        "psychedelic music", "visualizer", "mandala visuals", "screensaver", "background visuals"]


def for_video(seed, palette):
    title = TITLES[seed % len(TITLES)].format(pal=palette)
    assert len(title) <= 60, title
    return {
        "title": title,
        "description": DESCRIPTION.format(pal_l=palette.lower()),
        "tags": TAGS + [f"{palette.lower()} kaleidoscope"],
        "thumb_text": THUMB_TEXT[seed % len(THUMB_TEXT)],   # 5 titles x 6 texts x 6 looks rotate independently
    }
