#!/usr/bin/env python3
"""
Dub any video or audio (one file or a whole folder) into Malayalam or other
Indian languages using Sarvam's Dubbing API.

Setup:
    pip install "sarvamai>=0.1.31a1" httpx
    export SARVAM_API_KEY="your-key"

Examples:
    python video_dubber.py movie.mp4 --dry-run              # cost estimate only
    python video_dubber.py movie.mp4                        # one file -> Malayalam
    python video_dubber.py ./episodes --limit 1             # test one file from a folder
    python video_dubber.py ./videos -r --workers 2          # folder + subfolders
    python video_dubber.py clip.mp4 --target ml-IN hi-IN    # several languages, one job
    python video_dubber.py talk.mp4 --src-lang ta-IN        # non-English source

Outputs go to ./dubbed (mirroring subfolders) as <name>.<lang>.<ext>.
Progress is saved in dubbing_state.json so re-running never repeats paid jobs.
"""
import argparse
import json
import os
import shutil
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import httpx
from sarvamai import SarvamAI

MEDIA_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".wmv",
             ".wav", ".mp3", ".m4a"}
FALLBACK_EXT = {"video": ".mp4", "srt": ".srt", "vtt": ".vtt", "audio": ".wav"}
TERMINAL = {"completed", "partial_failure", "failed", "deleted"}
RATE_INR_PER_MIN = 40  # Starter plan, editor_flow=false, per target language (check pricing)
POLL_SECONDS = 15
MAX_WAIT = 3600  # seconds per phase

_lock = threading.Lock()


# ---------- state (resume support) ----------
def load_state(path: Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def update_state(state: dict, path: Path, key: str, **fields) -> None:
    with _lock:
        state.setdefault(key, {}).update(fields)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, indent=2, ensure_ascii=False))
        tmp.replace(path)


# ---------- helpers ----------
def duration_minutes(p: Path):
    if not shutil.which("ffprobe"):
        return None
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=nw=1:nk=1", str(p)],
        capture_output=True, text=True,
    )
    try:
        return float(out.stdout.strip()) / 60
    except ValueError:
        return None


def download(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    with httpx.stream("GET", url, follow_redirects=True, timeout=None) as r:
        r.raise_for_status()
        with open(tmp, "wb") as f:
            for chunk in r.iter_bytes():
                f.write(chunk)
    tmp.replace(dest)


def collect_files(src: Path, recursive: bool):
    if src.is_file():
        return [src], src.parent
    pattern = src.rglob("*") if recursive else src.iterdir()
    files = sorted(p for p in pattern if p.is_file() and p.suffix.lower() in MEDIA_EXT)
    return files, src


# ---------- one file ----------
def dub_one(client, media: Path, root: Path, out_dir: Path, state: dict, state_path: Path,
            src_lang: str, targets: list, exports: list, num_speakers):
    rel = media.relative_to(root)
    key = f"{rel}|{','.join(targets)}"
    entry = state.get(key, {})
    if entry.get("done"):
        return str(rel), "skipped (already done)"

    job_id = entry.get("job_id")
    if not job_id:
        kwargs = dict(
            source_language_code=src_lang,
            target_language_codes=targets,
            export_options=exports,
            voice_cloning=True,
            job_name=media.name,
        )
        if num_speakers:
            kwargs["num_speakers"] = num_speakers
        created = client.dubbing.create(**kwargs)
        job_id = created.data.job_id
        client.dubbing.upload(created.data.upload_url, media)
        client.dubbing.start(job_id=job_id)
        # Saved only after start succeeds, so a crash earlier never reuses a dead job.
        update_state(state, state_path, key, job_id=job_id, done=False)

    # Phase 1: wait for the dub itself
    deadline = time.monotonic() + MAX_WAIT
    while True:
        try:
            job = client.dubbing.get_live_status(job_id=job_id).data
        except httpx.TransportError:
            time.sleep(POLL_SECONDS)
            continue
        print(f"[{rel}] {job.progress:>3}%  {job.current_step_label}", flush=True)
        if job.status in TERMINAL:
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"{rel}: job {job_id} did not finish in time")
        time.sleep(POLL_SECONDS)

    if job.status in {"failed", "deleted"}:
        raise RuntimeError(f"{rel}: {job.error_message or job.status} (job {job_id})")

    # Phase 2: wait for exported files (one per language x format)
    wanted = {(lang, fmt) for lang in targets for fmt in exports}
    deadline = time.monotonic() + MAX_WAIT
    while True:
        try:
            result = client.dubbing.get_export_status(job_id=job_id, limit=100).data.exports or []
        except httpx.TransportError:
            time.sleep(POLL_SECONDS)
            continue
        settled = {(e.target_language, e.export_type) for e in result
                   if e.status in {"completed", "failed"}}
        if wanted <= settled:
            break
        if time.monotonic() > deadline:
            raise TimeoutError(f"{rel}: exports for job {job_id} did not settle in time")
        time.sleep(POLL_SECONDS)

    ready = {
        (e.target_language, e.export_type): e.download_url
        for e in result
        if e.status == "completed" and not e.is_stale and getattr(e, "download_url", None)
    }
    missing = wanted - set(ready)
    if missing:
        raise RuntimeError(f"{rel}: exports missing {sorted(missing)} (job {job_id})")

    for (lang, fmt), url in ready.items():
        ext = Path(urlparse(url).path).suffix or FALLBACK_EXT.get(fmt, ".bin")
        short = lang.split("-")[0]
        download(url, out_dir / rel.parent / f"{media.stem}.{short}{ext}")

    update_state(state, state_path, key, done=True)
    return str(rel), "done"


# ---------- main ----------
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", type=Path, help="a video/audio file or a folder of them")
    ap.add_argument("-r", "--recursive", action="store_true", help="include subfolders")
    ap.add_argument("--out", type=Path, default=Path("dubbed"))
    ap.add_argument("--state", type=Path, default=Path("dubbing_state.json"))
    ap.add_argument("--target", nargs="+", default=["ml-IN"], help="target language code(s), default ml-IN")
    ap.add_argument("--src-lang", default=os.environ.get("SRC_LANG", "en-IN"),
                    help="source language code (see Sarvam's language-codes page)")
    ap.add_argument("--exports", nargs="+", default=["video", "srt"],
                    help="export formats; for audio-only inputs check Sarvam's export-formats page")
    ap.add_argument("--speakers", type=int, default=0, help="number of speakers (omit to let Sarvam decide)")
    ap.add_argument("--workers", type=int, default=2, help="parallel jobs (mind your rate limits)")
    ap.add_argument("--limit", type=int, default=0, help="only process the first N files")
    ap.add_argument("--dry-run", action="store_true", help="list files and estimate cost, spend nothing")
    args = ap.parse_args()

    if not args.input.exists():
        raise SystemExit(f"Not found: {args.input}")
    files, root = collect_files(args.input, args.recursive)
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit("No supported video/audio files found.")

    if args.dry_run:
        total = 0.0
        for p in files:
            m = duration_minutes(p)
            total += m or 0
            print(f"{p.name}  {f'{m:.1f} min' if m else 'duration unknown (install ffprobe)'}")
        cost = total * RATE_INR_PER_MIN * len(args.target)
        print(f"\n{len(files)} files, ~{total:.0f} min, {len(args.target)} language(s), "
              f"est. cost ~Rs {cost:,.0f}")
        return

    args.out.mkdir(parents=True, exist_ok=True)
    client = SarvamAI(api_subscription_key=os.environ["SARVAM_API_KEY"])
    state = load_state(args.state)

    failures = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {
            pool.submit(dub_one, client, p, root, args.out, state, args.state,
                        args.src_lang, args.target, args.exports, args.speakers or None): p
            for p in files
        }
        for fut in as_completed(futures):
            p = futures[fut]
            try:
                name, status = fut.result()
                print(f"[{name}] {status}", flush=True)
            except Exception as e:  # keep the batch going; re-run to retry failures
                failures.append((p.name, str(e)))
                print(f"[{p.name}] FAILED: {e}", flush=True)

    print(f"\nFinished. {len(files) - len(failures)} ok, {len(failures)} failed.")
    for name, err in failures:
        print(f"  - {name}: {err}")


if __name__ == "__main__":
    main()
