import os
import uuid
import shutil
import fitz
import cv2
import re
import numpy as np
import concurrent.futures
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Optional, Any

from pdf_processor import PDFProcessor
from ocr_engine import OCREngine
from inpaint_engine import InpaintEngine
from sample_generator import create_sample_documents

app = FastAPI(title="Precision PDF & Image Text Editor API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
UPLOADS_DIR = os.path.join(BASE_DIR, "uploads")
MODIFIED_DIR = os.path.join(BASE_DIR, "modified")

os.makedirs(UPLOADS_DIR, exist_ok=True)
os.makedirs(MODIFIED_DIR, exist_ok=True)

# Generate sample documents
create_sample_documents(UPLOADS_DIR)

pdf_processor = PDFProcessor(upload_dir=UPLOADS_DIR)
ocr_engine = OCREngine()
inpaint_engine = InpaintEngine()

active_docs = {}

# Performance In-Memory Caches
OCR_CACHE = {}          # (file_path, page_num, mtime) -> ocr_res dict
PAGE_IMAGE_CACHE = {}   # (file_path, page_num, dpi, mtime) -> bytes

def get_cached_page_image(file_path: str, page_num: int, dpi: int = 150) -> bytes:
    try:
        mtime = os.path.getmtime(file_path)
    except Exception:
        mtime = 0
    cache_key = (file_path, page_num, dpi, mtime)
    if cache_key in PAGE_IMAGE_CACHE:
        return PAGE_IMAGE_CACHE[cache_key]

    img_bytes = pdf_processor.render_page(file_path, page_num, dpi=dpi)
    if len(PAGE_IMAGE_CACHE) > 300:
        PAGE_IMAGE_CACHE.clear()
    PAGE_IMAGE_CACHE[cache_key] = img_bytes
    return img_bytes

def get_cached_ocr(file_path: str, page_num: int, width_pt: float, height_pt: float):
    try:
        mtime = os.path.getmtime(file_path)
    except Exception:
        mtime = 0
    cache_key = (file_path, page_num, mtime)
    if cache_key in OCR_CACHE:
        return OCR_CACHE[cache_key]

    img_bytes = get_cached_page_image(file_path, page_num, dpi=150)
    ocr_res = ocr_engine.process_image(img_bytes, pdf_width_pt=width_pt, pdf_height_pt=height_pt)
    if len(OCR_CACHE) > 200:
        OCR_CACHE.clear()
    OCR_CACHE[cache_key] = ocr_res
    return ocr_res

# Register existing samples
linux_sample_path = os.path.join(UPLOADS_DIR, "sample_linux_terminal.pdf")
if os.path.exists(linux_sample_path):
    try:
        doc_info = pdf_processor.load_document(linux_sample_path)
        active_docs["sample_linux_terminal"] = {
            "file_path": linux_sample_path,
            "current_path": linux_sample_path,
            "filename": "sample_linux_terminal.pdf",
            "page_count": doc_info["page_count"]
        }
    except Exception:
        pass

digital_sample_path = os.path.join(UPLOADS_DIR, "sample_digital_contract.pdf")
if os.path.exists(digital_sample_path):
    active_docs["sample_digital"] = {
        "file_path": digital_sample_path,
        "current_path": digital_sample_path,
        "filename": "sample_digital_contract.pdf",
        "page_count": 1
    }

scanned_sample_path = os.path.join(UPLOADS_DIR, "sample_scanned_receipt.pdf")
if os.path.exists(scanned_sample_path):
    active_docs["sample_scanned"] = {
        "file_path": scanned_sample_path,
        "current_path": scanned_sample_path,
        "filename": "sample_scanned_receipt.pdf",
        "page_count": 1
    }

def get_doc_entry(doc_id: str):
    if doc_id in active_docs:
        return active_docs[doc_id]
    if doc_id == "sample_linux_terminal":
        linux_path = os.path.join(UPLOADS_DIR, "sample_linux_terminal.pdf")
        if os.path.exists(linux_path):
            doc_info = pdf_processor.load_document(linux_path)
            entry = {
                "file_path": linux_path,
                "current_path": linux_path,
                "filename": "sample_linux_terminal.pdf",
                "page_count": doc_info["page_count"]
            }
            active_docs[doc_id] = entry
            return entry
    # Check if uploaded file exists on disk with this doc_id
    if os.path.exists(UPLOADS_DIR):
        for fname in os.listdir(UPLOADS_DIR):
            if fname.startswith(f"{doc_id}_") and fname.endswith(".pdf"):
                fpath = os.path.join(UPLOADS_DIR, fname)
                try:
                    doc_info = pdf_processor.load_document(fpath)
                    entry = {
                        "file_path": fpath,
                        "current_path": fpath,
                        "filename": fname.split("_", 1)[1] if "_" in fname else fname,
                        "page_count": doc_info["page_count"]
                    }
                    active_docs[doc_id] = entry
                    return entry
                except Exception:
                    pass
    return None

class SearchMatchRequest(BaseModel):
    doc_id: str
    page_num: Optional[int] = 0
    query: str
    replace_with: Optional[str] = ""
    whole_word: Optional[bool] = True
    all_pages: Optional[bool] = False

class SampleAreaRequest(BaseModel):
    doc_id: str
    page_num: int
    pixel_bbox: List[float]
    dpi: Optional[int] = 150

class UnifiedReplacementItem(BaseModel):
    id: str
    type: str  # "vector" or "image_ocr" or "manual"
    page: int
    original_text: str
    new_text: str
    pdf_bbox: List[float]     # [x0, y0, x1, y1] in PDF points
    pixel_bbox: List[float]   # [x0, y0, x1, y1] in preview pixels
    font_name: Optional[str] = "helv"
    font_type: Optional[str] = "sans"
    font_size: Optional[float] = 12.0
    font_color: Optional[str] = "#000000"
    bg_color: Optional[str] = "#ffffff"
    inpaint: Optional[bool] = True

class UnifiedReplacementRequest(BaseModel):
    doc_id: str
    page_num: Optional[int] = 0
    replacements: List[UnifiedReplacementItem]
    render_dpi: Optional[int] = 200

@app.get("/api/health")
def health_check():
    return {"status": "ok", "service": "Precision PDF & Image Text Editor"}

@app.get("/api/doc/{doc_id}/info")
def get_doc_info(doc_id: str):
    entry = get_doc_entry(doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")
    return {
        "doc_id": doc_id,
        "filename": entry["filename"],
        "page_count": entry["page_count"]
    }

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    doc_id = str(uuid.uuid4())
    filename = file.filename
    ext = os.path.splitext(filename)[1].lower()

    if ext not in [".pdf", ".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp"]:
        raise HTTPException(status_code=400, detail="Only PDF and standard image formats are supported")

    dest_path = os.path.join(UPLOADS_DIR, f"{doc_id}_{filename}")
    with open(dest_path, "wb") as f:
        content = await file.read()
        f.write(content)

    if ext != ".pdf":
        converted_pdf_path = os.path.join(UPLOADS_DIR, f"{doc_id}_converted.pdf")
        doc = fitz.open()
        img = Image.open(dest_path)
        img_w, img_h = img.size
        pt_w = (img_w / 150.0) * 72.0
        pt_h = (img_h / 150.0) * 72.0
        page = doc.new_page(width=pt_w, height=pt_h)
        page.insert_image(fitz.Rect(0, 0, pt_w, pt_h), filename=dest_path)
        doc.save(converted_pdf_path)
        doc.close()
        dest_path = converted_pdf_path

    doc_info = pdf_processor.load_document(dest_path)
    active_docs[doc_id] = {
        "file_path": dest_path,
        "current_path": dest_path,
        "filename": filename,
        "page_count": doc_info["page_count"]
    }

    return {
        "doc_id": doc_id,
        "filename": filename,
        "page_count": doc_info["page_count"]
    }

@app.get("/api/doc/{doc_id}/page/{page_num}")
def get_page_data(doc_id: str, page_num: int, include_ocr: bool = False):
    entry = get_doc_entry(doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")

    current_path = entry["current_path"]

    try:
        vector_data = pdf_processor.extract_vector_text_blocks(current_path, page_num)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    ocr_data = None
    has_vector = len(vector_data["blocks"]) > 0

    try:
        mtime = os.path.getmtime(current_path)
    except Exception:
        mtime = 0

    # Fast path: check if OCR is already cached in memory
    cached_ocr = OCR_CACHE.get((current_path, page_num, mtime))
    if cached_ocr:
        ocr_data = cached_ocr
    elif include_ocr or not has_vector:
        # Only run OCR when explicitly requested or when page is purely scanned (no vector text)
        try:
            ocr_data = get_cached_ocr(
                current_path, page_num, vector_data["page_width"], vector_data["page_height"]
            )
        except Exception as e:
            ocr_data = {"error": str(e), "boxes": [], "words": []}

    return {
        "doc_id": doc_id,
        "page_num": page_num,
        "page_width": vector_data["page_width"],
        "page_height": vector_data["page_height"],
        "has_vector_text": has_vector,
        "vector_blocks": vector_data["blocks"],
        "vector_words": vector_data.get("words", []),
        "ocr_data": ocr_data
    }

@app.get("/api/doc/{doc_id}/page-image/{page_num}")
def get_page_image(doc_id: str, page_num: int, dpi: int = 150):
    entry = get_doc_entry(doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")

    current_path = entry["current_path"]
    try:
        img_bytes = get_cached_page_image(current_path, page_num, dpi=dpi)
        etag = f'"{abs(hash((current_path, page_num, dpi)))}"'
        return Response(
            content=img_bytes,
            media_type="image/png",
            headers={
                "Cache-Control": "public, max-age=86400, stale-while-revalidate=86400",
                "ETag": etag
            }
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/doc/{doc_id}/run-ocr/{page_num}")
def run_page_ocr(doc_id: str, page_num: int, dpi: int = 150):
    entry = get_doc_entry(doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")

    current_path = entry["current_path"]
    try:
        doc = fitz.open(current_path)
        page = doc[page_num]
        rect = page.rect
        doc.close()

        ocr_res = get_cached_ocr(current_path, page_num, rect.width, rect.height)
        return ocr_res
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search-and-match")
def search_and_match(req: SearchMatchRequest):
    entry = get_doc_entry(req.doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")

    query = req.query.strip()
    if not query:
        return {"matches": []}

    current_path = entry["current_path"]
    total_pages = entry.get("page_count", 1)
    target_pages = list(range(total_pages)) if req.all_pages else [req.page_num]

    matches = []
    scale = 150.0 / 72.0

    # 1. Fast Vector search across all target pages (<20ms total)
    for p_num in target_pages:
        try:
            vector_matches = pdf_processor.search_vector_occurrences(
                current_path, p_num, query, whole_word=req.whole_word
            )
            for vm in vector_matches:
                bbox = vm["bbox"]
                px_bbox = [round(c * scale, 1) for c in bbox]
                matches.append({
                    "id": vm["id"],
                    "type": "vector",
                    "page": p_num,
                    "original_text": vm["matched_text"],
                    "new_text": req.replace_with,
                    "pdf_bbox": bbox,
                    "pixel_bbox": px_bbox,
                    "span_text": vm.get("span_text", ""),
                    "font_name": vm["font"],
                    "font_type": vm["font_type"],
                    "font_size": vm["size"],
                    "font_color": vm["color"],
                    "bg_color": vm["bg_color"],
                    "inpaint": False
                })
        except Exception:
            pass

    # 2. Smart OCR search
    # If vector search already found matches and user searched across all pages of a digital PDF,
    # we don't need to burn CPU running OCR across every page.
    try:
        mtime = os.path.getmtime(current_path)
    except Exception:
        mtime = 0

    doc = fitz.open(current_path)
    ocr_pages_to_check = []

    for p_num in target_pages:
        page = doc[p_num]
        has_vec = len(page.get_text().strip()) > 0
        has_imgs = len(page.get_images()) > 0
        is_cached = (current_path, p_num, mtime) in OCR_CACHE

        # Analyze every page across the whole document that contains images, is scanned, or is cached
        if is_cached or has_imgs or not has_vec:
            ocr_pages_to_check.append((p_num, is_cached, page.rect.width, page.rect.height))

    doc.close()

    def process_ocr_page_matches(p_num, w_pt, h_pt):
        page_matches = []
        try:
            ocr_res = get_cached_ocr(current_path, p_num, w_pt, h_pt)
            for line_item in ocr_res.get("boxes", []):
                line_text = line_item["text"]
                if req.whole_word and query.isalnum() and ' ' not in query:
                    pattern = r'\b' + re.escape(query) + r'\b'
                    m_iter = list(re.finditer(pattern, line_text, re.IGNORECASE))
                    if not m_iter and query.lower() in line_text.lower():
                        m_iter = list(re.finditer(re.escape(query), line_text, re.IGNORECASE))
                else:
                    m_iter = list(re.finditer(re.escape(query), line_text, re.IGNORECASE))

                for m in m_iter:
                    line_len = max(1, len(line_text))
                    raw_box = line_item["pixel_bbox"]
                    raw_w = raw_box[2] - raw_box[0]
                    sub_x0 = raw_box[0] + (m.start() / line_len) * raw_w
                    sub_x1 = raw_box[0] + (m.end() / line_len) * raw_w
                    sub_x1 = max(sub_x0 + 6, sub_x1)

                    px_bbox = [round(sub_x0, 1), round(raw_box[1], 1), round(sub_x1, 1), round(raw_box[3], 1)]
                    bg_hex = line_item.get("bg_color", "#ffffff")
                    bg_r = int(bg_hex[1:3], 16) if len(bg_hex) == 7 else 255
                    bg_g = int(bg_hex[3:5], 16) if len(bg_hex) == 7 else 255
                    bg_b = int(bg_hex[5:7], 16) if len(bg_hex) == 7 else 255
                    bg_lum = 0.299 * bg_r + 0.587 * bg_g + 0.114 * bg_b
                    is_terminal = bg_lum < 120 or any(sym in line_text for sym in ['@', '~', '$', '[', ']', '/'])

                    pt_scale = 72.0 / 150.0
                    pdf_bbox = [round(c * pt_scale, 2) for c in px_bbox]

                    page_matches.append({
                        "id": f"ocr_match_{uuid.uuid4().hex[:6]}",
                        "type": "image_ocr",
                        "page": p_num,
                        "original_text": m.group(),
                        "new_text": req.replace_with,
                        "pdf_bbox": pdf_bbox,
                        "pixel_bbox": px_bbox,
                        "span_text": line_text,
                        "font_name": "Consolas" if is_terminal else "Arial",
                        "font_type": "mono" if is_terminal else ("bold" if "bold" in line_text.lower() else "sans"),
                        "font_size": line_item.get("est_font_size", 12.0),
                        "font_color": line_item.get("color", "#000000"),
                        "bg_color": bg_hex,
                        "inpaint": True
                    })
        except Exception:
            pass
        return page_matches

    # Process pages using ThreadPool for maximum parallelism across the whole document
    if ocr_pages_to_check:
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
            future_to_page = {
                executor.submit(process_ocr_page_matches, p_num, w_pt, h_pt): p_num
                for p_num, _, w_pt, h_pt in ocr_pages_to_check
            }
            for future in concurrent.futures.as_completed(future_to_page):
                page_matches = future.result()
                matches.extend(page_matches)

    # Sort all matches in reading order across the entire document
    matches.sort(key=lambda m: (m["page"], m["pixel_bbox"][1], m["pixel_bbox"][0]))

    return {
        "query": query,
        "replace_with": req.replace_with,
        "matches": matches,
        "count": len(matches)
    }

@app.post("/api/sample-area")
def sample_area(req: SampleAreaRequest):
    entry = get_doc_entry(req.doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")

    current_path = entry["current_path"]

    img_bytes = pdf_processor.render_page(current_path, req.page_num, dpi=req.dpi)
    nparr = np.frombuffer(img_bytes, np.uint8)
    img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

    style_info = inpaint_engine.sample_area_style(img_bgr, req.pixel_bbox)

    pt_scale = 72.0 / req.dpi
    pdf_bbox = [round(c * pt_scale, 2) for c in req.pixel_bbox]

    return {
        "pixel_bbox": req.pixel_bbox,
        "pdf_bbox": pdf_bbox,
        "style": style_info
    }

@app.post("/api/apply-replacements")
def apply_replacements(req: UnifiedReplacementRequest):
    entry = get_doc_entry(req.doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")

    current_path = entry["current_path"]

    vector_edits = []
    image_edits_by_page = {}

    for item in req.replacements:
        if item.type == "vector":
            vector_edits.append({
                "page": item.page,
                "bbox": item.pdf_bbox,
                "pdf_bbox": item.pdf_bbox,
                "original_text": item.original_text,
                "new_text": item.new_text,
                "font": item.font_name,
                "size": item.font_size,
                "color": item.font_color,
                "bg_color": item.bg_color or "#ffffff"
            })
        else:
            p = item.page
            if p not in image_edits_by_page:
                image_edits_by_page[p] = []
            image_edits_by_page[p].append(item)

    # Apply vector edits
    if vector_edits:
        v_out = os.path.join(MODIFIED_DIR, f"vmod_{uuid.uuid4().hex[:8]}.pdf")
        pdf_processor.apply_vector_edits(current_path, vector_edits, v_out)
        current_path = v_out
        entry["current_path"] = current_path

    # Apply image OCR inpainting edits across all requested pages
    if image_edits_by_page:
        dpi = 150
        scale_factor = 1.0

        doc = fitz.open(current_path)
        new_doc = fitz.open()

        for idx in range(len(doc)):
            if idx in image_edits_by_page:
                img_bytes = pdf_processor.render_page(current_path, idx, dpi=dpi)
                nparr = np.frombuffer(img_bytes, np.uint8)
                img_bgr = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                scaled_image_edits = []
                for item in image_edits_by_page[idx]:
                    pb = item.pixel_bbox
                    scaled_image_edits.append({
                        "pixel_bbox": [round(c * scale_factor, 1) for c in pb],
                        "original_text": item.original_text,
                        "new_text": item.new_text,
                        "font_size": round((item.font_size or 16) * scale_factor, 1),
                        "font_color": item.font_color,
                        "font_type": item.font_type,
                        "bg_color": item.bg_color,
                        "inpaint": item.inpaint
                    })

                modified_bgr = inpaint_engine.inpaint_and_replace(img_bgr, scaled_image_edits)
                temp_img_path = os.path.join(MODIFIED_DIR, f"temp_inpaint_{uuid.uuid4().hex[:8]}.png")
                cv2.imwrite(temp_img_path, modified_bgr)

                target_page = doc[idx]
                p_w, p_h = target_page.rect.width, target_page.rect.height
                np_page = new_doc.new_page(width=p_w, height=p_h)
                np_page.insert_image(fitz.Rect(0, 0, p_w, p_h), filename=temp_img_path)

                if os.path.exists(temp_img_path):
                    try:
                        os.remove(temp_img_path)
                    except Exception:
                        pass
            else:
                new_doc.insert_pdf(doc, from_page=idx, to_page=idx)

        doc.close()
        final_out = os.path.join(MODIFIED_DIR, f"final_{uuid.uuid4().hex[:8]}_{entry['filename']}")
        new_doc.save(final_out, garbage=3, deflate=True)
        new_doc.close()
        entry["current_path"] = final_out

    return {
        "status": "success",
        "message": f"Successfully replaced {len(req.replacements)} occurrence(s) preserving surrounding layout and design!",
        "current_path": entry["current_path"]
    }

@app.post("/api/reset-doc/{doc_id}")
def reset_document(doc_id: str):
    entry = get_doc_entry(doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")

    entry["current_path"] = entry["file_path"]
    return {"status": "success", "message": "Document reset to original version"}

@app.get("/api/download/{doc_id}")
def download_document(doc_id: str):
    entry = get_doc_entry(doc_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Document not found")

    current_path = entry["current_path"]
    filename = entry["filename"]
    if not filename.endswith(".pdf"):
        filename += ".pdf"

    return FileResponse(
        current_path,
        media_type="application/pdf",
        filename=f"edited_{filename}"
    )

frontend_dist = os.path.join(PROJECT_DIR, "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
