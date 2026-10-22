import cv2, os, json, fitz, sys
import numpy as np

backend_dir = r'C:\Users\Admin\.gemini\antigravity\scratch\pdf-editor\backend'
sys.path.append(backend_dir)
uploads = os.path.join(backend_dir, 'uploads')
demo_dir = r'C:\Users\Admin\.gemini\antigravity\scratch\pdf-editor\frontend\public\demo_data'
os.makedirs(demo_dir, exist_ok=True)

# Clear old demo files
for f in os.listdir(demo_dir):
    try:
        os.remove(os.path.join(demo_dir, f))
    except Exception:
        pass

from pdf_processor import PDFProcessor
from ocr_engine import OCREngine

proc = PDFProcessor(upload_dir=uploads)
ocr = OCREngine()

# 1. Digital contract
d_path = os.path.join(uploads, 'sample_digital_contract.pdf')
if os.path.exists(d_path):
    img_b = proc.render_page(d_path, 0, dpi=120)
    img = cv2.imdecode(np.frombuffer(img_b, np.uint8), cv2.IMREAD_COLOR)
    cv2.imwrite(os.path.join(demo_dir, 'sample_digital_page_0.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
    with open(os.path.join(demo_dir, 'sample_digital_page_0.json'), 'w') as f:
        json.dump(proc.extract_vector_text_blocks(d_path, 0), f)

# 2. Scanned receipt
s_path = os.path.join(uploads, 'sample_scanned_receipt.pdf')
if os.path.exists(s_path):
    img_b = proc.render_page(s_path, 0, dpi=120)
    img = cv2.imdecode(np.frombuffer(img_b, np.uint8), cv2.IMREAD_COLOR)
    cv2.imwrite(os.path.join(demo_dir, 'sample_scanned_page_0.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 75])
    with open(os.path.join(demo_dir, 'sample_scanned_page_0.json'), 'w') as f:
        json.dump(ocr.process_image(img), f)

# 3. Linux terminal pages 0, 1, 7
l_path = os.path.join(uploads, 'sample_linux_terminal.pdf')
if os.path.exists(l_path):
    doc = fitz.open(l_path)
    for p in [0, 1, 7]:
        img_b = proc.render_page(l_path, p, dpi=120)
        img = cv2.imdecode(np.frombuffer(img_b, np.uint8), cv2.IMREAD_COLOR)
        cv2.imwrite(os.path.join(demo_dir, f'sample_linux_page_{p}.jpg'), img, [cv2.IMWRITE_JPEG_QUALITY, 80])
        with open(os.path.join(demo_dir, f'sample_linux_page_{p}.json'), 'w') as f:
            json.dump(proc.extract_vector_text_blocks(l_path, p), f)

total_kb = sum(os.path.getsize(os.path.join(demo_dir, f)) for f in os.listdir(demo_dir)) / 1024
print(f"Total demo_data size: {total_kb:.1f} KB!")
for f in os.listdir(demo_dir):
    print(f"  {f}: {os.path.getsize(os.path.join(demo_dir, f)) / 1024:.1f} KB")
