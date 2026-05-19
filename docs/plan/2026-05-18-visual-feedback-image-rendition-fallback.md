# Visual Feedback Image-Rendition Fallback Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** GUSTAV soll gültige PNG/JPG-Bildabgaben robuster an Mistral senden, indem nach einer bildbezogenen Provider-429 genau einmal eine JPEG-1280-Rendition versucht wird, ohne das gespeicherte Original zu verändern.

**Architecture:** Die Änderung bleibt im Learning-Adapter. Direkte Bildabgaben (`image/png`, `image/jpeg`) werden zunächst wie bisher als Original-Data-URI an den Visual-Feedback-Pfad gesendet. Wenn der Provider diesen Originalversuch mit 429 ablehnt, erzeugt der Adapter aus denselben validierten Upload-Bytes eine providergebundene JPEG-Rendition und ruft denselben Visual-Feedback-Program-Call genau einmal erneut auf.

**Tech Stack:** Python 3.13, Pillow, DSPy/LiteLLM/OpenAI-compatible Chat Completions, pytest, Supabase/PostgreSQL nur als bestehende Persistenz- und Testumgebung.

---

## Referenzen und Befund

Tickets:

- `docs/tickets/learning-visual-feedback-provider-image-admission-2026-05-18.md`
- Vorgänger: `docs/tickets/learning-visual-feedback-provider-rate-limit-2026-05-12.md`

Relevante Live-Verifikation gegen `mistral-small-latest` mit echtem Visual-Analyse-Prompt, Aufgabenstellung, Kriterien und `teacher_context_md`:

- PNG-Original `1920x1200`, `372528` Bytes, `496704` Base64-Zeichen: 429 `rate_limited`, Code `1300`.
- Dasselbe PNG als JPEG-1280 q85 `1280x800`, `120166` Bytes, `160224` Base64-Zeichen: akzeptiert.
- JPG-Original `1357x1268`, `379358` Bytes, `505812` Base64-Zeichen: 429 `throttling_error`, Code `429`.
- Dasselbe JPG als JPEG-1280 q85 `1280x1196`, `254482` Bytes, `339312` Base64-Zeichen: akzeptiert.

Interpretation: Die Dateigröße allein erklärt den Fehler nicht. Wahrscheinlicher ist eine Kombination aus Data-URI/Base64-Transport, Bildmaßen, Kompression und Mistrals interner Bildaufnahme. Der gespeicherte Upload ist gültig; fragil ist die providergebundene Repräsentation.

## User Story und BDD-Szenarien

User Story:

Als Schüler möchte ich handschriftliche oder gezeichnete Lösungen als Bild hochladen können, damit GUSTAV sie zuverlässig bewertet, auch wenn der externe Visual-Provider die ursprüngliche Bildrepräsentation ablehnt.

BDD-Szenarien:

- Given ein Schüler lädt ein gültiges PNG oder JPG hoch, when der Visual-Provider das Original akzeptiert, then GUSTAV speichert das normale Feedback und verändert die Originaldatei nicht.
- Given ein Schüler lädt ein gültiges PNG oder JPG hoch, when der Visual-Provider das Original mit 429 ablehnt, then GUSTAV erzeugt serverseitig eine JPEG-1280-q85-Rendition und versucht denselben Visual-Feedback-Call genau einmal erneut.
- Given der JPEG-1280-Fallback wird akzeptiert, when die Analyse abgeschlossen wird, then der Schüler sieht normales Feedback und Lehrer sehen weiterhin das unveränderte Original.
- Given auch der JPEG-1280-Fallback wird mit 429 abgelehnt, when der Worker den Fehler persistiert, then die öffentliche Submission bleibt `feedback_failed`, intern steht `feedback_last_error='image_too_complex_for_provider'`, und die UI zeigt den bestehenden deutschen Upload-Hinweis ohne internen Code.
- Given der Upload ist inhaltlich kein gültiges Bild, when die Signaturvalidierung fehlschlägt, then GUSTAV erzeugt keine Rendition und bleibt beim bestehenden `invalid_upload_content`-Pfad.
- Given eine PDF-Abgabe wird verarbeitet, when der Visual-Feedback-Pfad aufgerufen wird, then dieser Plan ändert das PDF-Stitching nicht.

## Contract, Datenmodell und Dateien

API/OpenAPI:

- Keine Änderung an `api/openapi.yml`.
- Kein neuer öffentlicher Fehlercode.
- Bestehender öffentlicher Zustand bleibt `error_code='feedback_failed'`.

PostgreSQL/Supabase:

- Keine Migration.
- `learning_submissions.feedback_last_error` wird weiter für den internen Grund `image_too_complex_for_provider` genutzt.

Zu ändernde Dateien:

- `backend/learning/adapters/local_feedback.py`: Provider-bound Rendition, 429-Fallback, visuelle LM-Retry-Konfiguration, PII-freie Diagnostik.
- `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py`: Adaptertests für Originalversuch, Fallback-Rendition und doppelte 429.
- `backend/tests/learning_adapters/test_local_feedback_dspy.py`: Konfigurationstest, dass visuelle LMs interne DSPy/LiteLLM-Retries deaktivieren.
- Optional nur bei Testlücke: `backend/tests/test_learning_ui_feedback_failure_messages.py` erweitern, falls die bestehende UI-Mapping-Abdeckung nicht ausreicht.

## Umsetzungsschritte

### Task 1: Tests für JPEG-1280-Rendition ergänzen

**Files:**

- Modify: `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py`
- Modify: `backend/learning/adapters/local_feedback.py`

- [ ] **Step 1: Failing Test für erfolgreiche Rendition nach Original-429 schreiben**

In `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py` einen Test ergänzen:

```python
def test_local_feedback_analyze_visual_retries_once_with_jpeg_rendition_after_original_429(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = "submissions/course/task/student/handwritten.jpg"
    payload_bytes = _jpeg_bytes()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()
    submission = {
        "id": "sub-jpeg-fallback",
        "kind": "image",
        "mime_type": "image/jpeg",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": "image/jpeg",
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    captured: list[str] = []

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        captured.append(image_data_uri)
        if len(captured) == 1:
            raise _ProviderRateLimitError("rate_limited")
        return FeedbackResult(
            feedback_md="OK",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
        )

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    res = adapter.analyze_visual(  # type: ignore[attr-defined]
        submission=submission,
        job_payload=job_payload,
        criteria=["K1"],
        instruction_md="Aufgabe",
        teacher_context_md="Hinweis",
    )

    assert res.feedback_md == "OK"
    assert len(captured) == 2
    assert captured[0].startswith("data:image/jpeg;base64,")
    assert base64.b64decode(captured[0].split(",", 1)[1]) == payload_bytes
    assert captured[1].startswith("data:image/jpeg;base64,")
    fallback_bytes = base64.b64decode(captured[1].split(",", 1)[1])
    assert fallback_bytes != payload_bytes
    with Image.open(BytesIO(fallback_bytes)) as image:
        assert image.format == "JPEG"
        assert max(image.size) <= 1280
        assert image.mode == "RGB"
    assert target.read_bytes() == payload_bytes
```

- [ ] **Step 2: Test ausführen und rot bestätigen**

Run:

```bash
.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py::test_local_feedback_analyze_visual_retries_once_with_jpeg_rendition_after_original_429
```

Expected: FAIL, weil der Adapter nach Provider-429 noch keinen JPEG-Fallback versucht.

- [ ] **Step 3: Minimalen Rendition-Helper implementieren**

In `backend/learning/adapters/local_feedback.py` `ImageOps`-basierte Helper ergänzen. Die Funktionen bleiben privat, weil dies ein providergebundenes Adapterdetail ist:

```python
_VISUAL_PROVIDER_RENDITION_MAX_EDGE = 1280
_VISUAL_PROVIDER_RENDITION_JPEG_QUALITY = 85


def _decode_provider_image_b64(image_b64: str) -> bytes:
    try:
        return base64.b64decode(image_b64, validate=True)
    except Exception as exc:
        raise FeedbackPermanentError("invalid_upload_content") from exc


def _provider_safe_jpeg_rendition_b64(*, image_b64: str) -> str:
    """Return a provider-bound JPEG rendition without mutating the stored upload."""
    raw = _decode_provider_image_b64(image_b64)
    try:
        from PIL import Image, ImageOps

        with Image.open(BytesIO(raw)) as image:
            image = ImageOps.exif_transpose(image)
            image = image.convert("RGB")
            image.thumbnail(
                (_VISUAL_PROVIDER_RENDITION_MAX_EDGE, _VISUAL_PROVIDER_RENDITION_MAX_EDGE),
                Image.Resampling.LANCZOS,
            )
            out = BytesIO()
            image.save(
                out,
                format="JPEG",
                quality=_VISUAL_PROVIDER_RENDITION_JPEG_QUALITY,
                optimize=True,
                progressive=False,
            )
    except FeedbackPermanentError:
        raise
    except Exception as exc:
        raise FeedbackPermanentError("provider_image_rendition_failed") from exc
    return base64.b64encode(out.getvalue()).decode("ascii")
```

- [ ] **Step 4: Adapter-Fallback minimal anschließen**

In `analyze_visual(...)` für direkte `image/jpeg`/`image/png` die ursprünglichen Bilddaten (`image_b64`) im lokalen Scope behalten. Den bestehenden `visual_feedback_program.analyze_visual_feedback(...)`-Call in einen kleinen privaten Call-Helper kapseln und bei Provider-429 einmal mit `data:image/jpeg;base64,...` wiederholen.

Zielstruktur:

```python
def _call_visual_feedback_program(
    *,
    image_data_uri: str,
    criteria: Sequence[str],
    instruction_md: str | None,
    teacher_context_md: str | None,
    analysis_lm,
    synthesis_lm,
) -> FeedbackResult:
    from backend.learning.adapters.dspy import visual_feedback_program

    return visual_feedback_program.analyze_visual_feedback(
        image_data_uri=image_data_uri,
        criteria=criteria,
        teacher_instructions_md=instruction_md,
        teacher_context_md=teacher_context_md,
        analysis_lm=analysis_lm,
        synthesis_lm=synthesis_lm,
    )
```

Im `except Exception as exc`-Block von `analyze_visual(...)`:

```python
if image_b64 and mime in {"image/jpeg", "image/png"} and _is_provider_rate_limit_exception(exc):
    fallback_b64 = _provider_safe_jpeg_rendition_b64(image_b64=image_b64)
    fallback_uri = _provider_image_data_uri(mime="image/jpeg", image_b64=fallback_b64)
    try:
        return _call_visual_feedback_program(
            image_data_uri=fallback_uri,
            criteria=criteria,
            instruction_md=instruction_md,
            teacher_context_md=teacher_context_md,
            analysis_lm=analysis_lm,
            synthesis_lm=synthesis_lm,
        )
    except Exception as fallback_exc:
        if _is_provider_rate_limit_exception(fallback_exc):
            raise FeedbackPermanentError("image_too_complex_for_provider") from fallback_exc
        _raise_feedback_error_for_exception(
            fallback_exc,
            default_transient_code="visual_feedback_failed",
            provider_image_diagnostics=_provider_image_diagnostics(mime="image/jpeg", image_b64=fallback_b64),
        )
_raise_feedback_error_for_exception(
    exc,
    default_transient_code="visual_feedback_failed",
    provider_image_diagnostics=provider_image_diagnostics,
)
```

Wichtig: Den Helper so platzieren, dass `FeedbackPermanentError("provider_image_rendition_failed")` nicht versehentlich als transienter Providerfehler umklassifiziert wird.

- [ ] **Step 5: Test grün machen**

Run:

```bash
.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py::test_local_feedback_analyze_visual_retries_once_with_jpeg_rendition_after_original_429
```

Expected: PASS.

### Task 2: Doppelte 429 als permanenten Bild-Admission-Fehler testen

**Files:**

- Modify: `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py`
- Modify: `backend/learning/adapters/local_feedback.py`

- [ ] **Step 1: Failing Test für Fallback-429 schreiben**

In `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py` einen parametrisierten Test ergänzen:

```python
@pytest.mark.parametrize(
    ("mime_type", "filename", "payload_factory"),
    [
        ("image/png", "visual.png", _large_png_bytes),
        ("image/jpeg", "visual.jpg", _jpeg_bytes),
    ],
)
def test_local_feedback_analyze_visual_maps_fallback_rate_limit_to_complex_image(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    mime_type: str,
    filename: str,
    payload_factory,
) -> None:
    monkeypatch.setenv("STORAGE_VERIFY_ROOT", str(tmp_path))
    monkeypatch.setenv("OPENAI_BASE_URL", "http://example.test/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")
    dspy_cache = tmp_path / "dspy_cache"
    dspy_cache.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("DSPY_CACHEDIR", str(dspy_cache))

    storage_key = f"submissions/course/task/student/{filename}"
    payload_bytes = payload_factory()
    target = tmp_path / storage_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload_bytes)
    sha = hashlib.sha256(payload_bytes).hexdigest()
    submission = {
        "id": "sub-double-429",
        "kind": "image",
        "mime_type": mime_type,
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
        "course_id": "c",
        "task_id": "t",
        "student_sub": "s",
    }
    job_payload = {
        "mime_type": mime_type,
        "storage_key": storage_key,
        "size_bytes": len(payload_bytes),
        "sha256": sha,
    }

    prog = importlib.import_module("backend.learning.adapters.dspy.visual_feedback_program")
    calls: list[str] = []

    def _fake_analyze_visual_feedback(*, image_data_uri: str, **_: object) -> FeedbackResult:
        calls.append(image_data_uri)
        raise _ProviderRateLimitError("rate_limited")

    monkeypatch.setattr(prog, "analyze_visual_feedback", _fake_analyze_visual_feedback)

    mod = importlib.import_module("backend.learning.adapters.local_feedback")
    adapter = mod.build()  # type: ignore[attr-defined]

    with pytest.raises(mod.FeedbackPermanentError) as exc:  # type: ignore[attr-defined]
        adapter.analyze_visual(  # type: ignore[attr-defined]
            submission=submission,
            job_payload=job_payload,
            criteria=["K1"],
            instruction_md="Aufgabe",
            teacher_context_md="Hinweis",
        )

    assert str(exc.value) == "image_too_complex_for_provider"
    assert len(calls) == 2
    assert calls[0].startswith(f"data:{mime_type};base64,")
    assert calls[1].startswith("data:image/jpeg;base64,")
    assert target.read_bytes() == payload_bytes
```

- [ ] **Step 2: Test rot bestätigen**

Run:

```bash
.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py::test_local_feedback_analyze_visual_maps_fallback_rate_limit_to_complex_image
```

Expected: FAIL, solange doppelte 429 noch nicht für JPG und PNG einheitlich zu `image_too_complex_for_provider` wird.

- [ ] **Step 3: Fallback-429-Klassifikation vervollständigen**

In `backend/learning/adapters/local_feedback.py` sicherstellen:

- Der erste direkte Bild-429 löst genau einen JPEG-Fallback aus.
- Ein 429 im Fallback löst `FeedbackPermanentError("image_too_complex_for_provider")` aus.
- Nicht-429 im Fallback läuft weiter durch `_raise_feedback_error_for_exception(...)`.
- `provider_image_diagnostics` enthält für Original und Rendition mindestens MIME, Bytes, Base64-Länge, Breite, Höhe und Pixelzahl.

Die bestehende `_provider_image_diagnostics(...)` so erweitern, dass sie Bilddimensionen nicht nur für PNG liest:

```python
def _provider_image_diagnostics(*, mime: str, image_b64: str) -> dict[str, object]:
    """Return PII-free image metadata used only for provider-failure diagnostics."""
    diagnostics: dict[str, object] = {"mime": mime, "base64_chars": len(image_b64)}
    try:
        raw = base64.b64decode(image_b64, validate=True)
        diagnostics["bytes"] = len(raw)
    except Exception:
        return diagnostics
    if mime not in {"image/png", "image/jpeg"}:
        return diagnostics
    try:
        from PIL import Image

        with Image.open(BytesIO(raw)) as image:
            width, height = image.size
            diagnostics["width"] = width
            diagnostics["height"] = height
            diagnostics["pixels"] = width * height
    except Exception as exc:
        LOG.warning("learning.feedback.visual_image_diagnostics_unavailable reason=%s", exc.__class__.__name__)
    return diagnostics
```

- [ ] **Step 4: Test grün machen**

Run:

```bash
.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py::test_local_feedback_analyze_visual_maps_fallback_rate_limit_to_complex_image
```

Expected: PASS.

### Task 3: Interne DSPy/LiteLLM-Retries für visuelle Requests abschalten

**Files:**

- Modify: `backend/tests/learning_adapters/test_local_feedback_dspy.py`
- Modify: `backend/learning/adapters/local_feedback.py`

- [ ] **Step 1: Failing Test für `num_retries=0` schreiben**

In `backend/tests/learning_adapters/test_local_feedback_dspy.py` einen Test ergänzen oder den bestehenden Visual-LM-Konfigurationstest erweitern:

```python
def test_adapter_disables_internal_retries_for_visual_lms(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.learning.adapters import local_feedback

    observed: dict = {}
    _install_fake_dspy(monkeypatch, observed=observed)

    monkeypatch.setenv("OPENAI_BASE_URL", "http://example/api/v1")
    monkeypatch.setenv("AI_TEXT_MODEL", "text-model")
    monkeypatch.setenv("AI_VISUAL_MODEL", "visual-model")

    from backend.learning.adapters import local_vision
    from backend.learning.adapters.dspy import visual_feedback_program

    monkeypatch.setattr(local_vision, "_resolve_submission_image_bytes", lambda **_: "AA==")
    monkeypatch.setattr(
        visual_feedback_program,
        "analyze_visual_feedback",
        lambda **_: FeedbackResult(
            feedback_md="OK",
            analysis_json={"schema": "criteria.v2", "score": 0, "criteria_results": []},
            parse_status="parsed_structured",
        ),
    )

    adapter = local_feedback.build()
    adapter.analyze_visual(  # type: ignore[attr-defined]
        submission={"id": "s", "kind": "image", "mime_type": "image/png"},
        job_payload={"mime_type": "image/png"},
        criteria=["K1"],
        instruction_md=None,
        teacher_context_md=None,
    )

    lm_calls = observed.get("lm_calls") or []
    assert len(lm_calls) == 2
    assert all(call["kwargs"].get("num_retries") == 0 for call in lm_calls)
```

- [ ] **Step 2: Test rot bestätigen**

Run:

```bash
.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_dspy.py::test_adapter_disables_internal_retries_for_visual_lms
```

Expected: FAIL, weil `dspy.LM` aktuell den Default `num_retries=3` nutzt.

- [ ] **Step 3: Visuelle LM-Erzeugung anpassen**

In `_LocalFeedbackAdapter._build_lm(...)` einen optionalen Parameter ergänzen:

```python
def _build_lm(
    self,
    *,
    model: str,
    temperature: float,
    think_level: str | None,
    reasoning_effort: str | None,
    num_retries: int | None = None,
):
    ...
    if num_retries is not None:
        lm_kwargs["num_retries"] = num_retries
    return dspy.LM(model, **lm_kwargs)
```

Dann nur für Visual-LMs `num_retries=0` setzen:

```python
self._visual_analysis_lm = self._build_lm(
    model=self._visual_model,
    temperature=self._visual_analysis_temperature,
    think_level=self._visual_analysis_think_level,
    reasoning_effort=self._visual_analysis_reasoning_effort,
    num_retries=0,
)
```

Dasselbe für `_get_visual_synthesis_lm(...)`. Text-LMs unverändert lassen.

- [ ] **Step 4: Konfigurationstest grün machen**

Run:

```bash
.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_dspy.py::test_adapter_disables_internal_retries_for_visual_lms
```

Expected: PASS.

### Task 4: Bestehende Verhaltensgrenzen absichern

**Files:**

- Modify: `backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py`
- Modify: `backend/tests/test_learning_ui_feedback_failure_messages.py` nur falls nötig

- [ ] **Step 1: Bestehende Tests auf neue Erwartung aktualisieren**

Der bestehende Test `test_local_feedback_analyze_visual_keeps_small_png_rate_limit_transient` passt nicht mehr zur gewählten Produktentscheidung „Fallback nach 429“. Er soll entweder entfernt oder in einen Fallback-Erfolgstest umgebaut werden. Bevorzugte Änderung: in einen Test umbenennen, der zeigt, dass auch kleine direkte Bilder nach einem ersten 429 genau einmal als JPEG-Rendition versucht werden.

Erwartung:

```python
assert len(calls) == 2
assert calls[0].startswith("data:image/png;base64,")
assert calls[1].startswith("data:image/jpeg;base64,")
```

- [ ] **Step 2: PDF-Nicht-Scope weiter absichern**

Den bestehenden Test `test_local_feedback_analyze_visual_keeps_stitched_pdf_png_out_of_rate_limit_normalization` beibehalten. Er muss weiterhin zeigen, dass PDF-Stitching in diesem Plan nicht automatisch in JPEG-1280 umgewandelt wird.

Run:

```bash
.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py::test_local_feedback_analyze_visual_keeps_stitched_pdf_png_out_of_rate_limit_normalization
```

Expected: PASS.

- [ ] **Step 3: UI-Mapping prüfen**

Run:

```bash
.venv/bin/pytest -q backend/tests/test_learning_ui_feedback_failure_messages.py
```

Expected: PASS. Falls dieser Test nur die PNG-Formulierung implizit beschreibt, die Copy so belassen, weil sie bewusst dateiformatunabhängig ist: „Das Bild ist wahrscheinlich zu groß oder zu komplex...“

### Task 5: Gesamttests und kritische Review

**Files:**

- No additional code files expected.

- [ ] **Step 1: Adapter- und UI-Tests ausführen**

Run:

```bash
.venv/bin/pytest -q backend/tests/learning_adapters/test_local_feedback_visual_pipeline.py backend/tests/learning_adapters/test_local_feedback_dspy.py backend/tests/test_learning_worker_feedback_error_mapping.py backend/tests/test_learning_ui_feedback_failure_messages.py
```

Expected: PASS.

- [ ] **Step 2: Breiteren Backend-Check ausführen**

Run:

```bash
.venv/bin/pytest -q backend/tests/test_learning_worker_jobs.py backend/tests/test_learning_worker_visual_dspy_pipeline.py backend/tests/test_openapi_learning_native_upload_visual_contract.py
```

Expected: PASS.

- [ ] **Step 3: Projektweiten Mindestcheck ausführen**

Run:

```bash
make verify
```

Expected: PASS.

- [ ] **Step 4: Kritische Codeanalyse durchführen**

Prüfpunkte vor Abschluss:

- KISS: Fallback-Logik ist ein klarer, einmaliger Pfad und keine allgemeine Retry-Maschine.
- Security/DSGVO: Logs enthalten keine Bildinhalte, Prompts, Aufgaben-Kontexte, Storage Keys, Hashes, API Keys oder Schülerdaten.
- Clean Architecture: Provider-Rendition bleibt im Adapter; Use Cases und Web-Routen kennen keine Provider-Details.
- Performance: Rendition dekodiert das Bild höchstens im Fehlerfall nach Original-429; keine zusätzliche Arbeit auf erfolgreichen Originalpfaden.
- Robustheit: `provider_image_rendition_failed` wird nicht still durch das fragile Original ersetzt.

## Review-Nachtrag 2026-05-19: P2 Pixelbudget vor Rendition-Dekodierung

Der externe Review-Hinweis P2 ist berechtigt: `LEARNING_MAX_UPLOAD_BYTES` begrenzt nur die komprimierte Upload-Datei, nicht die entpackten Pixel im Worker. Ein stark komprimiertes großes Bild könnte im JPEG-Fallback vor dem Downscale sehr viel RAM belegen.

Umsetzung:

- `_provider_safe_jpeg_rendition_b64(...)` prüft direkt nach `Image.open(...)` die Bildmaße und bricht vor `ImageOps.exif_transpose(...)`, `convert(...)`, Alpha-Compositing und `thumbnail(...)` ab, wenn `width * height > 16_777_216`.
- Der Abbruch nutzt intern `FeedbackPermanentError("image_too_complex_for_provider")`, damit die öffentliche Fehlermeldung die bestehende, dateiformatunabhängige Schüler-Handlungsanweisung verwendet.
- Das Log bleibt PII-frei und enthält nur Breite, Höhe, Pixelzahl, Limit, Bytezahl und Base64-Länge.
- Wenn der Pixelbudget-Abbruch nach einem ursprünglichen Provider-429 passiert, übernimmt der Adapter die `usage_events` dieses ersten Provider-Calls in den permanenten Fehler.
- P1 bleibt ausdrücklich außerhalb dieses Nachtrags; die Klassifikation eines doppelten Provider-429 wird hier nicht verändert.

Zusätzliche Tests:

- Ein künstliches großes PNG wird vor EXIF-Transpose und Dekodierung als `image_too_complex_for_provider` abgelehnt.
- Nach ursprünglichem Provider-429 plus Pixelbudget-Abbruch erfolgt kein zweiter Provider-Call, und die Usage-Events des ersten Calls bleiben erhalten.

## Annahmen

- Der erste 429 auf einem direkten PNG/JPG-Bild ist hinreichend bildbezogen, um genau einen JPEG-1280-Fallback zu rechtfertigen.
- Wenn auch JPEG-1280 mit 429 scheitert, ist für den Schüler eine konkrete Upload-Handlungsanweisung hilfreicher als weitere automatische Provider-Versuche.
- `mistral-small-latest` bleibt vorerst das relevante Prod-Modell; die Lösung bleibt aber providerneutral genug für OpenAI-kompatible Vision-Provider.
- Es gibt keine öffentliche API- oder DB-Vertragsänderung; die Änderung liegt vollständig im internen Analysepfad.
