from pathlib import Path
from PIL import Image, ImageOps
import random
import subprocess
import json
import threading
import hitherdither
from datetime import date
from flask import Flask, send_file, jsonify
from palettes import inky_7color as inky_palette
from dotenv import load_dotenv
from os import getenv

env = load_dotenv()
input_dir = Path(getenv("INPUT_DIR", "input"))
output_dir = Path(getenv("OUTPUT_DIR", "output"))

VIDEO_EXTENSIONS = {'.mp4', '.avi', '.mov', '.mkv', '.flv', '.wmv', '.webm', '.mpeg', '.mpg'}

app = Flask(__name__)
latest_frame: Path | None = None
latest_original: Path | None = None
latest_frame_lock = threading.Lock()
latest_frame_info: dict | None = None


def generate_frame():
    global latest_frame, latest_original, latest_frame_info

    directories = [entry.name for entry in input_dir.iterdir() if entry.is_dir()]
    if not directories:
        print("No subdirectories found.")
        return

    directory = random.choice(directories)
    dir_path = input_dir / directory
    video_files = [f.name for f in dir_path.iterdir() if f.is_file() and f.suffix.lower() in VIDEO_EXTENSIONS]
    if not video_files:
        print(f"No video files found in {directory}.")
        return

    video_file = random.choice(video_files)
    video_path = dir_path / video_file
    print(f"Generating frame from: {video_file}")

    try:
        result = subprocess.run([
            'ffprobe',
            '-v', 'error',
            '-select_streams', 'v:0',
            '-show_entries', 'format=duration',
            '-of', 'json',
            str(video_path)
        ], capture_output=True, text=True, check=True)
        duration = float(json.loads(result.stdout)['format']['duration'])

        timestamp = random.uniform(0, duration)
        print(f"Extracting frame at {timestamp:.2f}s")

        date_dir = output_dir / date.today().isoformat()
        date_dir.mkdir(exist_ok=True)
        original_frame = date_dir / f"{video_file}_{timestamp:.2f}_original.jpg"
        subprocess.run([
            'ffmpeg', '-y',
            '-ss', str(timestamp),
            '-i', str(video_path),
            '-frames:v', '1',
            str(original_frame)
        ], check=True, capture_output=True)

        img = Image.open(original_frame)
        resized = ImageOps.fit(img, (640, 364), method=Image.LANCZOS)
        dithered = hitherdither.ordered.bayer.bayer_dithering(
            resized, inky_palette, [256/4, 256/4, 256/4], order=8
        )
        output_path = date_dir / f"{video_file}_{timestamp:.2f}_dithered.jpg"
        dithered.convert("RGB").save(output_path)

        hours, remainder = divmod(int(timestamp), 3600)
        minutes, seconds = divmod(remainder, 60)
        info = {
            "movie": directory,
            "timecode": f"{hours}:{minutes:02}:{seconds:02}",
        }
        output_path.with_suffix(".json").write_text(json.dumps(info, indent=2))

        with latest_frame_lock:
            latest_frame = output_path
            latest_original = original_frame
            latest_frame_info = info

        print(f"Frame saved: {output_path}")

    except Exception as e:
        print(f"Error generating frame: {e}")


@app.route("/frame_info")
def serve_frame_info():
    with latest_frame_lock:
        info = latest_frame_info
    if info is None:
        return "No frame info available yet.", 503
    return jsonify(info)


@app.route("/frame_original")
def serve_frame_original():
    with latest_frame_lock:
        frame = latest_original
    if frame is None or not frame.exists():
        return "No frame available yet.", 503
    return send_file(frame, mimetype="image/jpeg")


@app.route("/frame_display")
def serve_frame_display():
    with latest_frame_lock:
        info = latest_frame_info
    if info is None:
        return "No frame available yet.", 503
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Frame Display</title>
  <style>
    body {{ font-family: sans-serif; background: #111; color: #eee; margin: 2rem; }}
    h1 {{ font-size: 1.2rem; margin-bottom: 0.25rem; }}
    p {{ margin: 0 0 1rem; color: #aaa; }}
    .frames {{ display: flex; gap: 1.5rem; flex-wrap: wrap; }}
    .frames figure {{ margin: 0; }}
    .frames figcaption {{ margin-top: 0.4rem; font-size: 0.85rem; color: #aaa; }}
    img {{ display: block; max-width: 640px; border: 1px solid #333; }}
  </style>
</head>
<body>
  <h1>{info["movie"]}</h1>
  <p>{info["timecode"]}</p>
  <div class="frames">
    <figure>
      <img src="/frame_original" alt="Original">
      <figcaption>Original</figcaption>
    </figure>
    <figure>
      <img src="/frame" alt="Dithered">
      <figcaption>Dithered</figcaption>
    </figure>
  </div>
</body>
</html>"""
    return html


@app.route("/frame")
def serve_frame():
    with latest_frame_lock:
        frame = latest_frame
    if frame is None or not frame.exists():
        return "No frame available yet.", 503
    threading.Thread(target=generate_frame, daemon=True).start()
    return send_file(frame, mimetype="image/jpeg")


if __name__ == "__main__":
    output_dir.mkdir(exist_ok=True)
    print("Generating initial frame...")
    generate_frame()
    app.run(host="0.0.0.0", port=5000)
