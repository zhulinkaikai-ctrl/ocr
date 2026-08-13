from __future__ import annotations

from fastapi import FastAPI

from ocr_api.routes import router


app = FastAPI(title="OCR API", version="0.1.0")
app.include_router(router)

