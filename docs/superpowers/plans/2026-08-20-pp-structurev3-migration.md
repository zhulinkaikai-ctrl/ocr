# PP-StructureV3 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the document-specific OCR pipeline with PP-StructureV3, keep local Streamlit upload testing, support image and PDF input, and return PaddleX's JSON-safe raw results for Java-side parsing.

**Architecture:** `ocr_api/adapter.py` owns lazy PP-StructureV3 initialization and result serialization. `ocr_api/file_loader.py` validates Base64/URL file input, accepts images and PDFs, and materializes request bytes into a temporary path so the same adapter call works for both formats. FastAPI routes expose one generic structure endpoint plus the two historical OCR paths as aliases; successful bodies contain only the raw result object or page-result list, while errors retain the existing error envelope. Streamlit uses the same adapter and displays the uploaded file plus raw JSON without document-specific extraction.

**Tech Stack:** Python 3.12, FastAPI, Streamlit, PaddleOCR 3.7 / PP-StructureV3, PaddleX result serialization, Pillow, HTTPX, unittest.

---

## File Structure

- Create: `ocr_api/adapter.py` — PP-StructureV3 lazy adapter, runtime configuration, raw JSON-safe result conversion.
- Create: `ocr_api/file_loader.py` — image/PDF Base64 and URL validation, bounded downloads, temporary-file materialization.
- Modify: `ocr_api/schemas.py` — generic file request fields with legacy image aliases.
- Modify: `ocr_api/responses.py` — keep only the shared error envelope.
- Modify: `ocr_api/routes.py` — generic raw-result route, historical aliases, unchanged health implementation.
- Modify: `app.py` — image/PDF upload UI that renders raw PP-StructureV3 JSON.
- Modify: `scripts/preload-ocr.py` — preload PP-StructureV3.
- Modify: `ocr_api/settings.py` — generic file-size setting with `MAX_FILE_BYTES` and `MAX_IMAGE_BYTES` compatibility.
- Modify: `README.md` — new API, request examples, raw-result behavior, image/PDF support.
- Modify: `docs/deploy-manual.md` and `docs/package-release.md` — active deployment/package references.
- Delete: `id_card_ocr/business_license.py`, `id_card_ocr/extractor.py`, `id_card_ocr/models.py`, `id_card_ocr/paddle_adapter.py`, `id_card_ocr/validator.py`, `id_card_ocr/__init__.py`.
- Delete: old document-specific tests and response/demo tests.
- Create: `tests/test_structure_adapter.py`, `tests/test_file_loader.py`.
- Modify: `tests/test_api_routes.py`, `tests/test_deployment_settings.py`.

### Task 1: Define the New Raw-Result Contract

**Files:**
- Create: `tests/test_structure_adapter.py`
- Create: `tests/test_file_loader.py`
- Modify: `tests/test_api_routes.py`

- [ ] **Step 1: Write failing adapter tests** for PP-StructureV3 initialization, `predict` input path usage, and conversion of a PaddleX-style `.json` property to JSON-safe dictionaries.
- [ ] **Step 2: Write failing file tests** for PNG, PDF, Base64 data URLs, and rejection of unsupported content.
- [ ] **Step 3: Rewrite route tests** so the generic and historical endpoints return fake raw results unchanged, PDF uploads are accepted, and the health endpoint plus unversioned 404 behavior remain unchanged.
- [ ] **Step 4: Run the focused tests** with `.\.venv\Scripts\python.exe -m unittest tests.test_structure_adapter tests.test_file_loader tests.test_api_routes -v`; expected result is failure because the new modules and route contract do not exist yet.

### Task 2: Implement PP-StructureV3 and File Loading

**Files:**
- Create: `ocr_api/adapter.py`
- Create: `ocr_api/file_loader.py`
- Modify: `ocr_api/settings.py`

- [ ] **Step 1: Implement lazy `PPStructureV3Adapter` initialization** with the existing runtime flags, configured device, Chinese language, document orientation, text-line orientation, table, formula, and chart recognition enabled.
- [ ] **Step 2: Implement raw result serialization** using PaddleX's `.json` property when present, recursively converting NumPy values, paths, mappings, lists, and tuples into standard JSON values.
- [ ] **Step 3: Implement bounded file decoding and URL download** for JPEG, PNG, BMP, WEBP, and PDF; validate images with Pillow, validate PDFs by `%PDF` magic, and materialize all inputs to temporary files with cleanup.
- [ ] **Step 4: Run the focused tests** and confirm all new adapter/file tests pass.

### Task 3: Implement FastAPI Raw JSON Routes

**Files:**
- Modify: `ocr_api/schemas.py`
- Modify: `ocr_api/responses.py`
- Modify: `ocr_api/routes.py`
- Modify: `api_app.py`

- [ ] **Step 1: Add `fileBase64` and `fileUrl` request fields**, retaining `imageBase64` and `imageUrl` as accepted aliases.
- [ ] **Step 2: Add `POST /api/v1/ocr/structure`** and route aliases for `/ocr/id-card` and `/ocr/business-license`; use one loader/adapter flow and return a single raw result for one-page input or a raw result list for multi-page PDF input.
- [ ] **Step 3: Keep the existing `/api/v1/health` function unchanged** and retain the existing error envelope for input/download/inference failures.
- [ ] **Step 4: Run route tests and compile checks**.

### Task 4: Rewrite the Streamlit Upload Tester

**Files:**
- Modify: `app.py`
- Modify: `scripts/preload-ocr.py`

- [ ] **Step 1: Replace document tabs and field summaries** with one upload control for supported image/PDF formats and a single recognition action.
- [ ] **Step 2: Reuse the temporary-file loader and cached PP-StructureV3 adapter**, show image previews when possible, and render the raw result JSON for images and PDFs.
- [ ] **Step 3: Update the preload script** to initialize `PPStructureV3Adapter`.
- [ ] **Step 4: Run compile checks for the app and script**.

### Task 5: Remove Obsolete Field Extraction and Documentation

**Files:**
- Delete: old `id_card_ocr` modules.
- Delete: old document-specific and response/demo tests.
- Modify: `README.md`, `docs/deploy-manual.md`, `docs/package-release.md`, `requirements.txt`, `requirements-prod.txt`.

- [ ] **Step 1: Delete document-specific extraction, validation, model, and adapter modules** after all imports have moved.
- [ ] **Step 2: Delete tests that assert ID-card/business-license field packaging** and update remaining tests to the generic contract.
- [ ] **Step 3: Update active documentation and dependency comments** to describe PP-StructureV3, image/PDF input, JSON requests, aliases, and Java-side parsing.
- [ ] **Step 4: Search the repository** for live imports/references to removed modules and old field endpoints; leave historical requirement/plan documents untouched unless they are active deployment instructions.

### Task 6: Full Verification

**Files:**
- No new production files.

- [ ] **Step 1: Run `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`.**
- [ ] **Step 2: Run `.\.venv\Scripts\python.exe -m compileall app.py api_app.py ocr_api scripts tests`.**
- [ ] **Step 3: Run a FastAPI TestClient smoke check for health, missing input, image Base64, and PDF Base64 with a fake adapter.
- [ ] **Step 4: Review `git diff --check`, `git status --short`, and confirm `.env.local`, `.git`, and health-check code were not modified.
