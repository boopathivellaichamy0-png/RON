# AcroText Precision - PDF & Image Text Editor

A full-stack precision PDF and image text editor designed to replace text seamlessly across both digital vector PDFs and scanned image/terminal documents while preserving surrounding typography, colors, borders, and backgrounds.

---

## 🚀 Key Features

- **Digital Vector PDF Editing:**
  - Direct PDF text layer manipulation using PyMuPDF (`fitz`).
  - Font family, weight (bold/regular), size, and exact ink color preservation.
  - Sentence context preservation: selectively replaces specific words without reflowing or distorting neighboring text.

- **Scanned & Terminal Image Text Inpainting:**
  - AI-assisted OCR with **dual-pass adaptive inversion detection** to capture low-contrast, small, and dark terminal text.
  - Word-level tokenization: isolates words from punctuation and symbols (e.g., handles `@`, `()`, `[]`, paths, and symbols individually).
  - High-fidelity inpainting with texture synthesis, border feathering, and Consolas monospace rendering for terminal screenshots.

- **Whole-Document Search & Replace:**
  - Document-wide multi-page analysis in under 1 second.
  - Substring and multi-word matching across full lines.
  - Multi-threaded page processing with in-memory OCR and image caching for 60 FPS continuous scrolling.

- **Persistent Drag Box Tool:**
  - Single-click activation stays active continuously for drawing bounding boxes over any missed or low-clarity text without re-clicking.
  - Automatic background and ink color sampling.

---

## 🛠️ Architecture

```
pdf-editor/
├── backend/
│   ├── main.py              # FastAPI endpoints, caching layer, and static file mount
│   ├── ocr_engine.py        # Dual-pass RapidOCR with adaptive thresholding
│   ├── inpaint_engine.py    # Texture synthesis, OpenCV inpainting, typography rendering
│   ├── pdf_processor.py     # PyMuPDF vector extraction, coordinate conversion, rendering
│   ├── sample_generator.py  # Auto-generates test PDFs (digital, scanned, terminal)
│   └── uploads/             # Sample and document storage
├── frontend/
│   ├── src/
│   │   ├── App.jsx          # Interactive editor UI, continuous canvas, draw tools
│   │   └── main.jsx
│   ├── package.json
│   ├── vite.config.js
│   └── dist/                # Pre-built production frontend bundle
├── test_suite.py            # Comprehensive 6-part end-to-end integration test suite
├── requirements.txt         # Python dependencies
└── README.md
```

---

## 🚦 Quick Start

### 1. Backend Setup
```bash
cd backend
pip install -r ../requirements.txt
python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

### 2. Frontend Setup (Optional - pre-built in `frontend/dist`)
```bash
cd frontend
npm install
npm run build
```

Open your browser at **`http://localhost:8000`** to start editing.

---

## 🧪 Verification Tests

Run the included verification test suite:
```bash
python test_suite.py
```
Validates:
1. Exact word replacement in sentences
2. Colored banner preservation
3. Typography and font styling
4. Scanned image word inpainting
5. Multi-occurrence replacement
6. PDF export integrity
