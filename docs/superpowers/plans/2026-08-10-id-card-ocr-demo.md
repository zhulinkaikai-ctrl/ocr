# 身份证 OCR Demo Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Streamlit demo that uses PaddleOCR output to extract structured resident ID card fields.

**Architecture:** Keep OCR invocation separate from extraction and validation. The Streamlit UI calls a small service pipeline: uploaded image -> OCR adapter -> OCR line list -> ID-card extractor -> validation -> JSON-ready result.

**Tech Stack:** Python 3, Streamlit, PaddleOCR, Pillow, stdlib unittest.

---

## File Structure

- `app.py`: Streamlit page, upload handling, preview, fields display, JSON output.
- `id_card_ocr/models.py`: Dataclasses and constants for OCR lines, extracted fields, and document results.
- `id_card_ocr/validator.py`: ID number, date, and field status validation.
- `id_card_ocr/extractor.py`: ID-card side detection and field extraction from OCR lines.
- `id_card_ocr/paddle_adapter.py`: PaddleOCR lazy initialization and version-tolerant result normalization.
- `tests/test_validator.py`: Tests for ID-number and date validation.
- `tests/test_extractor.py`: Tests for front/back side extraction and JSON shape.
- `requirements.txt`: Runtime dependencies.
- `README.md`: Local setup and run instructions.

## Tasks

### Task 1: Write Failing Tests

**Files:**
- Create: `tests/test_validator.py`
- Create: `tests/test_extractor.py`

- [ ] Add tests for ID-number checksum, invalid checksum, date validation, front-side extraction, back-side extraction, and JSON field shape.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Expected: tests fail because `id_card_ocr` modules do not exist yet.

### Task 2: Implement Core Logic

**Files:**
- Create: `id_card_ocr/__init__.py`
- Create: `id_card_ocr/models.py`
- Create: `id_card_ocr/validator.py`
- Create: `id_card_ocr/extractor.py`

- [ ] Add dataclasses for `OCRLine`, `ExtractedField`, and `IDCardResult`.
- [ ] Implement resident ID checksum and date validation.
- [ ] Implement front/back detection from keywords.
- [ ] Implement rule-based field extraction from PaddleOCR text lines.
- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Expected: tests pass.

### Task 3: Add PaddleOCR Adapter And UI

**Files:**
- Create: `id_card_ocr/paddle_adapter.py`
- Create: `app.py`
- Create: `requirements.txt`
- Create: `README.md`

- [ ] Add lazy PaddleOCR initialization with angle/orientation support.
- [ ] Normalize PaddleOCR 3.x `predict` results and 2.x `ocr(..., cls=True)` results into `OCRLine` instances.
- [ ] Build Streamlit UI with upload, preview, read-only field table, validation badges, raw OCR text, and copyable JSON.
- [ ] Add local setup commands to README.

### Task 4: Verify

**Files:**
- All created files.

- [ ] Run `python -m unittest discover -s tests -v`.
- [ ] Run `python -m compileall app.py id_card_ocr tests`.
- [ ] If Streamlit/PaddleOCR are installed locally, run `streamlit run app.py`.
