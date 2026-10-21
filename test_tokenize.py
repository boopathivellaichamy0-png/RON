import cv2
import numpy as np
import re

img_path = r'C:/Users/Admin/.gemini/antigravity/brain/f3a861be-f3fc-4e6d-84fb-fbbea8ddbc8f/.user_uploaded/media_1792475130175_add55e4a.png'
img = cv2.imread(img_path)

x0, y0, x1, y1 = 12, 181, 190, 199
line_w = x1 - x0
line_h = y1 - y0
line_text = '-(ashwant@ashwant)-[~/exp4]'

print('Line box:', x0, y0, x1, y1, 'W=', line_w, 'H=', line_h)

# Split tokens: words, @, and other symbols
tokens = []
# Find all words (e.g. ashwant, exp4) and special tokens
for m in re.finditer(r'[a-zA-Z0-9_]+|[^\s\w]', line_text):
    tok = m.group()
    start = m.start()
    end = m.end()
    wx0 = int(x0 + (start / len(line_text)) * line_w)
    wx1 = int(x0 + (end / len(line_text)) * line_w)
    tokens.append((tok, wx0, y0, wx1, y1))
    print(f'Token: "{tok}" -> BBox [{wx0}, {y0}, {wx1}, {y1}], W={wx1-wx0}')
