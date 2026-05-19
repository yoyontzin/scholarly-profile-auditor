"""Rutas FastAPI para servir el widget y procesar auditorías."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import JSONResponse

from app.core.logging import get_logger
from app.services.exports import export_widget_data
from app.services.pipeline import PipelineInput, run_pipeline

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["audit"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@router.post("/audit")
async def audit(
    orcid: str = Form(...),
    scholar_url: str | None = Form(None),
    area_snii: str | None = Form(None),
    refs: UploadFile | None = File(None),
) -> JSONResponse:
    """Ejecuta el pipeline y devuelve el contenido del widget/data.json."""
    refs_path: Path | None = None
    if refs and refs.filename:
        suffix = Path(refs.filename).suffix or ".bib"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(await refs.read())
        tmp.close()
        refs_path = Path(tmp.name)

    try:
        inp = PipelineInput(
            orcid=orcid.strip(),
            scholar_url=scholar_url,
            user_refs_path=refs_path,
            area_snii=area_snii,
        )
        result = await run_pipeline(inp)
    except Exception as e:  # noqa: BLE001
        logger.exception("Auditoría falló")
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Escribir widget/data.json en un dir temp y leerlo de vuelta
    with tempfile.TemporaryDirectory() as tmpdir:
        data_path = export_widget_data(result, Path(tmpdir))
        payload = json.loads(data_path.read_text(encoding="utf-8"))
    return JSONResponse(payload)
