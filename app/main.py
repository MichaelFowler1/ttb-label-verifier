"""
FastAPI application: single + batch label verification, plus the static UI.

Endpoints
---------
GET  /                 -> the operator UI (static/index.html)
GET  /health           -> liveness probe
POST /api/verify       -> verify one label image against expected application fields
POST /api/verify-batch -> verify many images; optional CSV maps filename -> fields
"""
from __future__ import annotations

import csv
import io
import time
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from .ocr import ocr_image
from . import matching

app = FastAPI(title="TTB Label Verifier", version="1.0.0")

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

EXPECTED_KEYS = [
    "brand_name", "class_type", "alcohol_content",
    "net_contents", "producer", "country_of_origin",
]


def _clean(expected: dict) -> dict:
    return {k: v.strip() for k, v in expected.items() if v and str(v).strip()}


def _verify_bytes(data: bytes, expected: dict) -> dict:
    t0 = time.perf_counter()
    raw_text = ocr_image(data)
    result = matching.verify(expected, raw_text)
    result["elapsed_ms"] = int((time.perf_counter() - t0) * 1000)
    return result


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/verify")
async def verify(
    file: UploadFile = File(...),
    brand_name: str = Form(""),
    class_type: str = Form(""),
    alcohol_content: str = Form(""),
    net_contents: str = Form(""),
    producer: str = Form(""),
    country_of_origin: str = Form(""),
) -> dict:
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file upload.")
    expected = _clean({
        "brand_name": brand_name, "class_type": class_type,
        "alcohol_content": alcohol_content, "net_contents": net_contents,
        "producer": producer, "country_of_origin": country_of_origin,
    })
    try:
        result = _verify_bytes(data, expected)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Processing failed: {exc}")
    result["filename"] = file.filename
    return result


def _parse_csv(raw: bytes) -> dict:
    mapping = {}
    text = raw.decode("utf-8-sig", errors="ignore")
    reader = csv.DictReader(io.StringIO(text))
    for row in reader:
        row = {(k or "").strip().lower(): (v or "").strip() for k, v in row.items()}
        fname = row.get("filename")
        if not fname:
            continue
        mapping[fname] = _clean({k: row.get(k, "") for k in EXPECTED_KEYS})
    return mapping


@app.post("/api/verify-batch")
async def verify_batch(
    files: List[UploadFile] = File(...),
    mapping_csv: Optional[UploadFile] = File(None),
    brand_name: str = Form(""),
    class_type: str = Form(""),
    alcohol_content: str = Form(""),
    net_contents: str = Form(""),
    producer: str = Form(""),
    country_of_origin: str = Form(""),
) -> dict:
    csv_map = {}
    if mapping_csv is not None:
        csv_map = _parse_csv(await mapping_csv.read())
    shared = _clean({
        "brand_name": brand_name, "class_type": class_type,
        "alcohol_content": alcohol_content, "net_contents": net_contents,
        "producer": producer, "country_of_origin": country_of_origin,
    })
    results = []
    for f in files:
        expected = csv_map.get(f.filename, shared)
        try:
            data = await f.read()
            result = _verify_bytes(data, expected)
        except Exception as exc:
            result = {"overall_pass": False, "error": str(exc),
                      "fields": [], "warning": {}, "elapsed_ms": 0}
        result["filename"] = f.filename
        results.append(result)
    summary = {
        "total": len(results),
        "passed": sum(1 for r in results if r.get("overall_pass")),
        "failed": sum(1 for r in results if not r.get("overall_pass")),
    }
    return {"summary": summary, "results": results}
