# Sarvam Video Dubber

[![CI](https://github.com/allanvarghese567-lab/sarvam-video-dubber/actions/workflows/ci.yml/badge.svg)](https://github.com/allanvarghese567-lab/sarvam-video-dubber/actions/workflows/ci.yml)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

CLI tool to dub any video or audio — one file or a whole folder — into **Malayalam** and other Indian languages using the [Sarvam AI](https://www.sarvam.ai/) Dubbing API.

Batch-friendly, resumable, parallel, with cost estimation before you spend.

## Features

- Single file or recursive folder processing
- Default target: `ml-IN` (Malayalam); any number of languages per job
- Voice cloning enabled by default
- Exports video + SRT (configurable)
- Resume via `dubbing_state.json` — re-runs never repeat paid jobs
- Dry-run mode for duration + cost estimate (`ffprobe`)
- Parallel workers with rate-limit awareness
- Docker image with FFmpeg included

## Requirements

| Item | Notes |
|------|--------|
| Python 3.10+ | Tested on 3.10–3.12 |
| Sarvam API key | [dashboard.sarvam.ai](https://dashboard.sarvam.ai) |
| FFmpeg / `ffprobe` | Only needed for `--dry-run` (optional otherwise) |

```bash
# Ubuntu / Debian
sudo apt install ffmpeg

# macOS
brew install ffmpeg
```

## Quick start

```bash
git clone https://github.com/allanvarghese567-lab/sarvam-video-dubber.git
cd sarvam-video-dubber

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env
# Set SARVAM_API_KEY in .env, then:
export SARVAM_API_KEY="your-key"

# Estimate cost (no API spend)
python video_dubber.py movie.mp4 --dry-run

# Dub to Malayalam
python video_dubber.py movie.mp4
```

## Usage

```bash
# One file → Malayalam
python video_dubber.py movie.mp4

# Test a single file from a folder
python video_dubber.py ./episodes --limit 1

# Folder + subfolders, 2 workers
python video_dubber.py ./videos -r --workers 2

# Multiple target languages in one job
python video_dubber.py clip.mp4 --target ml-IN hi-IN ta-IN

# Non-English source
python video_dubber.py talk.mp4 --src-lang ta-IN

# Custom output + export formats
python video_dubber.py movie.mp4 --out ./output --exports video srt
```

### Arguments

| Flag | Description | Default |
|------|-------------|---------|
| `input` | Video/audio file or folder | *required* |
| `-r, --recursive` | Include subfolders | `false` |
| `--out` | Output directory | `./dubbed` |
| `--state` | Resume state file | `./dubbing_state.json` |
| `--target` | Target language code(s) | `ml-IN` |
| `--src-lang` | Source language code | `en-IN` (or `$SRC_LANG`) |
| `--exports` | Export formats | `video srt` |
| `--speakers` | Number of speakers | auto |
| `--workers` | Parallel jobs | `2` |
| `--limit` | Process only first N files | all |
| `--dry-run` | Estimate cost only (no API calls) | `false` |

## Docker

```bash
docker build -t sarvam-video-dubber .

# Cost estimate
docker run --rm -e SARVAM_API_KEY -v "$PWD:/data" \
  sarvam-video-dubber /data/movie.mp4 --dry-run

# Dub and write results to host ./dubbed
docker run --rm -e SARVAM_API_KEY \
  -v "$PWD:/data" \
  -v "$PWD/dubbed:/app/dubbed" \
  -v "$PWD/dubbing_state.json:/app/dubbing_state.json" \
  sarvam-video-dubber /data/movie.mp4

# Folder + multiple languages
docker run --rm -e SARVAM_API_KEY \
  -v "$PWD:/data" \
  -v "$PWD/dubbed:/app/dubbed" \
  sarvam-video-dubber /data/episodes -r --target ml-IN hi-IN --workers 2
```

The image includes `ffmpeg`/`ffprobe` and all Python dependencies. Pass any CLI flags after the image name.

## Output

Files land in `./dubbed` (mirroring input subfolders):

```
<original-stem>.<lang>.<ext>
```

Examples: `movie.ml.mp4`, `movie.ml.srt`, `episode01.hi.mp4`

## Pricing note

The dry-run estimator uses **₹40 / minute / target language** (Starter plan, `editor_flow=false`). Always confirm current rates on the [Sarvam dashboard](https://dashboard.sarvam.ai).

## Project layout

```
sarvam-video-dubber/
├── video_dubber.py      # CLI entrypoint
├── requirements.txt
├── Dockerfile
├── ruff.toml
├── .env.example
├── .github/workflows/ci.yml
└── README.md
```

## CI

GitHub Actions runs on every push and PR to `main`:

- Ruff lint + `py_compile` + import smoke test on Python 3.10–3.12
- CLI `--help` and error-path checks
- Docker image build and `--help` smoke test

## License

MIT
