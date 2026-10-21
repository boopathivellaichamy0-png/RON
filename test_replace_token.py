import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import re

img_path = r'C:/Users/Admin/.gemini/antigravity/brain/f3a861be-f3fc-4e6d-84fb-fbbea8ddbc8f/.user_uploaded/media_1792475130175_add55e4a.png'
img = cv2.imread(img_path)

# Target box [12, 181, 190, 199]
x0, y0, x1, y1 = 12, 181, 190, 199
line_w = x1 - x0
line_h = y1 - y0
line_text = '-(ashwant@ashwant)-[~/exp4]'

# Target word 1: first 'ashwant' -> bbox [25, 181, 71, 199]
wx0, wy0, wx1, wy1 = 25, 181, 71, 199
w_box_h = wy1 - wy0

# Sample background around that word
roi = img[wy0:wy1, wx0:wx1]
border = np.concatenate([roi[0, :], roi[-1, :], roi[:, 0], roi[:, -1]])
bg_bgr = np.median(border, axis=0).astype(int)
bg_tuple = (int(bg_bgr[0]), int(bg_bgr[1]), int(bg_bgr[2]))

# Erase ONLY that word's exact box
img_out = img.copy()
cv2.rectangle(img_out, (wx0, wy0), (wx1, wy1), bg_tuple, -1)

# Render 'boopathi' with auto-scaled font
img_pil = Image.fromarray(cv2.cvtColor(img_out, cv2.COLOR_BGR2RGB))
draw = ImageDraw.Draw(img_pil)

# Sample ink color
gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
p80 = np.percentile(gray, 80)
ink_pixels = roi[gray >= p80]
med_ink = np.median(ink_pixels, axis=0).astype(int)
ink_rgb = (int(med_ink[2]), int(med_ink[1]), int(med_ink[0]))

# Dynamic font sizing
target_h = max(6, int(w_box_h * 0.74))
font_sz = max(5, int(w_box_h * 0.8))
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', font_sz)
tb = draw.textbbox((0, 0), 'boopathi', font=font)
h = tb[3] - tb[1]

while h > target_h and font_sz > 5:
    font_sz -= 1
    font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', font_sz)
    tb = draw.textbbox((0, 0), 'boopathi', font=font)
    h = tb[3] - tb[1]

offset_y = wy0 + max(0, (w_box_h - h) // 2) - tb[1]
draw.text((wx0, offset_y), 'boopathi', fill=ink_rgb, font=font)

res = cv2.cvtColor(np.array(img_pil), cv2.COLOR_RGB2BGR)
cv2.imwrite('backend/uploads/token_test_result.png', res)
print('Successfully replaced first ashwant with boopathi, leaving -( and @ untouched!')
