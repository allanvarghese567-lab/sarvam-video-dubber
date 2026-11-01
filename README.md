# Sarvam Video Dubber

CLI application to dub any video or audio (single file or entire folder) into **Malayalam** and other Indian languages using [Sarvam AI](https://www.sarvam.ai/) Dubbing API.

Supports batch processing, resume-from-failure, parallel jobs, cost estimation, and multiple target languages in one run.

## Features

- Single file or recursive folder processing
- Default target: `ml-IN` (Malayalam); add any number of languages
- Voice cloning enabled by default
- Exports video + SRT (configurable)
- Progress saved in `dubbing_state.json` — re-runs never repeat paid jobs
- Dry-run mode for cost estimation (uses `ffprobe`)
- Parallel workers with rate-limit awareness

## Requirements

- Python 3.9+
- `ffprobe` (from FFmpeg) — only needed for `--dry-run` duration/cost estimates
- Sarvam API key

```bash
# Install FFmpeg (Ubuntu/Debian)
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## Setup

```bash
git clone https://github.com/allanvarghese567-lab/sarvam-video-dubber.git
cd sarvam-video-dubber

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate

pip install -r requirements.txt

cp .env.example .env
# Edit .env and set SARVAM_API_KEY=...
export SARVAM_API_KEY="your-key"   # or load from .env with your preferred tool
```

## Usage

```bash
# Cost estimate only (no API calls)
python video_dubber.py movie.mp4 --dry-run

# Dub one file → Malayalam
python video_dubber.py movie.mp4

# Test one file from a folder
python video_dubber.py ./episodes --limit 1

# Folder + subfolders, 2 parallel workers
python video_dubber.py ./videos -r --workers 2

# Multiple target languages in one job
python video_dubber.py clip.mp4 --target ml-IN hi-IN ta-IN

# Non-English source
python video_dubber.py talk.mp4 --src-lang ta-IN

# Custom output directory and export formats
python video_dubber.py movie.mp4 --out ./output --exports video srt
```

### Arguments

| Flag | Description | Default |
|------|-------------|---------|
| `input` | Video/audio file or folder | required |
| `-r, --recursive` | Include subfolders | false |
| `--out` | Output directory | `./dubbed` |
| `--state` | Resume state file | `./dubbing_state.json` |
| `--target` | Target language code(s) | `ml-IN` |
| `--src-lang` | Source language code | `en-IN` (or `$SRC_LANG`) |
| `--exports` | Export formats | `video srt` |
| `--speakers` | Number of speakers | auto |
| `--workers` | Parallel jobs | `2` |
| `--limit` | Process only first N files | all |
| `--dry-run` | Estimate cost only | false |

## Output

Files are written to `./dubbed` (mirroring input subfolders) as:

```
<original-stem>.<lang>.<ext>
```

Example: `movie.ml.mp4`, `movie.ml.srt`

## Pricing note

The dry-run estimator uses a fixed rate of **₹40 / minute / target language** (Starter plan, `editor_flow=false`). Always verify current pricing on the [Sarvam dashboard](https://dashboard.sarvam.ai).

## License

MIT
