# Sarvam Video Dubber
# Usage:
#   docker build -t sarvam-video-dubber .
#   docker run --rm -e SARVAM_API_KEY -v "$PWD:/data" sarvam-video-dubber /data/movie.mp4 --dry-run
#   docker run --rm -e SARVAM_API_KEY -v "$PWD:/data" -v "$PWD/dubbed:/app/dubbed" \
#     sarvam-video-dubber /data/movie.mp4

FROM python:3.12-slim

# ffprobe is required for --dry-run duration/cost estimates
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY video_dubber.py .

# Default state/output live under /app; mount host dirs as needed
ENTRYPOINT ["python", "video_dubber.py"]
# Override at runtime, e.g. docker run ... image /data/clip.mp4 --target ml-IN
CMD ["--help"]
