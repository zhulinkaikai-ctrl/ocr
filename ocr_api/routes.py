from __future__ import annotations

import logging
from functools import lru_cache
from typing import Annotated, Any

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from .adapter import PPStructureV3Adapter
from .file_loader import (
    FileDownloadError,
    FileInputError,
    infer_serving_file_type,
    load_request_file,
    materialize_file,
)
from .schemas import LayoutParsingRequest
from .serving_response import build_error, build_success


logger = logging.getLogger(__name__)
router = APIRouter()


@lru_cache(maxsize=1)
def get_ocr_adapter() -> PPStructureV3Adapter:
    """Return the process-wide OCR adapter; tests override this FastAPI dependency."""
    return PPStructureV3Adapter(lang="ch", enable_orientation=True)


@router.get("/api/v1/health")
async def health() -> dict[str, int]:
    return {"status": 200}


@router.post("/layout-parsing")
async def layout_parsing(
    request: LayoutParsingRequest,
    adapter: Annotated[PPStructureV3Adapter, Depends(get_ocr_adapter)],
) -> JSONResponse:
    try:
        uploaded = await load_request_file(request.file, request.fileType)
    except FileInputError:
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=build_error(400, "Bad Request"),
        )
    except FileDownloadError:
        return JSONResponse(
            status_code=status.HTTP_502_BAD_GATEWAY,
            content=build_error(502, "Bad Gateway"),
        )

    try:
        with materialize_file(uploaded) as input_path:
            raw_results = adapter.recognize(input_path, **_predict_options(request))
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=build_success(raw_results, request.fileType or infer_serving_file_type(uploaded)),
        )
    except Exception:
        logger.exception("PP-StructureV3 layout parsing failed")
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=build_error(500, "Internal Server Error"),
        )


def _predict_options(request: LayoutParsingRequest) -> dict[str, Any]:
    options = {
        "use_doc_orientation_classify": request.useDocOrientationClassify,
        "use_doc_unwarping": request.useDocUnwarping,
        "use_textline_orientation": request.useTextlineOrientation,
        "use_seal_recognition": request.useSealRecognition,
        "use_table_recognition": request.useTableRecognition,
        "use_formula_recognition": request.useFormulaRecognition,
        "use_chart_recognition": request.useChartRecognition,
        "use_region_detection": request.useRegionDetection,
        "format_block_content": request.formatBlockContent,
    }
    return {key: value for key, value in options.items() if value is not None}
