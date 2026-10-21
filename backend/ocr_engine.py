import numpy as np
import cv2
from PIL import Image
import io
import re
from rapidocr_onnxruntime import RapidOCR

class OCREngine:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(OCREngine, cls).__new__(cls)
            cls._instance.ocr = RapidOCR()
        return cls._instance

    def _sample_colors_and_size(self, img_bgr, px0, py0, px1, py1):
        """
        Samples dominant ink color and background color around a specific bounding box.
        Supports both light documents (white paper / black ink) and dark documents
        (terminals, IDEs, dark banners, night mode / white ink).
        """
        h, w = img_bgr.shape[:2]
        x0 = max(0, int(px0))
        y0 = max(0, int(py0))
        x1 = min(w, int(px1))
        y1 = min(h, int(py1))

        if x1 <= x0 or y1 <= y0:
            return "#1a1a1a", "#ffffff", 12.0

        roi = img_bgr[y0:y1, x0:x1]
        box_h = y1 - y0

        # Sample border pixels for background color
        pad = max(1, min(2, box_h // 4, (x1 - x0) // 4))
        try:
            border_pixels = np.concatenate([
                roi[:pad, :].reshape(-1, 3),
                roi[-pad:, :].reshape(-1, 3),
                roi[:, :pad].reshape(-1, 3),
                roi[:, -pad:].reshape(-1, 3)
            ])
            med_bgr = np.median(border_pixels, axis=0).astype(int)
            bg_hex = f"#{med_bgr[2]:02x}{med_bgr[1]:02x}{med_bgr[0]:02x}"
            bg_lum = 0.299 * med_bgr[2] + 0.587 * med_bgr[1] + 0.114 * med_bgr[0]
        except Exception:
            bg_hex = "#ffffff"
            bg_lum = 255.0

        # Sample text ink color (Light/Dark background aware)
        try:
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            if bg_lum < 120:
                # Dark background: text ink is lighter than background!
                p80 = np.percentile(gray_roi, 80)
                ink_candidates = roi[gray_roi >= max(bg_lum + 12, p80)]
                if len(ink_candidates) == 0:
                    ink_candidates = roi[gray_roi >= p80]
                med_ink = np.median(ink_candidates, axis=0).astype(int)
                ink_hex = f"#{med_ink[2]:02x}{med_ink[1]:02x}{med_ink[0]:02x}"
            else:
                # Light background: text ink is darker than background!
                p20 = np.percentile(gray_roi, 20)
                ink_candidates = roi[gray_roi <= min(bg_lum - 12, p20)]
                if len(ink_candidates) == 0:
                    ink_candidates = roi[gray_roi <= p20]
                med_ink = np.median(ink_candidates, axis=0).astype(int)
                ink_hex = f"#{med_ink[2]:02x}{med_ink[1]:02x}{med_ink[0]:02x}"
        except Exception:
            ink_hex = "#1a1a1a" if bg_lum >= 120 else "#e0e0e0"

        est_font_size = max(7.0, round(box_h * 0.75, 1))
        return ink_hex, bg_hex, est_font_size

    def _segment_line_into_words(self, img_bgr, px0, py0, px1, py1, line_text, confidence, scale_x, scale_y, line_idx):
        """
        Tokenizes recognized text into individual words, names, and symbols one by one.
        Separates names from @, brackets, and punctuation so users can select and replace
        individual words without affecting surrounding symbols like '@'.
        """
        if not line_text or not line_text.strip():
            return []

        h, w = img_bgr.shape[:2]
        x0 = max(0, int(px0))
        y0 = max(0, int(py0))
        x1 = min(w, int(px1))
        y1 = min(h, int(py1))
        line_w = x1 - x0
        line_h = y1 - y0

        if line_w <= 6:
            return []

        # Find word tokens (names, alphanumeric sequences) and individual symbols
        # Matches words like 'ashwant' separately from '@', '(', ')', etc.
        token_matches = list(re.finditer(r'[a-zA-Z0-9_]+|[^\s\w]', line_text))
        if not token_matches:
            token_matches = list(re.finditer(r'\S+', line_text))

        line_len = max(1, len(line_text))

        # Split fused duplicate tokens (e.g. 'ashwantashwant' when '@' was dropped by OCR)
        expanded_tokens = []
        for m in token_matches:
            tok = m.group().strip()
            if not tok:
                continue
            n = len(tok)
            if n >= 6 and n % 2 == 0 and tok[:n//2].lower() == tok[n//2:].lower():
                half = n // 2
                expanded_tokens.append((tok[:half], m.start(), m.start() + half))
                expanded_tokens.append((tok[half:], m.start() + half, m.end()))
            else:
                expanded_tokens.append((tok, m.start(), m.end()))

        word_results = []
        for w_idx, (tok, start, end) in enumerate(expanded_tokens):
            actual_x0 = int(x0 + (start / line_len) * line_w)
            actual_x1 = int(x0 + (end / line_len) * line_w)
            actual_x1 = max(actual_x0 + 4, actual_x1)

            ink_color, bg_color, est_size = self._sample_colors_and_size(img_bgr, actual_x0, y0, actual_x1, y1)
            pdf_bbox = [
                round(actual_x0 * scale_x, 2),
                round(y0 * scale_y, 2),
                round(actual_x1 * scale_x, 2),
                round(y1 * scale_y, 2)
            ]

            word_results.append({
                "id": f"ocr_w_{line_idx}_{w_idx}",
                "line_id": f"ocr_line_{line_idx}",
                "text": tok,
                "confidence": confidence,
                "color": ink_color,
                "bg_color": bg_color,
                "est_font_size": est_size,
                "pixel_bbox": [float(actual_x0), float(y0), float(actual_x1), float(y1)],
                "pdf_bbox": pdf_bbox,
                "full_line_text": line_text
            })

        return word_results

    def _run_ocr_dual_pass(self, img):
        """
        Runs dual-pass OCR with adaptive contrast and inversion detection to maximize
        recall for low-clarity, blurry, small, or dark-background text (e.g. Linux terminals).
        """
        if hasattr(self.ocr, 'text_detector') and hasattr(self.ocr.text_detector, 'postprocess_op'):
            self.ocr.text_detector.postprocess_op.thresh = 0.2
            self.ocr.text_detector.postprocess_op.box_thresh = 0.35

        # Pass 1: Standard image
        r1, _ = self.ocr(img)
        res1 = r1 if r1 else []

        # Analyze image background luminance
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        mean_lum = float(np.mean(gray))
        p20_lum = float(np.percentile(gray, 20))

        # If image has dark regions (e.g. terminals, code blocks, dark banners, night mode)
        # or overall low clarity, run inverted pass (255 - img)
        res2 = []
        if mean_lum < 185 or p20_lum < 90:
            inv = 255 - img
            r2, _ = self.ocr(inv)
            res2 = r2 if r2 else []

        if not res2:
            return res1
        if not res1:
            return res2

        def poly_to_bbox(poly):
            pts = np.array(poly, dtype=np.float32)
            return [float(np.min(pts[:, 0])), float(np.min(pts[:, 1])),
                    float(np.max(pts[:, 0])), float(np.max(pts[:, 1]))]

        def box_overlap(box1, box2):
            ix0 = max(box1[0], box2[0])
            iy0 = max(box1[1], box2[1])
            ix1 = min(box1[2], box2[2])
            iy1 = min(box1[3], box2[3])
            if ix1 <= ix0 or iy1 <= iy0:
                return 0.0
            inter_area = (ix1 - ix0) * (iy1 - iy0)
            area1 = (box1[2] - box1[0]) * (box1[3] - box1[1])
            area2 = (box2[2] - box2[0]) * (box2[3] - box2[1])
            min_area = min(area1, area2)
            return inter_area / min_area if min_area > 0 else 0.0

        # Prioritize candidates: for dark backgrounds, inverted results (res2) have superior clarity!
        if mean_lum < 130:
            all_candidates = list(res2) + list(res1)
        else:
            all_candidates = list(res1) + list(res2)

        # Sort candidates by length of text * confidence descending so complete line boxes are preferred
        all_candidates.sort(
            key=lambda x: len(x[1].strip()) * (float(x[2]) if not isinstance(x[2], str) else 0.9),
            reverse=True
        )

        merged = []
        for cand in all_candidates:
            cand_box = poly_to_bbox(cand[0])
            overlaps = False
            for kept in merged:
                kept_box = poly_to_bbox(kept[0])
                if box_overlap(cand_box, kept_box) > 0.55:
                    overlaps = True
                    break
            if not overlaps:
                merged.append(cand)

        # Sort merged in reading order: top-to-bottom, left-to-right
        merged.sort(key=lambda item: (poly_to_bbox(item[0])[1], poly_to_bbox(item[0])[0]))
        return merged

    def process_image(self, img_source, pdf_width_pt: float = None, pdf_height_pt: float = None):
        if isinstance(img_source, bytes):
            nparr = np.frombuffer(img_source, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        elif isinstance(img_source, Image.Image):
            img = cv2.cvtColor(np.array(img_source), cv2.COLOR_RGB2BGR)
        elif isinstance(img_source, np.ndarray):
            img = img_source
        else:
            raise ValueError("Unsupported image source type")

        img_h, img_w = img.shape[:2]
        scale_x = (pdf_width_pt / img_w) if pdf_width_pt else 1.0
        scale_y = (pdf_height_pt / img_h) if pdf_height_pt else 1.0

        ocr_results = self._run_ocr_dual_pass(img)

        extracted_lines = []
        extracted_words = []

        if not ocr_results:
            return {
                "image_width": img_w,
                "image_height": img_h,
                "boxes": [],
                "words": []
            }

        for idx, item in enumerate(ocr_results):
            poly = item[0]
            text = item[1].strip()
            confidence = round(float(item[2]), 4) if not isinstance(item[2], str) else 0.9

            if not text:
                continue

            pts = np.array(poly, dtype=np.float32)
            px0 = float(np.min(pts[:, 0]))
            py0 = float(np.min(pts[:, 1]))
            px1 = float(np.max(pts[:, 0]))
            py1 = float(np.max(pts[:, 1]))

            ink_color, bg_color, est_size = self._sample_colors_and_size(img, px0, py0, px1, py1)

            pdf_bbox = [
                round(px0 * scale_x, 2),
                round(py0 * scale_y, 2),
                round(px1 * scale_x, 2),
                round(py1 * scale_y, 2)
            ]

            line_entry = {
                "id": f"ocr_line_{idx}",
                "text": text,
                "confidence": confidence,
                "color": ink_color,
                "bg_color": bg_color,
                "est_font_size": est_size,
                "pixel_bbox": [round(px0, 1), round(py0, 1), round(px1, 1), round(py1, 1)],
                "pdf_bbox": pdf_bbox,
                "polygon": [[round(p[0], 1), round(p[1], 1)] for p in poly]
            }
            extracted_lines.append(line_entry)

            segmented_words = self._segment_line_into_words(
                img, px0, py0, px1, py1, text, confidence, scale_x, scale_y, idx
            )
            extracted_words.extend(segmented_words)

        return {
            "image_width": img_w,
            "image_height": img_h,
            "boxes": extracted_lines,
            "words": extracted_words
        }
