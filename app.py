#!/usr/bin/env python3
import asyncio
import io
import logging
import os
import re
import time
from datetime import datetime
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image
from flask import Flask, jsonify, render_template, request, send_file

import edge_tts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)

APP_DIR = Path(__file__).resolve().parent
OUT_DIR = APP_DIR / "out"
OUT_DIR.mkdir(exist_ok=True)

DEFAULT_OCR_LANG = os.environ.get("IMGVOICE_OCR_LANG", "spa")
DEFAULT_VOICE = os.environ.get("IMGVOICE_VOICE", "es-CL-CatalinaNeural")
DEFAULT_RATE = os.environ.get("IMGVOICE_RATE", "+0%")
DEFAULT_VOLUME = os.environ.get("IMGVOICE_VOLUME", "+0%")
MAX_TEXT_LENGTH = int(os.environ.get("IMGVOICE_MAX_TEXT", "500"))

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 8 * 1024 * 1024

_rate_store: dict[str, list[float]] = {}
RATE_LIMIT_MAX = int(os.environ.get("IMGVOICE_RATE_LIMIT", "10"))
RATE_WINDOW = 60


def check_rate_limit(ip: str) -> bool:
    now = time.time()
    window_start = now - RATE_WINDOW
    timestamps = _rate_store.get(ip, [])
    timestamps = [t for t in timestamps if t > window_start]
    if len(timestamps) >= RATE_LIMIT_MAX:
        return False
    timestamps.append(now)
    _rate_store[ip] = timestamps
    return True


def normalize_paragraphs_ocr(text: str) -> str:
    if not text:
        return ""

    text = text.replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)

    bullet_leaders = r"(?:\+|\*|·|●|◦|▪|■|–|—)"
    text = re.sub(rf"(?m)^\s*{bullet_leaders}\s+", "• ", text)
    text = re.sub(r"(?m)^\s*[\[\(]\s*\+\s*[\]\)]\s+", "• ", text)
    text = re.sub(r"(?m)^\s*\+\s*(?=\S)", "• ", text)

    raw_lines = text.split("\n")
    paragraphs = []
    current_lines = []

    for ln in raw_lines:
        ln = ln.strip()
        if not ln:
            if current_lines:
                paragraphs.append(current_lines)
                current_lines = []
            continue
        current_lines.append(ln)

    if current_lines:
        paragraphs.append(current_lines)

    rebuilt_paragraphs = []
    for plines in paragraphs:
        merged = ""
        for line in plines:
            if not merged:
                merged = line
                continue
            if line.startswith("• "):
                merged += "\n" + line
                continue
            merged += " " + line

        merged = re.sub(r"\s{2,}", " ", merged).strip()
        rebuilt_paragraphs.append(merged)

    return "\n\n".join(rebuilt_paragraphs).strip()


def preprocess_for_ocr(pil_img: Image.Image) -> np.ndarray:
    img = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def ocr_image_bytes(image_bytes: bytes, lang: str = DEFAULT_OCR_LANG) -> str:
    pil_img = Image.open(io.BytesIO(image_bytes))
    processed = preprocess_for_ocr(pil_img)
    config = "--oem 3 --psm 6"
    raw = pytesseract.image_to_string(processed, lang=lang, config=config)
    return normalize_paragraphs_ocr(raw)


async def _tts_to_bytesio(text: str, voice: str, rate: str, volume: str) -> io.BytesIO:
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    buf = io.BytesIO()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            buf.write(chunk["data"])
    buf.seek(0)
    return buf


@lru_cache(maxsize=256)
def _tts_cache_key(text: str, voice: str, rate: str, volume: str) -> str:
    return f"{text}|{voice}|{rate}|{volume}"


_tts_cache: dict[str, bytes] = {}
MAX_CACHE_SIZE = 128


def tts_to_bytes_cached(text: str, voice: str, rate: str, volume: str) -> bytes:
    key = _tts_cache_key(text, voice, rate, volume)
    if key in _tts_cache:
        log.debug("TTS cache hit")
        return _tts_cache[key]

    loop = asyncio.new_event_loop()
    try:
        buf = loop.run_until_complete(_tts_to_bytesio(text, voice, rate, volume))
        data = buf.read()
    finally:
        loop.close()

    if len(_tts_cache) >= MAX_CACHE_SIZE:
        _tts_cache.pop(next(iter(_tts_cache)))
    _tts_cache[key] = data

    return data


@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/ocr")
def api_ocr():
    ip = request.remote_addr or "unknown"
    if not check_rate_limit(ip):
        log.warning("Rate limit OCR para %s", ip)
        return jsonify({"ok": False, "error": "Demasiadas peticiones"}), 429

    if "image" not in request.files:
        return jsonify({"ok": False, "error": "Falta archivo 'image'"}), 400

    lang = (request.form.get("lang") or DEFAULT_OCR_LANG).strip()
    f = request.files["image"]
    img_bytes = f.read()

    try:
        text = ocr_image_bytes(img_bytes, lang=lang)
        log.info("OCR ok ip=%s lang=%s len=%d", ip, lang, len(text))
        return jsonify({"ok": True, "text": text})
    except Exception as e:
        log.exception("OCR error")
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/tts")
def api_tts():
    ip = request.remote_addr or "unknown"
    if not check_rate_limit(ip):
        log.warning("Rate limit TTS para %s", ip)
        return jsonify({"ok": False, "error": "Demasiadas peticiones"}), 429

    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()[:MAX_TEXT_LENGTH]
    voice = (payload.get("voice") or DEFAULT_VOICE).strip()
    rate = (payload.get("rate") or DEFAULT_RATE).strip()
    volume = (payload.get("volume") or DEFAULT_VOLUME).strip()

    if not text:
        return jsonify({"ok": False, "error": "Texto vacio para TTS"}), 400

    try:
        mp3 = tts_to_bytes_cached(text, voice=voice, rate=rate, volume=volume)
        log.info("TTS ok ip=%s len=%d voice=%s", ip, len(text), voice)
        return send_file(
            io.BytesIO(mp3),
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="lectura.mp3",
        )
    except Exception as e:
        log.exception("TTS error")
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    host = os.environ.get("IMGVOICE_HOST", "127.0.0.1")
    port = int(os.environ.get("IMGVOICE_PORT", "5000"))
    app.run(host=host, port=port, debug=False)
