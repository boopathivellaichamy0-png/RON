import fitz
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont
import os

def create_sample_documents(output_dir="uploads"):
    os.makedirs(output_dir, exist_ok=True)
    digital_pdf_path = os.path.join(output_dir, "sample_digital_contract.pdf")
    scanned_pdf_path = os.path.join(output_dir, "sample_scanned_receipt.pdf")

    # 1. Generate High-Quality Digital Vector PDF
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4 standard

    # Draw header rect
    page.draw_rect(fitz.Rect(50, 40, 545, 95), color=None, fill=(0.08, 0.22, 0.45))
    page.insert_text(fitz.Point(65, 75), "GLOBAL SERVICES CONTRACT", fontname="hebo", fontsize=18, color=(1, 1, 1))
    
    # Contract Info
    page.insert_text(fitz.Point(50, 130), "CONTRACT ID: GSC-2026-8891", fontname="hebo", fontsize=12, color=(0.1, 0.1, 0.1))
    page.insert_text(fitz.Point(50, 150), "DATE: October 09, 2026", fontname="helv", fontsize=11, color=(0.3, 0.3, 0.3))
    page.insert_text(fitz.Point(50, 170), "CLIENT: Horizon Innovations Corp", fontname="helv", fontsize=11, color=(0.1, 0.1, 0.1))
    page.insert_text(fitz.Point(50, 190), "CONSULTANT: Apex Technologies Ltd", fontname="helv", fontsize=11, color=(0.1, 0.1, 0.1))

    # Divider line
    page.draw_line(fitz.Point(50, 215), fitz.Point(545, 215), color=(0.8, 0.8, 0.8), width=1)

    # Paragraph text
    page.insert_text(fitz.Point(50, 245), "1. Scope of Deliverables", fontname="hebo", fontsize=13, color=(0.08, 0.22, 0.45))
    page.insert_text(fitz.Point(50, 270), "The Consultant agrees to deliver the enterprise cloud architecture migration plan", fontname="helv", fontsize=11, color=(0.2, 0.2, 0.2))
    page.insert_text(fitz.Point(50, 290), "and supervise the deployment pipeline through Q4 fiscal cycle with 99.99% uptime.", fontname="helv", fontsize=11, color=(0.2, 0.2, 0.2))

    page.insert_text(fitz.Point(50, 330), "2. Compensation and Milestones", fontname="hebo", fontsize=13, color=(0.08, 0.22, 0.45))
    page.insert_text(fitz.Point(50, 355), "Milestone A: Architecture Assessment - $15,000.00 USD (Completed)", fontname="helv", fontsize=11, color=(0.2, 0.2, 0.2))
    page.insert_text(fitz.Point(50, 375), "Milestone B: Security Compliance & Audit - $25,000.00 USD (Pending Review)", fontname="helv", fontsize=11, color=(0.2, 0.2, 0.2))
    page.insert_text(fitz.Point(50, 395), "Total Payable: $40,000.00 USD within 30 days of invoice date.", fontname="hebo", fontsize=11, color=(0.05, 0.4, 0.15))

    page.insert_text(fitz.Point(50, 440), "3. Confidentiality & Non-Disclosure", fontname="hebo", fontsize=13, color=(0.08, 0.22, 0.45))
    page.insert_text(fitz.Point(50, 465), "All proprietary data shall be retained strictly confidential under NDA schedule 4.", fontname="helv", fontsize=11, color=(0.2, 0.2, 0.2))
    
    # Signature block
    page.draw_rect(fitz.Rect(50, 520, 270, 600), color=(0.7, 0.7, 0.7), width=1)
    page.insert_text(fitz.Point(60, 545), "Authorized Representative:", fontname="helv", fontsize=10, color=(0.4, 0.4, 0.4))
    page.insert_text(fitz.Point(60, 575), "Marcus Vance (Managing Director)", fontname="hebo", fontsize=11, color=(0.1, 0.1, 0.1))

    doc.save(digital_pdf_path)
    doc.close()

    # 2. Generate Realistic Scanned Image PDF
    # Create image on canvas with subtle paper texture, noise, and rasterized text
    img_w, img_h = 1200, 1600
    # Slightly aged paper color (RGB ~ 250, 248, 242)
    paper = np.full((img_h, img_w, 3), (242, 248, 250), dtype=np.uint8)  # BGR
    # Add subtle grain noise
    noise = np.random.normal(0, 3.5, (img_h, img_w, 3)).astype(np.int16)
    paper = np.clip(paper.astype(np.int16) + noise, 0, 255).astype(np.uint8)

    # Convert to PIL to draw text
    pil_img = Image.fromarray(cv2.cvtColor(paper, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    try:
        font_large = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 38)
        font_med_bold = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 26)
        font_med = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 24)
        font_small = ImageFont.truetype("C:/Windows/Fonts/cour.ttf", 22)
    except Exception:
        font_large = font_med_bold = font_med = font_small = ImageFont.load_default()

    # Draw scanned receipt / invoice
    draw.text((100, 100), "OFFICIAL TAX INVOICE", fill=(30, 30, 30), font=font_large)
    draw.text((100, 160), "INVOICE NO: INV-99214-X", fill=(50, 50, 50), font=font_med_bold)
    draw.text((100, 205), "ISSUED TO: ACME SUPPLIES INC", fill=(60, 60, 60), font=font_med)
    draw.text((100, 245), "BILLING DATE: 18-SEPTEMBER-2026", fill=(60, 60, 60), font=font_med)
    draw.text((100, 285), "PAYMENT STATUS: PAID IN FULL", fill=(20, 100, 30), font=font_med_bold)

    # Line item entries
    draw.line([(100, 340), (1100, 340)], fill=(150, 150, 150), width=2)
    draw.text((100, 360), "ITEM DESCRIPTION", fill=(40, 40, 40), font=font_med_bold)
    draw.text((700, 360), "QTY", fill=(40, 40, 40), font=font_med_bold)
    draw.text((950, 360), "AMOUNT", fill=(40, 40, 40), font=font_med_bold)
    draw.line([(100, 405), (1100, 405)], fill=(150, 150, 150), width=2)

    draw.text((100, 430), "Heavy Duty Server Rack Units", fill=(50, 50, 50), font=font_small)
    draw.text((700, 430), "4", fill=(50, 50, 50), font=font_small)
    draw.text((950, 430), "$3,200.00", fill=(50, 50, 50), font=font_small)

    draw.text((100, 480), "High-Speed Optical Transceivers", fill=(50, 50, 50), font=font_small)
    draw.text((700, 480), "12", fill=(50, 50, 50), font=font_small)
    draw.text((950, 480), "$1,440.00", fill=(50, 50, 50), font=font_small)

    draw.text((100, 530), "Onsite Installation & Calibration", fill=(50, 50, 50), font=font_small)
    draw.text((700, 530), "1", fill=(50, 50, 50), font=font_small)
    draw.text((950, 530), "$850.00", fill=(50, 50, 50), font=font_small)

    draw.line([(100, 600), (1100, 600)], fill=(150, 150, 150), width=2)
    draw.text((650, 630), "SUBTOTAL:", fill=(40, 40, 40), font=font_med_bold)
    draw.text((950, 630), "$5,490.00", fill=(40, 40, 40), font=font_med_bold)

    draw.text((650, 675), "SALES TAX (8%):", fill=(40, 40, 40), font=font_med_bold)
    draw.text((950, 675), "$439.20", fill=(40, 40, 40), font=font_med_bold)

    draw.text((650, 725), "TOTAL BALANCE:", fill=(15, 30, 120), font=font_large)
    draw.text((950, 725), "$5,929.20", fill=(15, 30, 120), font=font_large)

    # Scanned stamp
    draw.rectangle([(120, 850), (450, 960)], outline=(180, 40, 40), width=3)
    draw.text((150, 880), "VERIFIED & APPROVED", fill=(180, 40, 40), font=font_med_bold)
    draw.text((170, 915), "ACCOUNTS DEPT", fill=(180, 40, 40), font=font_med)

    # Convert back to cv2 to apply slight scan artifact / blur / rotation
    final_scanned = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    # Slight gaussian blur to emulate scanner optics
    final_scanned = cv2.GaussianBlur(final_scanned, (3, 3), 0.4)

    # Save as scanned PDF
    scanned_img_path = os.path.join(output_dir, "temp_scanned.png")
    cv2.imwrite(scanned_img_path, final_scanned)

    s_doc = fitz.open()
    s_page = s_doc.new_page(width=595, height=842)
    s_page.insert_image(fitz.Rect(0, 0, 595, 842), filename=scanned_img_path)
    s_doc.save(scanned_pdf_path)
    s_doc.close()

    if os.path.exists(scanned_img_path):
        os.remove(scanned_img_path)

    return {
        "digital_pdf": digital_pdf_path,
        "scanned_pdf": scanned_pdf_path
    }

if __name__ == "__main__":
    create_sample_documents()
