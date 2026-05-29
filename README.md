# web-imagevoice

Web application that extracts text from uploaded images using Tesseract OCR and reads it aloud as speech using Microsoft Edge TTS.

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

## API

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/ocr` | Extract text from uploaded image |
| POST | `/api/tts` | Convert text to audio MP3 |

## Features

- Image preprocessing (Gaussian blur, Otsu threshold)
- Spanish language OCR support
- Paragraph reconstruction and bullet normalization
- 8 MB upload limit

## License

MIT
