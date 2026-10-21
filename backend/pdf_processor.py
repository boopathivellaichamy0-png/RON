import os
import io
import re
import fitz  # PyMuPDF
from PIL import Image

class PDFProcessor:
    def __init__(self, upload_dir="uploads"):
        self.upload_dir = upload_dir
        os.makedirs(upload_dir, exist_ok=True)

    def load_document(self, file_path: str):
        doc = fitz.open(file_path)
        page_count = len(doc)
        metadata = doc.metadata
        return {
            "page_count": page_count,
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "is_encrypted": doc.is_encrypted
        }

    def render_page(self, file_path: str, page_num: int, dpi: int = 150) -> bytes:
        doc = fitz.open(file_path)
        if page_num < 0 or page_num >= len(doc):
            raise IndexError("Page number out of bounds")
        page = doc[page_num]
        zoom = dpi / 72.0
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat, alpha=False)
        img_bytes = pix.tobytes("png")
        doc.close()
        return img_bytes

    def _sample_bg_color_at_rect(self, page, rect: fitz.Rect) -> str:
        """
        Samples the document background color around/beneath a given rectangle.
        Samples the full perimeter ring around the text to detect the true background
        (e.g., dark blue banners, colored boxes, or paper grain).
        """
        try:
            clip_rect = fitz.Rect(max(0, rect.x0 - 3), max(0, rect.y0 - 3), rect.x1 + 3, rect.y1 + 3)
            pix = page.get_pixmap(clip=clip_rect, dpi=72)
            if pix.width > 2 and pix.height > 2:
                samples = []
                for x in range(pix.width):
                    samples.append(pix.pixel(x, 0)[:3])
                    samples.append(pix.pixel(x, pix.height - 1)[:3])
                for y in range(pix.height):
                    samples.append(pix.pixel(0, y)[:3])
                    samples.append(pix.pixel(pix.width - 1, y)[:3])
                
                # Median RGB of perimeter pixels
                med_r = int(sorted([s[0] for s in samples])[len(samples) // 2])
                med_g = int(sorted([s[1] for s in samples])[len(samples) // 2])
                med_b = int(sorted([s[2] for s in samples])[len(samples) // 2])
                return f"#{med_r:02x}{med_g:02x}{med_b:02x}"
        except Exception:
            pass
        return "#ffffff"

    def extract_vector_text_blocks(self, file_path: str, page_num: int):
        """
        Extracts digital text structure down to individual selectable words,
        capturing exact word bounding boxes, baseline origin, typography, and background color.
        """
        doc = fitz.open(file_path)
        if page_num < 0 or page_num >= len(doc):
            raise IndexError("Page number out of bounds")
        page = doc[page_num]
        page_rect = page.rect
        page_width, page_height = page_rect.width, page_rect.height

        blocks_data = []
        words_data = []

        page_dict = page.get_text("dict", flags=fitz.TEXT_DEHYPHENATE)
        raw_words = page.get_text("words")  # list of (x0, y0, x1, y1, word, block_no, line_no, word_no)

        # Build index of words for fast lookup
        word_idx = 0
        block_idx = 0

        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:  # text block
                for line_idx, line in enumerate(block.get("lines", [])):
                    line_text = ""
                    spans_info = []
                    line_bbox = line.get("bbox")

                    for span in line.get("spans", []):
                        text = span.get("text", "")
                        if not text.strip():
                            continue
                        line_text += text + " "

                        color_int = span.get("color", 0)
                        r = (color_int >> 16) & 255
                        g = (color_int >> 8) & 255
                        b = color_int & 255
                        color_hex = f"#{r:02x}{g:02x}{b:02x}"

                        spans_info.append({
                            "text": text,
                            "font": span.get("font", "Helvetica"),
                            "size": round(span.get("size", 11.0), 2),
                            "color": color_hex,
                            "flags": span.get("flags", 0),
                            "origin": span.get("origin", [span.get("bbox", [0, 0])[0], span.get("bbox", [0, 0, 0, 0])[3]]),
                            "bbox": [round(c, 2) for c in span.get("bbox", [])]
                        })

                    clean_line_text = line_text.strip()
                    if clean_line_text:
                        primary_font = spans_info[0]["font"] if spans_info else "Helvetica"
                        primary_size = spans_info[0]["size"] if spans_info else 12.0
                        primary_color = spans_info[0]["color"] if spans_info else "#000000"
                        bg_hex = self._sample_bg_color_at_rect(page, fitz.Rect(line_bbox))

                        line_id = f"p{page_num}_b{block_idx}_l{line_idx}"
                        blocks_data.append({
                            "id": line_id,
                            "page": page_num,
                            "type": "vector",
                            "text": clean_line_text,
                            "font": primary_font,
                            "size": primary_size,
                            "color": primary_color,
                            "bg_color": bg_hex,
                            "bbox": [round(c, 2) for c in line_bbox],
                            "spans": spans_info
                        })

            block_idx += 1

        # Extract word-level and token-level entities
        for rw in raw_words:
            wx0, wy0, wx1, wy1, w_text, b_no, l_no, w_no = rw[:8]
            w_rect = fitz.Rect(wx0, wy0, wx1, wy1)

            # Find matching span for font styling and baseline
            matched_span = None
            for b in blocks_data:
                for s in b.get("spans", []):
                    s_rect = fitz.Rect(s["bbox"])
                    if w_rect.intersects(s_rect):
                        matched_span = s
                        break
                if matched_span:
                    break

            font_name = matched_span["font"] if matched_span else "Helvetica"
            font_size = matched_span["size"] if matched_span else 11.0
            font_color = matched_span["color"] if matched_span else "#000000"
            flags = matched_span.get("flags", 0) if matched_span else 0
            origin = matched_span.get("origin", [wx0, wy1]) if matched_span else [wx0, wy1]
            bg_hex = self._sample_bg_color_at_rect(page, w_rect)
            font_type = "bold" if (flags & 2 != 0 or "bold" in font_name.lower()) else ("serif" if "times" in font_name.lower() else "sans")

            # Check if word contains @, brackets, or glued symbols that should be separated
            sub_matches = list(re.finditer(r'[a-zA-Z0-9_]+|[^\s\w]', w_text))
            if len(sub_matches) > 1 and len(w_text) > 2:
                total_w_len = max(1, len(w_text))
                full_w_width = wx1 - wx0
                for sm in sub_matches:
                    sub_tok = sm.group().strip()
                    if not sub_tok:
                        continue
                    sub_start = sm.start()
                    sub_end = sm.end()
                    sub_x0 = wx0 + (sub_start / total_w_len) * full_w_width
                    sub_x1 = wx0 + (sub_end / total_w_len) * full_w_width
                    sub_rect = fitz.Rect(sub_x0, wy0, max(sub_x0 + 3, sub_x1), wy1)

                    words_data.append({
                        "id": f"p{page_num}_w_{word_idx}",
                        "page": page_num,
                        "type": "vector",
                        "text": sub_tok,
                        "bbox": [round(sub_x0, 2), round(wy0, 2), round(sub_x1, 2), round(wy1, 2)],
                        "font": font_name,
                        "font_type": font_type,
                        "size": font_size,
                        "color": font_color,
                        "bg_color": bg_hex,
                        "origin": origin,
                        "block_no": b_no,
                        "line_no": l_no,
                        "word_no": w_no
                    })
                    word_idx += 1
            else:
                words_data.append({
                    "id": f"p{page_num}_w_{word_idx}",
                    "page": page_num,
                    "type": "vector",
                    "text": w_text,
                    "bbox": [round(wx0, 2), round(wy0, 2), round(wx1, 2), round(wy1, 2)],
                    "font": font_name,
                    "font_type": font_type,
                    "size": font_size,
                    "color": font_color,
                    "bg_color": bg_hex,
                    "origin": origin,
                    "block_no": b_no,
                    "line_no": l_no,
                    "word_no": w_no
                })
                word_idx += 1

        doc.close()
        return {
            "page_width": round(page_width, 2),
            "page_height": round(page_height, 2),
            "blocks": blocks_data,
            "words": words_data
        }

    def search_vector_occurrences(self, file_path: str, page_num: int, query: str, whole_word: bool = True):
        """
        Finds exact occurrences of query string in the vector PDF.
        Supports whole-word matching to avoid unintended replacements inside unrelated words.
        Returns precise word/phrase bounding box and line/span context.
        """
        if not query or not query.strip():
            return []

        doc = fitz.open(file_path)
        if page_num < 0 or page_num >= len(doc):
            return []
        page = doc[page_num]

        clean_query = query.strip()
        rects = page.search_for(clean_query)

        # Get detailed spans
        page_dict = page.get_text("dict", flags=fitz.TEXT_DEHYPHENATE)
        all_spans = []
        for block in page_dict.get("blocks", []):
            if block.get("type") == 0:
                for line in block.get("lines", []):
                    for span in line.get("spans", []):
                        all_spans.append(span)

        matches = []
        for idx, r in enumerate(rects):
            # Locate the containing span
            best_span = None
            for span in all_spans:
                s_rect = fitz.Rect(span.get("bbox", [0, 0, 0, 0]))
                if r.intersects(s_rect):
                    best_span = span
                    break

            span_text = best_span.get("text", "") if best_span else clean_query

            # Check whole-word boundary if requested
            if whole_word and clean_query.isalnum() and ' ' not in clean_query:
                pattern = r'\b' + re.escape(clean_query) + r'\b'
                if not re.search(pattern, span_text, re.IGNORECASE):
                    if clean_query.lower() not in span_text.lower():
                        continue

            # Determine position in span text
            char_start = span_text.lower().find(clean_query.lower())
            char_end = char_start + len(clean_query) if char_start != -1 else len(clean_query)

            font_name = best_span.get("font", "Helvetica") if best_span else "Helvetica"
            font_size = round(best_span.get("size", 11.0), 2) if best_span else 11.0
            color_int = best_span.get("color", 0) if best_span else 0
            cr = (color_int >> 16) & 255
            cg = (color_int >> 8) & 255
            cb = color_int & 255
            color_hex = f"#{cr:02x}{cg:02x}{cb:02x}"
            origin = best_span.get("origin", [r.x0, r.y1]) if best_span else [r.x0, r.y1]
            flags = best_span.get("flags", 0) if best_span else 0

            # Sample background color behind this word (preserves blue banners, etc.)
            bg_hex = self._sample_bg_color_at_rect(page, r)

            matches.append({
                "id": f"vec_match_{page_num}_{idx}",
                "page": page_num,
                "type": "vector",
                "matched_text": clean_query,
                "bbox": [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)],
                "span_bbox": [round(c, 2) for c in best_span["bbox"]] if best_span else [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)],
                "span_text": span_text,
                "char_start": char_start,
                "char_end": char_end,
                "origin": origin,
                "font": font_name,
                "font_type": "bold" if (flags & 2 != 0 or "bold" in font_name.lower()) else ("serif" if "times" in font_name.lower() else "sans"),
                "size": font_size,
                "color": color_hex,
                "bg_color": bg_hex
            })

        doc.close()
        return matches

    def apply_vector_edits(self, original_path: str, edits: list, output_path: str):
        """
        Applies exact word replacement in vector PDF.
        Preserves all surrounding text in the sentence, preserves dark blue banners
        and colored backgrounds, preserves exact font, size, baseline, and color.
        """
        doc = fitz.open(original_path)

        edits_by_page = {}
        for edit in edits:
            p = edit.get("page", 0)
            if p not in edits_by_page:
                edits_by_page[p] = []
            edits_by_page[p].append(edit)

        for page_num, page_edits in edits_by_page.items():
            if page_num < 0 or page_num >= len(doc):
                continue
            page = doc[page_num]

            # Re-read page spans to guarantee fresh coordinates and text
            page_dict = page.get_text("dict", flags=fitz.TEXT_DEHYPHENATE)
            all_spans = []
            for block in page_dict.get("blocks", []):
                if block.get("type") == 0:
                    for line in block.get("lines", []):
                        for span in line.get("spans", []):
                            all_spans.append(span)

            # Process each word edit
            for item in page_edits:
                orig_text = item.get("original_text", "")
                new_text = item.get("new_text", "")
                bbox = item.get("pdf_bbox") or item.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue

                target_rect = fitz.Rect(bbox)

                # Locate the parent span containing this word
                matched_span = None
                for s in all_spans:
                    s_rect = fitz.Rect(s["bbox"])
                    if target_rect.intersects(s_rect):
                        matched_span = s
                        break

                # Background fill color (detect or use provided bg_color)
                bg_hex = item.get("bg_color") or self._sample_bg_color_at_rect(page, target_rect)
                bg_hex_clean = bg_hex.lstrip("#")
                if len(bg_hex_clean) == 6:
                    bg_rgb = tuple(int(bg_hex_clean[i:i+2], 16)/255.0 for i in (0, 2, 4))
                else:
                    bg_rgb = (1.0, 1.0, 1.0)

                # Text color
                color_hex = (item.get("color") or item.get("font_color") or "#000000").lstrip("#")
                if len(color_hex) == 6:
                    text_rgb = tuple(int(color_hex[i:i+2], 16)/255.0 for i in (0, 2, 4))
                else:
                    text_rgb = (0.0, 0.0, 0.0)

                # Font size
                font_size = float(item.get("size") or item.get("font_size") or 11.0)
                font_name = item.get("font") or item.get("font_name") or "helv"
                safe_font = "helv"
                f_lower = font_name.lower()
                if "bold" in f_lower or "hebo" in f_lower:
                    safe_font = "hebo"
                elif "times" in f_lower:
                    safe_font = "times-bold" if "bold" in f_lower else "times-roman"
                elif "courier" in f_lower:
                    safe_font = "courier-bold" if "bold" in f_lower else "courier"
                elif "italic" in f_lower:
                    safe_font = "heit"

                if matched_span:
                    # Replace word inside the span, preserving all surrounding text!
                    full_span_text = matched_span.get("text", "")
                    
                    # Regex whole-word replacement if whole word, otherwise substring replacement
                    if orig_text in full_span_text:
                        pattern = r'\b' + re.escape(orig_text) + r'\b'
                        if re.search(pattern, full_span_text):
                            updated_span_text = re.sub(pattern, new_text, full_span_text, count=1)
                        else:
                            updated_span_text = full_span_text.replace(orig_text, new_text, 1)
                    else:
                        updated_span_text = new_text

                    span_rect = fitz.Rect(matched_span["bbox"])
                    # Redact the span bbox using the exact background color
                    page.add_redact_annot(span_rect, fill=bg_rgb)
                    page.apply_redactions()

                    # Re-insert the updated span text at the exact baseline origin
                    origin_point = fitz.Point(matched_span.get("origin", [span_rect.x0, span_rect.y1]))
                    page.insert_text(
                        origin_point,
                        updated_span_text,
                        fontname=safe_font,
                        fontsize=font_size,
                        color=text_rgb
                    )
                else:
                    # Standalone word/box replacement
                    page.add_redact_annot(target_rect, fill=bg_rgb)
                    page.apply_redactions()

                    if new_text:
                        origin_point = fitz.Point(target_rect.x0, target_rect.y1 - 2)
                        page.insert_text(
                            origin_point,
                            new_text,
                            fontname=safe_font,
                            fontsize=font_size,
                            color=text_rgb
                        )

        doc.save(output_path, garbage=3, deflate=True)
        doc.close()
        return output_path
