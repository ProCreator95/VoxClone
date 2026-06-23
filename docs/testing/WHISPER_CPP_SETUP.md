# whisper.cpp Setup Guide — Ubuntu Linux (CPU-Only)

VoxClone uses **whisper.cpp** for speech recognition.
This is a pure C++ implementation: no Python ML stack, no PyTorch, no CUDA.

**Target environment:** Ubuntu Linux · 32 GB RAM · CPU only · Offline

---

## Overview

```
Step 1 — Install system dependencies
Step 2 — Build whisper.cpp from source
Step 3 — Download a GGML model
Step 4 — Configure VoxClone
Step 5 — Validate the installation
```

---

## Step 1 — Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    cmake \
    git \
    wget \
    ffmpeg
```

Verify prerequisites:

```bash
cmake --version    # need 3.14+
gcc --version      # need GCC 9+ or Clang 11+
ffmpeg -version    # need 4.x+
```

---

## Step 2 — Build whisper.cpp

Clone and build (CPU-only, no CUDA flags):

```bash
# Clone the repository
git clone https://github.com/ggerganov/whisper.cpp.git
cd whisper.cpp

# Build (replace N with your core count, e.g. make -j8 for 8 cores)
cmake -B build -DWHISPER_BUILD_TESTS=OFF -DWHISPER_BUILD_EXAMPLES=ON
cmake --build build --config Release -j$(nproc)
```

After a successful build, the binary is at:

```
whisper.cpp/build/bin/whisper-cli
```

**Install to PATH (recommended):**

```bash
sudo cp build/bin/whisper-cli /usr/local/bin/whisper-cli
sudo chmod +x /usr/local/bin/whisper-cli
```

Or add the build directory to PATH temporarily:

```bash
export PATH="$PATH:/path/to/whisper.cpp/build/bin"
```

Or set the absolute path directly in `.env`:

```bash
WHISPER_CPP_BINARY=/home/user/whisper.cpp/build/bin/whisper-cli
```

---

## Step 3 — Download a GGML Model

All commands run from inside `backend/` (the directory containing `.env`).

### Option A: Tiny (recommended for testing — fastest)

```bash
mkdir -p models
wget -O models/ggml-tiny.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin
```

**Size:** ~75 MB | **Speed:** ~5–10× real-time on modern CPU | **Accuracy:** good for clear speech

### Option B: Base (recommended for production)

```bash
mkdir -p models
wget -O models/ggml-base.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.en.bin
```

**Size:** ~142 MB | **Speed:** ~3–6× real-time | **Accuracy:** very good

### Option C: Small (highest accuracy)

```bash
mkdir -p models
wget -O models/ggml-small.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.en.bin
```

**Size:** ~466 MB | **Speed:** ~1–3× real-time | **Accuracy:** excellent

### Multilingual models (Phase 7 — Urdu, Hindi, Arabic, Persian, etc.)

Required when job `parameters.language` is a non-English code or `"auto"`.
English-only hosts using default `WHISPER_ROUTING_POLICY=english_first` do not need these.

```bash
mkdir -p models

wget -O models/ggml-tiny.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.bin

wget -O models/ggml-base.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin

wget -O models/ggml-small.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
```

| Tier | File | Size | When routed |
|------|------|------|-------------|
| tiny | `ggml-tiny.bin` | ~75 MB | `language: ur` + `whisper_model: tiny`, or `language: auto` |
| base | `ggml-base.bin` | ~142 MB | Non-English jobs; recommended minimum for Urdu |
| small | `ggml-small.bin` | ~466 MB | Higher accuracy for non-Latin scripts |

**Job examples:**

```json
{ "job_type": "subtitle_generation", "parameters": { "language": "ur", "whisper_model": "base" } }
{ "job_type": "subtitle_generation", "parameters": { "language": "auto", "whisper_model": "base" } }
```

### Offline Download (air-gapped systems)

If the machine has no internet access, download the model on another machine:

```bash
# On a machine with internet access:
wget https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin

# Transfer to the target machine:
scp ggml-tiny.en.bin user@target-host:/path/to/VoxClone/backend/models/
```

### Verify the Download

```bash
# Check file size (tiny.en should be ~75 MB)
ls -lh models/ggml-tiny.en.bin

# Quick integrity check — should print binary header info
xxd models/ggml-tiny.en.bin | head -2
```

Expected (first line starts with `00000000: 6767 6d6c` — the GGML magic bytes).

---

## Step 4 — Configure VoxClone

Edit `backend/.env`:

```bash
# Binary
WHISPER_CPP_BINARY=whisper-cli

# Model — change to ggml-base.en.bin or ggml-small.en.bin for better accuracy
WHISPER_MODEL_PATH=models/ggml-tiny.en.bin

# CPU threads — set to your physical core count
WHISPER_THREADS=4

# Language — keep "en" for the English-only .en models
WHISPER_LANGUAGE=en
```

**Thread count recommendations for 32 GB RAM:**

| CPU cores | WHISPER_THREADS |
|-----------|----------------|
| 4 cores   | 4              |
| 8 cores   | 8              |
| 16 cores  | 8 (diminishing returns) |

---

## Step 5 — Validate the Installation

Run every command from `backend/` with the virtual environment activated:

```bash
cd "/home/shz/Documents/Mustafa projects/VoxClone/backend"
source .venv/bin/activate
```

### 5.1 Verify Binary is on PATH

```bash
which whisper-cli
```

**Expected:** `/usr/local/bin/whisper-cli` (or wherever you installed it)

**If not found:**
```bash
# Check if it's in the build directory
ls -la ~/whisper.cpp/build/bin/whisper-cli
# Add to PATH or set WHISPER_CPP_BINARY=/absolute/path in .env
```

---

### 5.2 Verify Binary Version

```bash
whisper-cli --version
```

**Expected (example):**
```
whisper-cli version 1.7.x (commit abcdef...)
```

**Also test with --help:**
```bash
whisper-cli --help 2>&1 | head -20
```

Expected output starts with:
```
usage: whisper-cli [options] file0.wav file1.wav ...
```

---

### 5.3 Verify Model File Exists

```bash
ls -lh models/ggml-tiny.en.bin
```

**Expected:**
```
-rw-r--r-- 1 user group 75M Jun 13 15:00 models/ggml-tiny.en.bin
```

---

### 5.4 Verify VoxClone Can See the Configuration

```bash
python3 -c "
from app.core.config import get_settings
s = get_settings()
print('WHISPER_CPP_BINARY:', s.WHISPER_CPP_BINARY)
print('WHISPER_MODEL_PATH:', s.WHISPER_MODEL_PATH)
print('WHISPER_THREADS:   ', s.WHISPER_THREADS)
print('WHISPER_LANGUAGE:  ', repr(s.WHISPER_LANGUAGE))
"
```

**Expected:**
```
WHISPER_CPP_BINARY: whisper-cli
WHISPER_MODEL_PATH: models/ggml-tiny.en.bin
WHISPER_THREADS:    4
WHISPER_LANGUAGE:   'en'
```

---

### 5.5 Validate WhisperService (binary + model check)

```bash
python3 -c "
import asyncio
from app.services.whisper_service import WhisperService

async def check():
    svc = WhisperService()
    try:
        await svc.validate()
        print('OK — binary and model found')
    except RuntimeError as e:
        print('FAILED:', e)

asyncio.run(check())
"
```

**Expected:** `OK — binary and model found`

**If it fails:** The error message will tell you exactly what is missing and how to fix it.

---

### 5.6 End-to-End Transcription Test

Generate a short test WAV file (requires sox or ffmpeg):

```bash
# Create a 3-second silent WAV (won't produce transcript, but validates the pipeline)
ffmpeg -f lavfi -i anullsrc=r=16000:cl=mono -t 3 -ar 16000 /tmp/test_silence.wav -y

# Run whisper.cpp directly (bypassing VoxClone)
whisper-cli \
  -m models/ggml-tiny.en.bin \
  -f /tmp/test_silence.wav \
  -t 4 \
  -l en \
  --output-json \
  -of /tmp/test_output
```

**Expected:**
- Exit code 0
- `/tmp/test_output.json` created
- JSON content: `{"transcription": [], ...}` (empty — silence has no speech)

```bash
cat /tmp/test_output.json
```

---

### 5.7 Test with Real Speech

If you have a WAV file with speech:

```bash
# Convert any video/audio to the required format first
ffmpeg -i your_video.mp4 -vn -acodec pcm_s16le -ar 16000 -ac 1 /tmp/speech.wav

# Transcribe
whisper-cli \
  -m models/ggml-tiny.en.bin \
  -f /tmp/speech.wav \
  -t 4 \
  -l en \
  --output-json \
  -of /tmp/speech_output

# View result
python3 -m json.tool /tmp/speech_output.json
```

**Expected JSON structure:**
```json
{
    "systeminfo": "...",
    "model": {"type": "tiny.en", ...},
    "result": {"language": "en"},
    "transcription": [
        {
            "timestamps": {"from": "00:00:00,000", "to": "00:00:02,340"},
            "offsets": {"from": 0, "to": 2340},
            "text": " Hello, this is a test."
        }
    ]
}
```

---

### 5.8 Full API Validation

With FastAPI, Redis, and Celery running:

```bash
# Start all services (3 terminals)
redis-server --daemonize yes
uvicorn app.main:app --reload --port 8000 &
celery -A app.tasks.celery_app worker --queues media,ai --concurrency 2 --loglevel=info &

# Upload test video
MEDIA_ID=$(curl -s -X POST http://localhost:8000/api/v1/uploads \
  -F "file=@/tmp/your_test.mp4" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# Create subtitle job
JOB_ID=$(curl -s -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d "{\"media_id\":\"$MEDIA_ID\",\"job_type\":\"subtitle_generation\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

echo "Job ID: $JOB_ID"

# Poll until done
until curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID/progress" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d['status'],d.get('current_step','')); exit(0 if d['status']=='completed' else 1)" \
  2>/dev/null; do
    sleep 5
done

# Download SRT
curl -s "http://localhost:8000/api/v1/jobs/$JOB_ID/download/srt"
```

---

## Troubleshooting

### Binary not found

```
RuntimeError: whisper.cpp binary 'whisper-cli' not found on PATH.
```

**Fix:**
```bash
# Check if binary exists
ls -la ~/whisper.cpp/build/bin/

# Install to PATH
sudo cp ~/whisper.cpp/build/bin/whisper-cli /usr/local/bin/
sudo chmod +x /usr/local/bin/whisper-cli

# Or set absolute path in .env
WHISPER_CPP_BINARY=/home/user/whisper.cpp/build/bin/whisper-cli
```

---

### Model file not found

```
RuntimeError: whisper.cpp model file not found: models/ggml-tiny.en.bin
```

**Fix:**
```bash
ls -lh models/  # Check what's in the models directory

# Re-download
wget -O models/ggml-tiny.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin

# Or update the path in .env to point to where the file actually is
WHISPER_MODEL_PATH=/absolute/path/to/ggml-tiny.en.bin
```

---

### Corrupt or incomplete model

```
whisper.cpp exited with code 1
```

**Fix:** Delete and re-download the model:
```bash
rm models/ggml-tiny.en.bin
wget -O models/ggml-tiny.en.bin \
  https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-tiny.en.bin
```

---

### Audio format error

```
whisper.cpp exited with code 1
stderr: error: failed to read WAV file
```

**Fix:** Ensure the audio is 16kHz mono PCM WAV:
```bash
ffprobe -v error -show_streams /tmp/audio.wav | grep -E "sample_rate|channels|codec_name"
# Expected: codec_name=pcm_s16le, sample_rate=16000, channels=1

# Re-encode if needed:
ffmpeg -i input.wav -acodec pcm_s16le -ar 16000 -ac 1 output.wav
```

VoxClone's FFmpegService already produces this format automatically when extracting audio from video. This error should only appear if you supply a pre-existing audio file that isn't in the right format.

---

### No JSON output file produced

```
RuntimeError: whisper.cpp ran successfully (exit 0) but produced no JSON file.
```

**Fix:** Upgrade whisper.cpp to a recent version:
```bash
cd ~/whisper.cpp
git pull
cmake -B build -DWHISPER_BUILD_EXAMPLES=ON
cmake --build build --config Release -j$(nproc)
sudo cp build/bin/whisper-cli /usr/local/bin/whisper-cli
```

---

## Model Selection Guide

| Model | File | Size | Speed (CPU) | RAM Usage | When to use |
|-------|------|------|-------------|-----------|-------------|
| tiny.en | `ggml-tiny.en.bin` | 75 MB | ~10× real-time | ~300 MB | Testing, low-power hardware, English |
| base.en | `ggml-base.en.bin` | 142 MB | ~6× real-time | ~500 MB | **English default (karaoke)** |
| small.en | `ggml-small.en.bin` | 466 MB | ~3× real-time | ~1.2 GB | High English accuracy |
| base | `ggml-base.bin` | 142 MB | ~6× real-time | ~500 MB | **Multilingual (Urdu, Hindi, auto)** |
| small | `ggml-small.bin` | 466 MB | ~3× real-time | ~1.2 GB | Multilingual high accuracy |

All `.en` models are English-only. Models without `.en` are multilingual (99 languages).
VoxClone routes by `parameters.language` and `WHISPER_ROUTING_POLICY` — see Phase 7 docs.

**Change the active model:**
```bash
# In backend/.env
WHISPER_MODEL_PATH=models/ggml-base.en.bin
```

No code changes or restarts are needed beyond restarting the Celery worker.

---

## Expected Processing Times (32 GB RAM, 8-core CPU)

| Audio Length | tiny.en | base.en | small.en |
|-------------|---------|---------|---------|
| 10 seconds | 1–3 sec | 2–5 sec | 5–15 sec |
| 1 minute | 5–15 sec | 10–30 sec | 30–90 sec |
| 10 minutes | 50–120 sec | 90–240 sec | 4–10 min |
| 60 minutes | 5–12 min | 8–20 min | 20–60 min |

Actual times vary with audio clarity, background noise, and available CPU frequency.
