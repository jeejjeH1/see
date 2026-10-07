import sys
from PIL import Image, ImageDraw
files = sys.argv[2:]; out = sys.argv[1]
W, H, C = 640, 360, 3
rows = (len(files) + C - 1) // C
sheet = Image.new('RGB', (C * W + (C + 1) * 8, rows * (H + 30) + 8), '#888')
d = ImageDraw.Draw(sheet)
for i, f in enumerate(files):
    im = Image.open(f).convert('RGB').resize((W, H), Image.LANCZOS)
    x, y = 8 + (i % C) * (W + 8), 8 + (i // C) * (H + 30)
    sheet.paste(im, (x, y)); d.text((x, y + H + 4), f.split('/')[-1], fill='white')
sheet.save(out)
