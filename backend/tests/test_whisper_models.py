"""Unit tests for language-first Whisper model routing (Phase 7 M2)."""

from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from app.core.config import Settings
from app.models.job import JobType
from app.services.whisper_models import (
    WHISPER_LANGUAGE_AUTO,
    apply_whisper_metadata,
    resolve_whisper_model,
    validate_whisper_language,
)


def _settings(**overrides: object) -> Settings:
    defaults = {
        "WHISPER_MODEL_PATH": Path("models/ggml-tiny.en.bin"),
        "WHISPER_ROUTING_POLICY": "english_first",
    }
    defaults.update(overrides)
    return Settings(**defaults)


class WhisperRoutingTests(unittest.TestCase):
    """Validation matrix for resolve_whisper_model()."""

    def test_english_only_media_omitted_language_backward_compat(self) -> None:
        resolved = resolve_whisper_model(
            None,
            JobType.SUBTITLE_GENERATION,
            None,
            _settings(),
        )
        self.assertEqual(resolved.alias, "tiny")
        self.assertEqual(resolved.path.name, "ggml-tiny.en.bin")
        self.assertEqual(resolved.variant, "english")
        self.assertEqual(resolved.cli_language, "en")
        self.assertIsNone(resolved.language_requested)

    def test_english_only_media_explicit_en(self) -> None:
        resolved = resolve_whisper_model(
            "base",
            JobType.SUBTITLE_GENERATION,
            "en",
            _settings(),
        )
        self.assertEqual(resolved.path.name, "ggml-base.en.bin")
        self.assertEqual(resolved.variant, "english")
        self.assertEqual(resolved.cli_language, "en")
        self.assertEqual(resolved.language_requested, "en")

    def test_urdu_only_media(self) -> None:
        resolved = resolve_whisper_model(
            "base",
            JobType.SUBTITLE_GENERATION,
            "ur",
            _settings(),
        )
        self.assertEqual(resolved.path.name, "ggml-base.bin")
        self.assertEqual(resolved.variant, "multilingual")
        self.assertEqual(resolved.cli_language, "ur")
        self.assertEqual(resolved.language_requested, "ur")

    def test_mixed_english_urdu_auto_detection(self) -> None:
        resolved = resolve_whisper_model(
            "base",
            JobType.KARAOKE,
            WHISPER_LANGUAGE_AUTO,
            _settings(),
        )
        self.assertEqual(resolved.path.name, "ggml-base.bin")
        self.assertEqual(resolved.variant, "multilingual")
        self.assertIsNone(resolved.cli_language)
        self.assertEqual(resolved.language_requested, WHISPER_LANGUAGE_AUTO)

    def test_karaoke_default_alias_english_first(self) -> None:
        resolved = resolve_whisper_model(
            None,
            JobType.KARAOKE,
            None,
            _settings(),
        )
        self.assertEqual(resolved.alias, "base")
        self.assertEqual(resolved.path.name, "ggml-base.en.bin")
        self.assertEqual(resolved.cli_language, "en")

    def test_subtitle_pipeline_whisper_model_override(self) -> None:
        resolved = resolve_whisper_model(
            "small",
            JobType.SUBTITLE_GENERATION,
            None,
            _settings(),
        )
        self.assertEqual(resolved.alias, "small")
        self.assertEqual(resolved.path.name, "ggml-small.en.bin")

    def test_multilingual_default_policy_future(self) -> None:
        resolved = resolve_whisper_model(
            None,
            JobType.SUBTITLE_GENERATION,
            None,
            _settings(WHISPER_ROUTING_POLICY="multilingual_default"),
        )
        self.assertEqual(resolved.path.name, "ggml-tiny.bin")
        self.assertEqual(resolved.variant, "multilingual")
        self.assertIsNone(resolved.cli_language)

    def test_hindi_arabic_persian_codes(self) -> None:
        for code in ("hi", "ar", "fa"):
            with self.subTest(language=code):
                resolved = resolve_whisper_model(
                    "tiny",
                    JobType.SUBTITLE_GENERATION,
                    code,
                    _settings(),
                )
                self.assertEqual(resolved.variant, "multilingual")
                self.assertEqual(resolved.cli_language, code)
                self.assertEqual(resolved.path.name, "ggml-tiny.bin")

    def test_apply_whisper_metadata(self) -> None:
        resolved = resolve_whisper_model(
            "tiny",
            JobType.SUBTITLE_GENERATION,
            "ur",
            _settings(),
        )
        params: dict = {}
        apply_whisper_metadata(params, resolved)
        self.assertEqual(params["whisper_model"], "tiny")
        self.assertEqual(params["whisper_model_file"], "ggml-tiny.bin")
        self.assertEqual(params["whisper_model_variant"], "multilingual")
        self.assertEqual(params["language_requested"], "ur")

    def test_validate_whisper_language_auto(self) -> None:
        self.assertEqual(validate_whisper_language("auto"), "auto")
        self.assertEqual(validate_whisper_language(" AUTO "), "auto")

    def test_validate_whisper_language_invalid(self) -> None:
        with self.assertRaises(ValueError):
            validate_whisper_language("not-a-language")


class WhisperSchemaLanguageValidationTests(unittest.TestCase):
    def test_job_create_rejects_invalid_language_on_subtitle_job(self) -> None:
        from app.schemas.job import JobCreate

        with self.assertRaises(ValueError):
            JobCreate(
                media_id="test-media-id",
                job_type=JobType.SUBTITLE_GENERATION,
                parameters={"language": "invalid-lang"},
            )

    def test_job_create_accepts_auto_language(self) -> None:
        from app.schemas.job import JobCreate

        job = JobCreate(
            media_id="test-media-id",
            job_type=JobType.SUBTITLE_GENERATION,
            parameters={"language": "auto"},
        )
        self.assertEqual(job.parameters["language"], "auto")


if __name__ == "__main__":
    unittest.main()
