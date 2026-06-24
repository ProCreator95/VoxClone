# Phase 8 — Voice Cloning Feasibility Study

**Date:** 2026-06-23  
**Branch:** `feature/whisper-multilingual`  
**Authoritative context:** `docs/context/PROJECT_SNAPSHOT_2026_06_22.md`  
**Scope:** Documentation and analysis only — **no packages installed, no engine implemented, no application code modified**

---

## Executive Summary

Phase 8 evaluates open-source voice cloning engines for future integration into VoxClone. **Voice cloning is not part of the MVP launch** (Phases 9–12 precede production voice features in the commercial roadmap). This study informs a **future proof-of-concept** and **Phase 12 Hetzner GPU planning** — not immediate implementation.

**Key finding:** All serious zero-shot voice cloning engines require **GPU inference** for acceptable latency. The planned **4 vCPU / 8 GB CPU-only Hetzner MVP** (Phase 12 launch target) can run Whisper, Demucs, and DeepFilterNet, but **cannot** host production-grade neural voice cloning alongside existing workloads.

**Commercial license disqualifiers:**

| Engine | Blocker |
|--------|---------|
| **Coqui XTTS-v2** | CPML — non-commercial only; no commercial license issuer after Coqui shutdown |
| **F5-TTS** (pretrained checkpoints) | CC-BY-NC-4.0 on weights (Emilia dataset) |
| **Fish Speech S2** | Custom Fish Audio Research License — not standard permissive OSS |

**Recommended path for VoxClone:**

| Decision | Recommendation |
|----------|----------------|
| **Best overall fit** | **Chatterbox Multilingual V3** (MIT, active, pip-installable, 23+ languages) |
| **Easiest PoC integration** | **Chatterbox-Turbo** (English MVP) or **Chatterbox Multilingual V3** |
| **Best commercial-safe quality** | **Chatterbox Multilingual V3** or **CosyVoice 3** (Apache 2.0) |
| **Prior roadmap alignment** | **OpenVoice V2** (MIT, already referenced in project docs) |
| **PoC engine** | **Chatterbox-Turbo** for English-first MVP alignment; evaluate **OpenVoice V2** in parallel |

**Integration pattern:** Follow Phase 6 isolation policy — separate Python environment or subprocess wrapper; do **not** merge torch stacks with pinned Demucs `requirements-ml.txt` without full regression validation.

---

## 1. Study Context

### 1.1 VoxClone constraints (locked)

| Constraint | Implication for voice cloning |
|------------|------------------------------|
| MVP excludes voice cloning | Phase 8 is feasibility only |
| Hetzner deferred to **Phase 12** | No production GPU until deployment phase |
| Flutter deferred to **Phase 9** | API design for cloning can wait |
| CPU-first cost control | Cloning is a **GPU-tier premium feature** |
| Architecture unchanged | FastAPI + Redis + Celery + SQLite + subprocess ML |
| Demucs torch pins (`2.8.0+cpu`) | Voice engine needs **isolated worker env** |
| DeepFilterNet CLI isolation precedent | Prefer subprocess or separate venv over shared deps |

### 1.2 Evaluation criteria

Each engine scored against:

1. Commercial launch readiness (license clarity)  
2. Hetzner hosting cost (RAM, GPU, disk)  
3. Operational simplicity (install, upgrades, subprocess fit)  
4. Revenue generation potential (premium tier candidate)  
5. User value (English cloning quality, dubbing pipeline fit)

### 1.3 VoxClone integration target (future)

```
POST /jobs { job_type: "voice_clone", parameters: { reference_audio, text, language } }
  → Celery voice_clone_task (ai queue)
  → VoiceCloningService (subprocess or isolated Python worker)
  → processed/<job_id>_cloned.wav
  → GET /jobs/{id}/download/cloned (future)
```

Retention: cloned outputs subject to configurable retention policy (default 10 days — see project snapshot).

---

## 2. Engine Profiles

### 2.1 Coqui XTTS-v2

| Attribute | Assessment |
|-----------|------------|
| **Project maturity** | High historical adoption (~45k GitHub stars on Coqui TTS); **Coqui Inc. shut down Jan 2024**; community fork `idiap/coqui-ai-TTS` maintains code |
| **License** | **CPML (Coqui Public Model License)** on model weights — **non-commercial only**; source code MPL-2.0 |
| **Commercial suitability** | **Not suitable** — no entity sells commercial licenses post-shutdown |
| **Linux compatibility** | Good (Ubuntu widely documented) |
| **CPU-only support** | Theoretically yes (`gpu=False`); impractically slow for production |
| **GPU requirements** | **Recommended** — docs default `gpu=True`, DeepSpeed optional |
| **RAM requirements** | ~4–8 GB+ VRAM typical; ~2–4 GB system RAM |
| **Inference speed** | Moderate on GPU (~3× RTF cited vs F5-TTS on RTX 4090); slow on CPU |
| **Voice cloning quality** | Strong multilingual zero-shot; 6–10 s reference |
| **Multi-speaker** | Yes (reference-driven zero-shot) |
| **English support** | Yes (17 languages official) |
| **Urdu support** | Community fine-tunes exist; not in official XTTS language list |
| **Deployment complexity** | Medium — Python package, large model download (~1.8 GB+) |
| **VoxClone integration** | Medium — Python API or CLI wrapper; **license blocks commercial VoxClone** |
| **Async Celery fit** | Good (long-running GPU job) |
| **Hetzner suitability** | Requires **GPU VPS** at Phase 12; not viable on 4 vCPU / 8 GB CPU |
| **Hosting impact** | +GPU instance cost; separate worker pool |
| **Community / maintenance** | **Declining** — original vendor gone; fork maintenance only |

**Verdict:** **Disqualified for commercial VoxClone.** Useful reference only.

---

### 2.2 OpenVoice V2 (MyShell / MIT)

| Attribute | Assessment |
|-----------|------------|
| **Project maturity** | High — ~37k GitHub stars; production use at MyShell since 2023; V2 released Apr 2024 |
| **License** | **MIT** — explicit free commercial use (V1 and V2) |
| **Commercial suitability** | **Excellent** |
| **Linux compatibility** | Good (Ubuntu) |
| **CPU-only support** | Possible but slow; PyTorch inference |
| **GPU requirements** | **Strongly recommended** for acceptable latency |
| **RAM requirements** | ~4–6 GB VRAM estimated; moderate system RAM |
| **Inference speed** | Moderate (~4× RTF vs F5 on RTX 4090 per third-party comparisons) |
| **Voice cloning quality** | Strong tone-color cloning; **does not clone accent/emotion** (by design — see project QA) |
| **Multi-speaker** | Reference-driven single speaker per run |
| **English support** | Native (V2 languages: EN, ES, FR, ZH, JA, KO) |
| **Urdu support** | **Not native** — requires custom base speaker TTS model for Urdu (Phase 13 concern) |
| **Deployment complexity** | Medium-high — multi-stage pipeline (base speaker + tone converter); MeloTTS dependency |
| **VoxClone integration** | Medium — Python scripts; fits Celery task; **already in VoxClone roadmap docs** |
| **Async Celery fit** | Good |
| **Hetzner suitability** | GPU VPS at Phase 12; not on CPU-only 8 GB with Demucs concurrent |
| **Hosting impact** | Moderate GPU VRAM; lighter than CosyVoice/Fish S2 |
| **Community / maintenance** | Active issues/PRs; MIT institution backing |

**Verdict:** **Strong commercial candidate.** Best **roadmap continuity** choice. Urdu requires extra base-speaker work (Phase 13).

---

### 2.3 F5-TTS (SWivid)

| Attribute | Assessment |
|-----------|------------|
| **Project maturity** | High — ~15k stars; active 2024–2026 development |
| **License** | Code **MIT**; pretrained checkpoints **CC-BY-NC-4.0** (Emilia dataset) |
| **Commercial suitability** | **Pretrained weights not suitable**; commercial path requires training on permissive data |
| **Linux compatibility** | Good |
| **CPU-only support** | Poor for production |
| **GPU requirements** | **Required** for practical use |
| **RAM requirements** | ~6–8 GB VRAM |
| **Inference speed** | Fast on GPU (~5× RTF on RTX 4090 cited) |
| **Voice cloning quality** | Excellent zero-shot (5–15 s reference) |
| **Multi-speaker** | Reference-driven |
| **English support** | Yes (EN, ZH base; community ports) |
| **Urdu support** | Not documented |
| **Deployment complexity** | Medium — `pip install f5-tts`; Python 3.10 |
| **VoxClone integration** | Medium — CLI `f5-tts_infer-cli` suitable for subprocess pattern |
| **Async Celery fit** | Good |
| **Hetzner suitability** | GPU VPS only |
| **Community / maintenance** | **Active** |

**Verdict:** **Disqualified for commercial use of pretrained weights.** Revisit only if VoxClone trains custom commercial-safe checkpoints.

---

### 2.4 CosyVoice / Fun-CosyVoice 3 (FunAudioLLM)

| Attribute | Assessment |
|-----------|------------|
| **Project maturity** | Very high — ~22k stars; CosyVoice 1→2→3 roadmap through 2025 |
| **License** | **Apache 2.0** (code and published models) |
| **Commercial suitability** | **Excellent** |
| **Linux compatibility** | Good; Docker deployment documented |
| **CPU-only support** | Not practical for production |
| **GPU requirements** | **Required** — Docker examples use `--runtime=nvidia`; TRT-LLM / vLLM acceleration |
| **RAM requirements** | 0.5B models ~4–8 GB VRAM; larger variants more |
| **Inference speed** | Streaming latency ~150 ms with GPU optimization; heavy without TRT |
| **Voice cloning quality** | State-of-the-art open-source tier (CosyVoice 3 benchmarks) |
| **Multi-speaker** | Zero-shot + cross-lingual cloning |
| **English support** | Yes (9+ languages in v3) |
| **Urdu support** | **Not in primary language list**; cross-lingual may partially work |
| **Deployment complexity** | **High** — conda env, submodules, optional vLLM/TRT, large model downloads |
| **VoxClone integration** | Hard — FastAPI/gRPC server pattern; heavy deps conflict with Demucs pins |
| **Async Celery fit** | Good via sidecar service |
| **Hetzner suitability** | **GPU VPS 8 vCPU / 16 GB+** recommended |
| **Hosting impact** | **High** — separate GPU worker or dedicated inference service |
| **Community / maintenance** | **Very active** (Alibaba/FunAudioLLM ecosystem) |

**Verdict:** **Best quality among Apache-licensed options.** High ops cost — defer until post-revenue GPU investment.

---

### 2.5 Chatterbox (Resemble AI)

| Attribute | Assessment |
|-----------|------------|
| **Project maturity** | Very high — ~25k stars; Turbo (2025), Multilingual V3 (2026) |
| **License** | **MIT** |
| **Commercial suitability** | **Excellent** |
| **Linux compatibility** | Debian 11+ documented; Ubuntu compatible |
| **CPU-only support** | Documented (`device="cpu"`) — slow; Turbo optimized for low VRAM GPU |
| **GPU requirements** | **Recommended** — Turbo targets low compute; V3 500M params |
| **RAM requirements** | Turbo ~350M: **lower VRAM** than CosyVoice; ~4 GB VRAM minimum practical |
| **Inference speed** | Turbo: optimized for voice agents (sub-200 ms latency cited for hosted service); fast local GPU |
| **Voice cloning quality** | Competitive with commercial APIs (Resemble benchmarks vs ElevenLabs) |
| **Multi-speaker** | Reference clip cloning (`audio_prompt_path`) |
| **English support** | Turbo (English-focused); Multilingual V3 (23+ languages) |
| **Urdu support** | **Not listed** in V3 language table (supports Arabic, Hindi — not Ur) |
| **Deployment complexity** | **Low** — `pip install chatterbox-tts` |
| **VoxClone integration** | **Easiest** — Python API or thin subprocess wrapper |
| **Async Celery fit** | Excellent |
| **Hetzner suitability** | **Best fit** among candidates for future GPU VPS (Turbo = lower VRAM) |
| **Hosting impact** | Moderate — smallest practical GPU footprint of top tier |
| **Community / maintenance** | **Very active**; Discord; built-in Perth watermarking |

**Verdict:** **Top recommendation for VoxClone** — MIT license, pip install, English Turbo for MVP path, Multilingual V3 for Phase 13 expansion.

---

### 2.6 Additional engines evaluated

#### Piper TTS (rhasspy/piper)

| Attribute | Assessment |
|-----------|------------|
| Maturity | Mature CPU TTS |
| License | MIT |
| Voice cloning | **No** — preset voices only |
| CPU | **Excellent** |
| Verdict | Useful for **non-cloning TTS** only; out of scope for Phase 8 cloning goal |

#### Spark-TTS (SparkAudio)

| Attribute | Assessment |
|-----------|------------|
| Maturity | Emerging (~2024–2025) |
| License | Apache 2.0 (per CosyVoice ecosystem references) |
| Quality | Strong benchmarks in CosyVoice eval tables |
| Complexity | Medium-high; 0.5B LLM-based |
| Verdict | **Secondary candidate** — similar tier to CosyVoice; less pip-simple than Chatterbox |

#### Fish Speech S2 Pro (Fish Audio)

| Attribute | Assessment |
|-----------|------------|
| Maturity | Cutting-edge (2026 S2 Pro, 4B params) |
| License | **Fish Audio Research License** — restrictive; not MIT/Apache |
| Quality | **Best-in-class** reported benchmarks |
| GPU | **Required** (H200-class for published throughput) |
| Urdu | Listed in 80+ language tier |
| Verdict | **Disqualified for commercial MVP** — license + 4B model exceeds Phase 12 budget |

#### StyleTTS 2

| Attribute | Assessment |
|-----------|------------|
| Maturity | Research-grade |
| License | MIT (code) |
| Cloning | Limited zero-shot vs dedicated cloning models |
| Verdict | **Not recommended** — superseded by Chatterbox/F5 for cloning use case |

---

## 3. Comparison Matrix

Scoring: 1 (poor) – 5 (excellent). **Commercial** column reflects pretrained-weight commercial viability.

| Engine | Maturity | Commercial | Linux | CPU OK | GPU need | Clone quality | EN | Urdu | Easy integrate | Celery async | Hetzner fit | Maintenance | **Total /65** |
|--------|----------|------------|-------|--------|----------|---------------|----|----|----------------|--------------|-------------|-------------|---------------|
| **Chatterbox V3/Turbo** | 5 | 5 | 5 | 2 | 4 | 4 | 5 | 2 | 5 | 5 | 4 | 5 | **51** |
| **OpenVoice V2** | 4 | 5 | 5 | 2 | 4 | 4 | 5 | 2 | 3 | 4 | 3 | 4 | **46** |
| **CosyVoice 3** | 5 | 5 | 4 | 1 | 5 | 5 | 5 | 2 | 2 | 4 | 3 | 5 | **46** |
| **Spark-TTS** | 3 | 5 | 4 | 1 | 4 | 4 | 4 | 2 | 3 | 4 | 3 | 3 | **40** |
| **F5-TTS** | 4 | 1 | 5 | 1 | 5 | 5 | 4 | 1 | 4 | 4 | 3 | 4 | **37** |
| **XTTS-v2** | 3 | 1 | 4 | 2 | 4 | 4 | 4 | 3 | 3 | 4 | 2 | 2 | **32** |
| **Fish Speech S2** | 4 | 1 | 4 | 1 | 5 | 5 | 5 | 4 | 2 | 3 | 2 | 4 | **36** |
| **Piper** | 5 | 5 | 5 | 5 | 1 | 1 | 5 | 1 | 5 | 5 | 5 | 4 | **42*** |

*Piper scores high but **does not clone voices** — not ranked for cloning selection.

### Rankings (voice cloning only)

| Rank | Engine | Rationale |
|------|--------|-----------|
| **1** | **Chatterbox** (Turbo + Multilingual V3) | MIT, pip install, active, lowest ops burden, Hetzner GPU friendly |
| **2** | **OpenVoice V2** | MIT, roadmap alignment, proven cloning; harder deploy than Chatterbox |
| **3** | **CosyVoice 3** | Apache 2.0, best quality tier; high deployment complexity |
| **4** | **Spark-TTS** | Apache 2.0 alternative to CosyVoice |
| **5** | **F5-TTS** | Quality excellent; NC weights block commercial pretrained use |
| **6** | **XTTS-v2** | CPML blocks commercial use |
| **7** | **Fish Speech S2** | Quality leader; license and 4B size block MVP path |

---

## 4. Strategic Answers

### A. Which engine is best for VoxClone?

**Chatterbox Multilingual V3** (with **Chatterbox-Turbo** for English-only premium tier).

Reasons: MIT license, active maintenance, `pip install` simplicity, subprocess-friendly API, built-in watermarking, fits Celery async model, lowest GPU footprint among top-tier cloners, aligns with English-first MVP and deferred GPU spend until Phase 12.

**OpenVoice V2** remains a valid **second choice** due to prior project documentation and MIT license.

---

### B. Which engine is easiest to integrate?

**Chatterbox-Turbo** / **Chatterbox Multilingual V3**

```python
# Documented pattern — not implemented in this phase
from chatterbox.tts_turbo import ChatterboxTurboTTS
model = ChatterboxTurboTTS.from_pretrained(device="cuda")
wav = model.generate(text, audio_prompt_path=ref_wav)
```

Single `pip install chatterbox-tts` vs OpenVoice multi-repo setup or CosyVoice conda stack. Follow **Phase 6 isolation**: separate worker venv or subprocess, not merged into `requirements-ml.txt`.

---

### C. Which engine provides the best output quality?

**Among commercial-safe options:** **CosyVoice 3** ≈ **Chatterbox Multilingual V3** (trade-off: CosyVoice wins on benchmark tables; Chatterbox wins on stability/watermarking/agent use cases).

**Absolute quality (license aside):** Fish Speech S2 Pro > CosyVoice 3 > F5-TTS > Chatterbox ≈ OpenVoice.

Quality alone does not override license and hosting constraints for VoxClone.

---

### D. Which engine is most suitable for CPU-only deployment?

**None for production voice cloning.**

| Engine | CPU reality |
|--------|-------------|
| Chatterbox | Supports `device="cpu"` — demo/dev only |
| OpenVoice | Runs on CPU — impractically slow |
| Piper | CPU-native but **not cloning** |

VoxClone Phase 12 CPU VPS runs Whisper + Demucs + DeepFilterNet. Voice cloning should be scheduled as a **GPU worker tier** when revenue justifies it — not on 4 vCPU / 8 GB CPU.

---

### E. Which engine is most suitable for future Hetzner deployment?

**Chatterbox-Turbo** on a **Hetzner GPU VPS** (or dedicated GPU cloud add-on).

| Phase 12 target | Voice cloning implication |
|-----------------|---------------------------|
| 4 vCPU / 8 GB CPU MVP | **No voice cloning worker** |
| 8 vCPU / 16 GB upgrade | Still insufficient without GPU |
| GPU instance (future) | Chatterbox-Turbo (~350M) fits smallest VRAM budget |

Estimated incremental cost: **€30–80+/month** for entry GPU VPS vs CPU-only plan (market-dependent at Phase 12).

---

### F. Which engine should be selected for a proof-of-concept?

**Primary PoC: Chatterbox-Turbo** (English, MIT, fastest path to validated Celery job).

**Secondary PoC: OpenVoice V2** (validate roadmap assumption; compare tone-color quality).

PoC scope (future milestone — not Phase 8 code):

1. Isolated venv + subprocess or dedicated Celery queue `gpu`  
2. Reference WAV from existing `vocal_separation` stems  
3. Generate 30 s English sample  
4. Measure VRAM, wall time, subjective quality  
5. Document dependency conflict matrix vs Demucs pins  

---

### G. Alignment with strategic criteria

| Criterion | Assessment |
|-----------|------------|
| **Commercial launch readiness** | Voice cloning **must not delay MVP** (Phases 9–11). Chatterbox MIT license clears future commercialization. |
| **Hosting cost control** | Defer GPU until Phase 12; use Turbo not CosyVoice/Fish for lowest VRAM. |
| **Operational simplicity** | Chatterbox pip > OpenVoice > CosyVoice. Subprocess isolation matches existing architecture. |
| **Revenue generation potential** | Premium tier: "Clone your voice" / dubbing add-on post-Phase 11 billing. |
| **User value** | Pairs with `vocal_separation` stems + `subtitle_generation` text for dubbing pipeline (Phase 13+). |

---

## 5. VoxClone Pipeline Synergy (Future)

```
upload → vocal_separation → vocals stem (reference)
       → subtitle_generation → transcript text
       → voice_clone (future) → cloned speech WAV
       → FFmpeg mux → dubbed video (voice_replacement, future)
```

Existing `voice_clone` and `voice_replacement` job types return HTTP 422 — schema placeholders only.

---

## 6. Dependency and Worker Isolation

**Critical:** Phase 5 pins `torch==2.8.0+cpu` for Demucs. Voice cloning engines typically require:

- CUDA-enabled PyTorch  
- Python 3.10–3.11 (many engines; VoxClone uses 3.12)  
- Additional packages (transformers, etc.)

**Approved pattern (mirror Phase 6 DeepFilterNet):**

| Approach | Voice cloning |
|----------|---------------|
| Subprocess + isolated venv | **Preferred** — `tools/voice-cloning/.venv` |
| Separate Celery queue `gpu` | Route clone jobs to GPU worker |
| Shared `requirements-ml.txt` | **Forbidden** without full Demucs regression |

Python 3.12 compatibility must be validated per engine during PoC — may require **3.11 worker container** even if API stays on 3.12.

---

## 7. Legal and Product Considerations

| Topic | Requirement |
|-------|-------------|
| Voice cloning consent | User must own/reference rights to voice sample |
| Watermarking | Chatterbox includes Perth watermark — disclose to users |
| Retention | Cloned outputs subject to configurable retention (default 10 days) |
| Urdu / Roman Urdu | Deferred Phase 13 — no engine provides production Urdu clone today |
| MVP marketing | Do not advertise voice cloning until post-Phase 12 |

---

## 8. Phase 8 Conclusions

| Item | Decision |
|------|----------|
| Implement now? | **No** — feasibility complete |
| MVP includes cloning? | **No** |
| Recommended engine | **Chatterbox** (Turbo English / V3 multilingual) |
| PoC engine | **Chatterbox-Turbo** |
| GPU required? | **Yes** for production quality |
| Phase 12 CPU VPS runs cloning? | **No** |
| XTTS / F5 pretrained / Fish S2 | **Not commercial-safe** for VoxClone as-is |

---

## 9. Recommended Next Steps

| Phase | Action |
|-------|--------|
| **Phase 9** | Flutter MVP — no voice cloning UI |
| **Phase 10** | Auth — user consent for voice samples |
| **Phase 11** | Billing — define premium cloning tier |
| **Phase 12** | Hetzner deploy + **GPU worker** + Chatterbox PoC on production hardware |
| **Phase 13** | Roman Urdu / translation — revisit multilingual TTS (Urdu gap) |

---

## 10. Related Documents

```
docs/context/PROJECT_SNAPSHOT_2026_06_22.md
docs/context/NEXT_SESSION_START_HERE.md
docs/reports/PHASE7_M3_WHISPER_BENCHMARK_REPORT.md
docs/reports/PHASE6_DEPENDENCY_PROTECTION_RULES.md
docs/context/NEXT_PHASES_ROADMAP.md
```

---

*Phase 8 feasibility study complete — documentation only, 2026-06-23.*
