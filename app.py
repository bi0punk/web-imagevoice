#!/usr/bin/env python3
import asyncio
import io
import os
import re
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np
import pytesseract
from PIL import Image
from flask import Flask, jsonify, render_template, request, send_file

import edge_tts

APP_DIR = Path(__file__).resolve().parent
OUT_DIR = APP_DIR / "out"
OUT_DIR.mkdir(exist_ok=True)

DEFAULT_OCR_LANG = "spa"
DEFAULT_VOICE = "es-CL-CatalinaNeural"  # alternativa: es-ES-ElviraNeural
DEFAULT_RATE = "+0%"
DEFAULT_VOLUME = "+0%"

app = Flask(__name__)


# -----------------------------
# Helpers
# -----------------------------
def clean_text(text: str) -> str:
    text = (text or "").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def preprocess_for_ocr(pil_img: Image.Image) -> np.ndarray:
    """
    Preproceso básico para OCR (mejora mucho en fotos reales):
    - RGB -> Gray
    - Blur suave
    - Otsu threshold
    """
    img = np.array(pil_img.convert("RGB"))
    gray = cv2.cvtColor(img, cv2.COLOR_RGB2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    _, th = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return th


def ocr_image_bytes(image_bytes: bytes, lang: str) -> str:
    pil_img = Image.open(io.BytesIO(image_bytes))
    processed = preprocess_for_ocr(pil_img)
    config = "--oem 3 --psm 6"
    txt = pytesseract.image_to_string(processed, lang=lang, config=config)
    return clean_text(txt)


async def tts_to_mp3(text: str, voice: str, rate: str, volume: str, out_path: str):
    communicate = edge_tts.Communicate(text=text, voice=voice, rate=rate, volume=volume)
    await communicate.save(out_path)


def generate_mp3_bytes(text: str, voice: str, rate: str, volume: str) -> bytes:
    text = clean_text(text)
    if not text:
        raise ValueError("Texto vacío para TTS")

    # nombre único (evita colisiones concurrentes simples)
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    mp3_path = OUT_DIR / f"tts_{ts}.mp3"

    asyncio.run(tts_to_mp3(text, voice, rate, volume, str(mp3_path)))
    data = mp3_path.read_bytes()

    # limpieza best-effort (en prod mejor usar TTL/cron o storage)
    try:
        mp3_path.unlink(missing_ok=True)
    except Exception:
        pass

    return data


# -----------------------------
# Routes
# -----------------------------
@app.get("/")
def index():
    return render_template("index.html")


@app.post("/api/ocr")
def api_ocr():
    if "image" not in request.files:
        return jsonify({"ok": False, "error": "Falta archivo 'image'"}), 400

    lang = request.form.get("lang", DEFAULT_OCR_LANG).strip() or DEFAULT_OCR_LANG
    f = request.files["image"]
    img_bytes = f.read()

    try:
        text = ocr_image_bytes(img_bytes, lang=lang)
        return jsonify({"ok": True, "text": text})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.post("/api/tts")
def api_tts():
    payload = request.get_json(silent=True) or {}
    text = payload.get("text", "")
    voice = (payload.get("voice") or DEFAULT_VOICE).strip()
    rate = (payload.get("rate") or DEFAULT_RATE).strip()
    volume = (payload.get("volume") or DEFAULT_VOLUME).strip()

    try:
        mp3 = generate_mp3_bytes(text, voice=voice, rate=rate, volume=volume)
        return send_file(
            io.BytesIO(mp3),
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="lectura.mp3",
        )
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


if __name__ == "__main__":
    # Dev server (producción: gunicorn)
    app.run(host="0.0.0.0", port=5000, debug=True)
