import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import os

class InpaintEngine:
    def __init__(self):
        self.font_dir = "C:/Windows/Fonts"
        self.font_map = {
            "mono": os.path.join(self.font_dir, "consola.ttf"),
            "consolas": os.path.join(self.font_dir, "consola.ttf"),
            "courier": os.path.join(self.font_dir, "cour.ttf"),
            "sans": os.path.join(self.font_dir, "arial.ttf"),
            "serif": os.path.join(self.font_dir, "times.ttf"),
            "bold": os.path.join(self.font_dir, "arialbd.ttf"),
            "bold_mono": os.path.join(self.font_dir, "consolab.ttf"),
            "calibri": os.path.join(self.font_dir, "calibri.ttf")
        }

    def _get_font(self, font_type: str, size: int):
        font_path = self.font_map.get(str(font_type).lower())
        if font_path and os.path.exists(font_path):
            try:
                return ImageFont.truetype(font_path, max(5, int(size)))
            except Exception:
                pass
        # Fallback to consolas or arial if available
        for fb in ["consola.ttf", "arial.ttf"]:
            p = os.path.join(self.font_dir, fb)
            if os.path.exists(p):
                try:
                    return ImageFont.truetype(p, max(5, int(size)))
                except Exception:
                    pass
        try:
            return ImageFont.load_default()
        except Exception:
            return None

    def sample_area_style(self, image_np: np.ndarray, bbox: list) -> dict:
        """
        Samples background color, ink color, and font metrics from a specific bounding box.
        Supports both light documents and dark themes / terminals.
        """
        h, w = image_np.shape[:2]
        x0 = max(0, int(bbox[0]))
        y0 = max(0, int(bbox[1]))
        x1 = min(w, int(bbox[2]))
        y1 = min(h, int(bbox[3]))

        if x1 <= x0 or y1 <= y0:
            return {
                "font_color": "#000000",
                "bg_color": "#ffffff",
                "font_size": 12.0,
                "is_textured": False
            }

        roi = image_np[y0:y1, x0:x1]
        box_h = y1 - y0

        # Sample border perimeter for background color
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
            std_bgr = np.std(border_pixels)
            is_textured = bool(std_bgr > 35)
        except Exception:
            bg_hex = "#ffffff"
            bg_lum = 255.0
            is_textured = False

        # Sample text ink color (Light / Dark mode aware)
        try:
            gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            if bg_lum < 120:
                p80 = np.percentile(gray_roi, 80)
                ink_pixels = roi[gray_roi >= max(bg_lum + 12, p80)]
                if len(ink_pixels) == 0:
                    ink_pixels = roi[gray_roi >= p80]
                med_ink = np.median(ink_pixels, axis=0).astype(int)
            else:
                p20 = np.percentile(gray_roi, 20)
                ink_pixels = roi[gray_roi <= min(bg_lum - 12, p20)]
                if len(ink_pixels) == 0:
                    ink_pixels = roi[gray_roi <= p20]
                med_ink = np.median(ink_pixels, axis=0).astype(int)
            ink_hex = f"#{med_ink[2]:02x}{med_ink[1]:02x}{med_ink[0]:02x}"
        except Exception:
            ink_hex = "#1a1a1a" if bg_lum >= 120 else "#e0e0e0"

        est_font_size = max(7.0, round(box_h * 0.75, 1))

        return {
            "font_color": ink_hex,
            "bg_color": bg_hex,
            "font_size": est_font_size,
            "is_textured": is_textured
        }

    def inpaint_and_replace(self, image_np: np.ndarray, edits: list) -> np.ndarray:
        """
        Smart Duplicate & Texture Synthesis Engine:
        1. Duplicates the original text ROI as a style reference.
        2. Synthesizes a seamless background patch matching local noise, texture, and luminance.
        3. Renders the replacement text using matching typography (Consolas for monospace/terminal,
           Arial/Times for standard text), with 3x supersampling and downscaling for natural screen anti-aliasing.
        4. Alpha-feathers borders to produce a 100% invisible transition into the surrounding image.
        """
        img_out = image_np.copy()
        img_h, img_w = img_out.shape[:2]

        for edit in edits:
            bbox = edit.get("pixel_bbox")
            if not bbox or len(bbox) != 4:
                continue

            x0 = max(0, int(bbox[0]))
            y0 = max(0, int(bbox[1]))
            x1 = min(img_w, int(bbox[2]))
            y1 = min(img_h, int(bbox[3]))

            w = x1 - x0
            h = y1 - y0
            if w <= 4 or h <= 4:
                continue

            # Original text crop (duplicate as style reference)
            roi = img_out[y0:y1, x0:x1]
            if roi.size == 0:
                continue

            # 1. Sample perimeter background color and local texture noise
            pad = max(1, min(3, h // 4, w // 4))
            try:
                border_pixels = np.concatenate([
                    roi[:pad, :].reshape(-1, 3),
                    roi[-pad:, :].reshape(-1, 3),
                    roi[:, :pad].reshape(-1, 3),
                    roi[:, -pad:].reshape(-1, 3)
                ])
                bg_bgr = np.median(border_pixels, axis=0).astype(np.float32)
                bg_std = np.std(border_pixels)
                bg_lum = 0.299 * bg_bgr[2] + 0.587 * bg_bgr[1] + 0.114 * bg_bgr[0]
            except Exception:
                bg_hex = edit.get("bg_color", "#ffffff").lstrip("#")
                if len(bg_hex) == 6:
                    bg_bgr = np.array([int(bg_hex[4:6], 16), int(bg_hex[2:4], 16), int(bg_hex[0:2], 16)], dtype=np.float32)
                else:
                    bg_bgr = np.array([255.0, 255.0, 255.0], dtype=np.float32)
                bg_std = 0.0
                bg_lum = 0.299 * bg_bgr[2] + 0.587 * bg_bgr[1] + 0.114 * bg_bgr[0]

            # 2. Sample original text ink color
            try:
                gray_roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
                if bg_lum < 120:
                    p75 = np.percentile(gray_roi, 75)
                    ink_pixels = roi[gray_roi >= max(bg_lum + 10, p75)]
                    if len(ink_pixels) == 0:
                        ink_pixels = roi[gray_roi >= p75]
                else:
                    p25 = np.percentile(gray_roi, 25)
                    ink_pixels = roi[gray_roi <= min(bg_lum - 10, p25)]
                    if len(ink_pixels) == 0:
                        ink_pixels = roi[gray_roi <= p25]
                ink_bgr = np.median(ink_pixels, axis=0).astype(np.float32)
            except Exception:
                color_hex = edit.get("font_color", "#000000").lstrip("#")
                if len(color_hex) == 6:
                    ink_bgr = np.array([int(color_hex[4:6], 16), int(color_hex[2:4], 16), int(color_hex[0:2], 16)], dtype=np.float32)
                else:
                    ink_bgr = np.array([25.0, 25.0, 25.0] if bg_lum >= 120 else [220.0, 220.0, 220.0], dtype=np.float32)

            # If user explicitly overrode font color
            req_color = edit.get("font_color")
            if req_color and req_color.startswith("#") and len(req_color) == 7:
                ink_bgr = np.array([int(req_color[5:7], 16), int(req_color[3:5], 16), int(req_color[1:3], 16)], dtype=np.float32)

            # 3. Synthesize duplicate background patch matching texture noise
            bg_patch = np.ones((h, w, 3), dtype=np.float32) * bg_bgr
            if bg_std > 1.2:
                noise = np.random.normal(0, min(bg_std * 0.45, 2.8), (h, w, 3))
                bg_patch = np.clip(bg_patch + noise, 0, 255)

            new_text = edit.get("new_text", "")
            if not new_text:
                # Just erase
                img_out[y0:y1, x0:x1] = bg_patch.astype(np.uint8)
                continue

            # 4. Font Family Selection (Consolas for monospace/terminal, Arial/Times for standard text)
            font_type = str(edit.get("font_type", "")).lower()
            is_mono = font_type in ["mono", "consolas", "courier"] or bg_lum < 120
            is_bold = "bold" in font_type or "bold" in str(edit.get("original_text", "")).lower()

            if is_mono:
                font_key = "bold_mono" if is_bold else "mono"
            elif "serif" in font_type:
                font_key = "serif"
            elif is_bold:
                font_key = "bold"
            else:
                font_key = "sans"

            # 5. Supersampled (3x) text rendering for natural subpixel screen anti-aliasing
            scale = 3
            hi_w, hi_h = w * scale, h * scale
            hi_img = Image.new("L", (hi_w, hi_h), 0)
            hi_draw = ImageDraw.Draw(hi_img)

            # Target height fitting inside line cell
            target_h = int(h * 0.72 * scale)
            font_size = max(6, int(h * 0.78 * scale))
            font = self._get_font(font_key, font_size)

            tb = hi_draw.textbbox((0, 0), new_text, font=font)
            text_w = tb[2] - tb[0]
            text_h = tb[3] - tb[1]

            # Fit text horizontally if longer than box
            if text_w > hi_w:
                font_size = max(5, int(font_size * (hi_w / text_w) * 0.98))
                font = self._get_font(font_key, font_size)
                tb = hi_draw.textbbox((0, 0), new_text, font=font)
                text_w = tb[2] - tb[0]
                text_h = tb[3] - tb[1]

            while text_h > target_h and font_size > 5:
                font_size -= 1
                font = self._get_font(font_key, font_size)
                tb = hi_draw.textbbox((0, 0), new_text, font=font)
                text_h = tb[3] - tb[1]

            # Center text in high-res patch
            off_x = max(0, (hi_w - (tb[2] - tb[0])) // 2) - tb[0]
            off_y = max(0, (hi_h - (tb[3] - tb[1])) // 2) - tb[1]
            hi_draw.text((off_x, off_y), new_text, fill=255, font=font)

            # Downsample high-res text mask with INTER_AREA to produce natural optical anti-aliasing
            text_mask = cv2.resize(np.array(hi_img), (w, h), interpolation=cv2.INTER_AREA).astype(np.float32) / 255.0
            text_mask = np.expand_dims(text_mask, axis=2)

            # 6. Composite text onto synthesized background patch
            synth_patch = text_mask * ink_bgr + (1.0 - text_mask) * bg_patch

            # 7. Alpha-feather the outer 1-pixel border to eliminate hard edges
            if w > 4 and h > 4:
                feather_mask = np.ones((h, w, 1), dtype=np.float32)
                feather_mask[0, :] = 0.35
                feather_mask[-1, :] = 0.35
                feather_mask[:, 0] = 0.35
                feather_mask[:, -1] = 0.35
                final_patch = synth_patch * feather_mask + roi.astype(np.float32) * (1.0 - feather_mask)
            else:
                final_patch = synth_patch

            img_out[y0:y1, x0:x1] = np.clip(final_patch, 0, 255).astype(np.uint8)

        return img_out
