# web-imagevoice

Web application that extracts text from uploaded images using Tesseract OCR and reads it aloud as speech using Microsoft Edge TTS.

**Security:** Debug mode disabled by default. Set `DEBUG=true` env var for development.

## Stack

Python 3, Flask, Tesseract OCR (pytesseract), Edge TTS (edge-tts)

## Installation

```bash
pip install flask pytesseract edge-tts
# Install Tesseract system package:
# sudo apt install tesseract-ocr tesseract-ocr-spa
```

## Usage

```bash
python app.py
```

Open `http://localhost:5000` in your browser.

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ocr` | Extract text from uploaded image |
| POST | `/api/tts` | Convert text to audio MP3 |

## Configuration

| Variable | Default | Description |
|---|---|---|
| `DEBUG` | `false` | Enable Flask debug mode (development only) |

## Features

- Image preprocessing (Gaussian blur, Otsu threshold)
- Spanish language OCR support
- Paragraph reconstruction and bullet normalization
- 8 MB upload limit

## Production

For production, use a WSGI server:

```bash
pip install gunicorn
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

Set `DEBUG=false` (default) and use a reverse proxy with HTTPS.

## License

MIT
