"""Thumbnail: a high-contrast frame from the video with short glowing text (or none)."""
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

GLOW = {"Neon": (255, 60, 200), "Ocean": (0, 220, 255), "Emerald": (90, 255, 160),
        "Ember": (255, 150, 40), "Cosmic": (170, 120, 255), "Prism": (255, 200, 90)}


def make(frame_png, out_jpg, text, palette, font_path):
    im = Image.open(frame_png).convert("RGB").crop((240, 135, 1680, 945)).resize((1280, 720), Image.LANCZOS)
    a = (np.asarray(im) / 255.0) ** 1.4
    im = Image.fromarray((a * 255).astype(np.uint8))
    im = ImageEnhance.Color(ImageEnhance.Contrast(im).enhance(1.3)).enhance(1.3).convert("RGBA")
    y, x = np.mgrid[0:720, 0:1280]
    d = np.sqrt(((x - 640) / 640) ** 2 + ((y - 360) / 360) ** 2)
    vg = (np.clip((d - 0.5) / 0.75, 0, 1) ** 1.5 * 255 * 0.6).astype(np.uint8)
    dk = Image.new("RGBA", im.size, (4, 0, 14, 255)); dk.putalpha(Image.fromarray(vg, "L")); im.alpha_composite(dk)
    if text:
        words = text.split()
        lines = [" ".join(words[: (len(words) + 1) // 2]), " ".join(words[(len(words) + 1) // 2:])] if len(words) > 1 else words
        shade = np.clip(1 - np.arange(1280) / 650, 0, 1) ** 1.2
        m = Image.fromarray(np.tile((shade * 210).astype(np.uint8), (720, 1)), "L")
        dk = Image.new("RGBA", im.size, (2, 2, 20, 255)); dk.putalpha(m); im.alpha_composite(dk)
        g = Image.new("RGBA", im.size, (0, 0, 0, 0)); gd = ImageDraw.Draw(g)
        f = ImageFont.truetype(font_path, 170 if max(len(s) for s in lines) <= 6 else 140)
        ys = [290, 450] if len(lines) == 2 else [370]
        for s, yy in zip(lines, ys):
            gd.text((55, yy), s, font=f, fill=GLOW.get(palette, (255, 90, 200)) + (255,), anchor="lm")
        g = g.filter(ImageFilter.GaussianBlur(14)); im.alpha_composite(g); im.alpha_composite(g)
        d = ImageDraw.Draw(im)
        for s, yy in zip(lines, ys):
            d.text((55, yy), s, font=f, fill=(255, 247, 225, 255), anchor="lm", stroke_width=5, stroke_fill=(20, 0, 35, 255))
    im.convert("RGB").save(out_jpg, quality=92)
    return out_jpg
