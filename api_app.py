from __future__ import annotations

from fastapi import FastAPI

from ocr_api.routes import router

# FastAPI 服务入口。启动命令：
# uvicorn api_app:app --host 0.0.0.0 --port 8000
app = FastAPI(title="OCR API", version="0.1.0")
app.include_router(router)
