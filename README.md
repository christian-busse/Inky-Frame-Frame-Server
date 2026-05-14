# Inky Frame Frame Server

Flask server that serves randomly selected, dithered movie frames over HTTP. The dithered image uses the colors and resolution of an Inky Frame 4.0

## How it works

On startup the server generates an initial frame, then listens on port `5000`. Each request to `GET /frame` serves the latest pre-generated image and immediately kicks off generation of the next one in a background thread, so the next request is always fast.

**Frame generation pipeline:**

1. Pick a random movie folder from `input/`
2. Pick a random video file within it
3. Use `ffprobe` to get the duration, pick a random timestamp
4. Extract that frame with `ffmpeg`
5. Scale and centre-crop to **640×400** (aspect-ratio preserved, no stretching)
6. Dither to the 7-color Inky Frame palette using Bayer ordered dithering
7. Save both the original and dithered JPEG, plus a JSON sidecar, under `output/YYYY-MM-DD/`

## Requirements

### System

`ffmpeg` and `ffprobe` must be on `PATH`.

### Python

```bash
cd server
python -m venv .
pip install -r requirements.txt
```

## Running

It's best to use absolute paths in your ENV file, so the server will also work if it's started as a systemd service:

```bash
cd server
python main.py
```

## Configuration

Optional `.env` file in `server/`:

```
INPUT_DIR=input
OUTPUT_DIR=output
```

## Adding movies

One subdirectory per movie under `input/`:

```
input/
  Alien/
    alien.mkv
  Con Air/
    conair.mp4
```

Supported formats: `.mp4`, `.avi`, `.mov`, `.mkv`, `.flv`, `.wmv`, `.webm`, `.mpeg`, `.mpg`

## Endpoints

| Endpoint | Description |
|---|---|
| `GET /frame` | Serves the latest dithered JPEG. Triggers next frame generation in the background. |
| `GET /frame_original` | Serves the original (undithered, cropped) JPEG. |
| `GET /frame_info` | Returns JSON with the movie name and timecode of the current frame. |
| `GET /frame_display` | HTML page showing the original and dithered images side by side. |

### `/frame_info` response

```json
{
  "movie": "Con Air",
  "timecode": "0:22:07"
}
```

## Output structure

```
output/
  2026-05-14/
    conair.mp4_1339.16_original.jpg
    conair.mp4_1339.16_dithered.jpg
    conair.mp4_1339.16_dithered.json
```

All frames are kept indefinitely.

## Palettes

Palettes are defined in `palettes.py`. The active palette is `inky_7color` (black, white, green, blue, red, yellow, orange). Add new palettes there as named variables and import by name in `main.py`.
