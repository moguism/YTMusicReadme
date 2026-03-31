import os
import base64
import requests
import colorsys
from io import BytesIO
from PIL import Image
from flask import Flask, send_file
from ytmusicapi2 import YTMusic

from constants import YT_CLIENT_CONFIG, IMAGE_FOLDER, SVG_FILENAME

app = Flask(__name__)
ytmusic = YTMusic(YT_CLIENT_CONFIG)

if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

SVG_WIDTH = 460
SVG_HEIGHT = 130


def image_to_base64(url: str) -> str | None:
    response = requests.get(url)
    if response.status_code == 200:
        return base64.b64encode(response.content).decode("utf-8")
    return None


def get_dominant_color(url: str) -> tuple[int, int, int]:
    """Extract a vibrant dominant color from album art."""
    try:
        resp = requests.get(url, timeout=5)
        img = Image.open(BytesIO(resp.content)).convert("RGB")
        img = img.resize((50, 50))
        pixels = list(img.getdata())

        best = None
        best_sat = -1
        for r, g, b in pixels:
            h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
            if s > best_sat and v > 0.3:
                best_sat = s
                best = (r, g, b)

        return best if best else (30, 215, 96)
    except Exception:
        return (30, 215, 96)


def clamp_text(text: str, max_chars: int = 28) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "…"


def rgb_to_hex(r: int, g: int, b: int) -> str:
    return f"#{r:02x}{g:02x}{b:02x}"


def darken(r: int, g: int, b: int, factor: float = 0.35) -> tuple[int, int, int]:
    return (int(r * factor), int(g * factor), int(b * factor))


def lighten(r: int, g: int, b: int, factor: float = 1.6) -> tuple[int, int, int]:
    return (min(255, int(r * factor)), min(255, int(g * factor)), min(255, int(b * factor)))


@app.route("/")
def get_latest_watch():
    last_watched = ytmusic.get_history()[0]
    title = clamp_text(last_watched["title"], 28)
    artist = (last_watched.get("artists") or [{"name": "Unknown"}])[0]["name"].split(", ")[0]
    artist = clamp_text(artist, 32)

    thumb_url = last_watched["thumbnails"][0]["url"]
    b64 = image_to_base64(thumb_url)
    if b64 is None:
        return "Error fetching thumbnail", 500

    dom = get_dominant_color(thumb_url)
    dark1 = darken(*dom, 0.18)
    dark2 = darken(*dom, 0.10)
    accent = lighten(*dom, 1.8)
    accent_hex = rgb_to_hex(*accent)
    dark1_hex = rgb_to_hex(*dark1)
    dark2_hex = rgb_to_hex(*dark2)
    dom_hex = rgb_to_hex(*dom)

    PAD = 16
    IMG = 90
    img_x, img_y = PAD, (SVG_HEIGHT - IMG) // 2

    TEXT_X = img_x + IMG + 16
    TEXT_MAX_W = SVG_WIDTH - TEXT_X - PAD

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg"
     xmlns:xlink="http://www.w3.org/1999/xlink"
     width="{SVG_WIDTH}" height="{SVG_HEIGHT}"
     viewBox="0 0 {SVG_WIDTH} {SVG_HEIGHT}">

  <defs>
    <!-- Background gradient derived from album art -->
    <linearGradient id="bgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" stop-color="{dark1_hex}"/>
      <stop offset="100%" stop-color="{dark2_hex}"/>
    </linearGradient>

    <!-- Accent gradient for bars and highlights -->
    <linearGradient id="barGrad" x1="0%" y1="0%" x2="0%" y2="100%">
      <stop offset="0%" stop-color="{accent_hex}" stop-opacity="1"/>
      <stop offset="100%" stop-color="{dom_hex}" stop-opacity="0.6"/>
    </linearGradient>

    <!-- Album art clip -->
    <clipPath id="artClip">
      <rect x="{img_x}" y="{img_y}" width="{IMG}" height="{IMG}" rx="10" ry="10"/>
    </clipPath>

    <!-- Card clip -->
    <clipPath id="cardClip">
      <rect x="0" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}" rx="16" ry="16"/>
    </clipPath>

    <!-- Soft glow filter -->
    <filter id="glow" x="-30%" y="-30%" width="160%" height="160%">
      <feGaussianBlur in="SourceGraphic" stdDeviation="8" result="blur"/>
      <feMerge>
        <feMergeNode in="blur"/>
        <feMergeNode in="SourceGraphic"/>
      </feMerge>
    </filter>

    <!-- Drop shadow for album art -->
    <filter id="artShadow" x="-15%" y="-15%" width="130%" height="130%">
      <feDropShadow dx="0" dy="4" stdDeviation="6"
                    flood-color="{dark1_hex}" flood-opacity="0.9"/>
    </filter>

    <!-- Shimmer: static gradient, the rect itself moves -->
    <linearGradient id="shimmer" x1="0%" y1="0%" x2="100%" y2="0%">
      <stop offset="0%"   stop-color="white" stop-opacity="0"/>
      <stop offset="50%"  stop-color="white" stop-opacity="0.07"/>
      <stop offset="100%" stop-color="white" stop-opacity="0"/>
    </linearGradient>
  </defs>

  <!-- Card base -->
  <g clip-path="url(#cardClip)">
    <rect width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="url(#bgGrad)"/>

    <!-- Subtle noise texture via feTurbulence would go here; using radial glow instead -->
    <radialGradient id="spotGlow" cx="30%" cy="50%" r="60%">
      <stop offset="0%" stop-color="{dom_hex}" stop-opacity="0.18"/>
      <stop offset="100%" stop-color="{dark1_hex}" stop-opacity="0"/>
    </radialGradient>
    <rect width="{SVG_WIDTH}" height="{SVG_HEIGHT}" fill="url(#spotGlow)"/>

    <!-- Shimmer overlay: rect moves smoothly across the card -->
    <rect x="-{SVG_WIDTH}" y="0" width="{SVG_WIDTH}" height="{SVG_HEIGHT}"
          fill="url(#shimmer)" clip-path="url(#cardClip)">
      <animate attributeName="x"
               from="-{SVG_WIDTH}" to="{SVG_WIDTH}"
               dur="3s" repeatCount="indefinite"/>
    </rect>

    <!-- Top edge highlight -->
    <line x1="16" y1="0.5" x2="{SVG_WIDTH - 16}" y2="0.5"
          stroke="white" stroke-opacity="0.08" stroke-width="1"/>
  </g>

  <!-- Album art shadow -->
  <rect x="{img_x}" y="{img_y}" width="{IMG}" height="{IMG}" rx="10" ry="10"
        fill="black" fill-opacity="0.5" filter="url(#artShadow)"/>

  <!-- Album art -->
  <image href="data:image/jpeg;base64,{b64}"
         x="{img_x}" y="{img_y}" width="{IMG}" height="{IMG}"
         clip-path="url(#artClip)" preserveAspectRatio="xMidYMid slice"/>

  <!-- Thin accent border on album art -->
  <rect x="{img_x}" y="{img_y}" width="{IMG}" height="{IMG}" rx="10" ry="10"
        fill="none" stroke="white" stroke-opacity="0.15" stroke-width="1"/>

  <!-- NOW PLAYING label -->
  <text x="{TEXT_X}" y="30"
        font-family="'Segoe UI', 'SF Pro Display', Helvetica, sans-serif"
        font-size="9" font-weight="600" letter-spacing="2.5"
        fill="{accent_hex}" fill-opacity="0.9">NOW PLAYING</text>

  <!-- Song title -->
  <text x="{TEXT_X}" y="56"
        font-family="'Segoe UI', 'SF Pro Display', Helvetica, sans-serif"
        font-size="17" font-weight="700" letter-spacing="-0.3"
        fill="white">{title}</text>

  <!-- Artist name -->
  <text x="{TEXT_X}" y="76"
        font-family="'Segoe UI', 'SF Pro Display', Helvetica, sans-serif"
        font-size="12" font-weight="400" letter-spacing="0.2"
        fill="white" fill-opacity="0.6">{artist}</text>

  <!-- Divider line -->
  <line x1="{TEXT_X}" y1="90" x2="{SVG_WIDTH - PAD}" y2="90"
        stroke="white" stroke-opacity="0.1" stroke-width="0.8"/>

  <!-- YouTube Music logo (text mark) -->
  <text x="{TEXT_X}" y="113"
        font-family="'Segoe UI', 'SF Pro Display', Helvetica, sans-serif"
        font-size="9" font-weight="600" letter-spacing="0.5"
        fill="white" fill-opacity="0.35">YouTube Music</text>

  <!-- Animated equalizer bars -->
  {_eq_bars(SVG_WIDTH - PAD - 36, 95, accent_hex)}
</svg>"""

    svg_path = os.path.join(IMAGE_FOLDER, SVG_FILENAME)
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(svg)

    return send_file(svg_path, mimetype="image/svg+xml")


def _eq_bars(x_start: int, y_base: int, color: str) -> str:
    """Generate 5 animated equalizer bars."""
    bars = []
    bar_w = 3
    gap = 2
    heights = [10, 16, 12, 18, 8]
    durations = ["0.8s", "0.6s", "1.0s", "0.7s", "0.9s"]
    delays = ["0s", "0.15s", "0.3s", "0.05s", "0.2s"]

    for i, (h, dur, delay) in enumerate(zip(heights, durations, delays)):
        bx = x_start + i * (bar_w + gap)
        by = y_base - h

        bars.append(f"""
  <rect x="{bx}" y="{by}" width="{bar_w}" height="{h}" rx="1.5"
        fill="url(#barGrad)">
    <animate attributeName="height"
             values="{h};{int(h * 0.3)};{h}"
             dur="{dur}" begin="{delay}"
             repeatCount="indefinite" calcMode="spline"
             keySplines="0.4 0 0.6 1; 0.4 0 0.6 1"/>
    <animate attributeName="y"
             values="{by};{y_base - int(h * 0.3)};{by}"
             dur="{dur}" begin="{delay}"
             repeatCount="indefinite" calcMode="spline"
             keySplines="0.4 0 0.6 1; 0.4 0 0.6 1"/>
  </rect>""")

    return "\n".join(bars)
