from pathlib import Path
from PIL import Image, ImageDraw

OUT = Path(r"C:/Users/Public/Documents/Code/jin/rag-lab/outputs/rag-lab-value-icons")
RED = (198, 16, 50, 255)
SIZE = 512
SCALE = 4
CANVAS = SIZE * SCALE


def canvas():
    return Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0)), ImageDraw.Draw(Image.new("RGBA", (1, 1)))


def save_icon(name, draw_fn):
    img = Image.new("RGBA", (CANVAS, CANVAS), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    draw_fn(d)
    img = img.resize((SIZE, SIZE), Image.Resampling.LANCZOS)
    img.save(OUT / f"{name}.png")


def p(points):
    return [(int(x * SCALE), int(y * SCALE)) for x, y in points]


def rr(d, xy, r=18, fill=RED):
    d.rounded_rectangle(tuple(int(v * SCALE) for v in xy), radius=int(r * SCALE), fill=fill)


def line(d, points, width=34):
    d.line(p(points), fill=RED, width=int(width * SCALE), joint="curve")


def agile_deploy(d):
    # Lightning mark for fast deployment.
    d.polygon(p([(282, 36), (92, 266), (220, 266), (164, 476), (420, 196), (282, 196)]), fill=RED)


def knowledge_unified(d):
    # Rounded unified knowledge hub: soft central node connected to sources.
    rr(d, (176, 176, 336, 336), 48)
    rr(d, (82, 82, 176, 176), 30)
    rr(d, (336, 82, 430, 176), 30)
    rr(d, (82, 336, 176, 430), 30)
    rr(d, (336, 336, 430, 430), 30)
    line(d, [(172, 154), (206, 206)], 30)
    line(d, [(340, 154), (306, 206)], 30)
    line(d, [(172, 358), (206, 306)], 30)
    line(d, [(340, 358), (306, 306)], 30)
    d.ellipse(tuple(int(v * SCALE) for v in (220, 220, 292, 292)), fill=(255, 255, 255, 255))


def efficiency_leap(d):
    # Rising arrow and speed bars.
    line(d, [(96, 372), (188, 280), (260, 318), (396, 152)], 38)
    d.polygon(p([(390, 88), (430, 210), (310, 178)]), fill=RED)
    rr(d, (82, 404, 174, 440), 12)
    rr(d, (82, 342, 136, 378), 12)
    rr(d, (82, 280, 118, 316), 12)


def trustworthy_answer(d):
    # Document with a transparent check mark for credible answers.
    rr(d, (118, 62, 378, 438), 34)
    d.polygon(p([(318, 62), (378, 122), (318, 122)]), fill=(0, 0, 0, 0))
    # Transparent check cutout.
    line(d, [(178, 258), (238, 318), (342, 198)], 44)
    # The previous line is red; overlay a larger transparent check to cut through the document.
    d.line(p([(178, 258), (238, 318), (342, 198)]), fill=(0, 0, 0, 0), width=int(28 * SCALE), joint="curve")


def risk_control(d):
    # Rounded shield, closer to the user's reference but softer.
    d.rounded_rectangle(tuple(int(v * SCALE) for v in (126, 98, 386, 388)), radius=int(118 * SCALE), fill=RED)
    # Shape the upper point and lower point with smooth polygons.
    d.polygon(p([(256, 48), (394, 106), (386, 230), (338, 382), (256, 462), (174, 382), (126, 230), (118, 106)]), fill=RED)
    d.rounded_rectangle(tuple(int(v * SCALE) for v in (146, 112, 366, 356)), radius=int(76 * SCALE), fill=RED)


def continuous_evolution(d):
    # Softer continuous improvement loop with rounded arrows and central spark.
    d.arc(tuple(int(v * SCALE) for v in (96, 86, 416, 406)), start=210, end=24, fill=RED, width=int(36 * SCALE))
    d.arc(tuple(int(v * SCALE) for v in (96, 106, 416, 426)), start=30, end=204, fill=RED, width=int(36 * SCALE))
    d.polygon(p([(396, 72), (450, 184), (328, 158)]), fill=RED)
    d.polygon(p([(116, 440), (62, 328), (184, 354)]), fill=RED)
    d.polygon(p([(256, 168), (286, 230), (354, 256), (286, 282), (256, 344), (226, 282), (158, 256), (226, 230)]), fill=RED)


icons = [
    ("01-agile-deployment", agile_deploy),
    ("02-knowledge-unified", knowledge_unified),
    ("03-efficiency-leap", efficiency_leap),
    ("04-trustworthy-answer", trustworthy_answer),
    ("05-risk-control", risk_control),
    ("06-continuous-evolution", continuous_evolution),
]
for name, fn in icons:
    save_icon(name, fn)

# Preview sheet on white background for quick inspection only.
sheet = Image.new("RGBA", (SIZE * 3, SIZE * 2), (255, 255, 255, 255))
for idx, (name, _) in enumerate(icons):
    icon = Image.open(OUT / f"{name}.png")
    x = (idx % 3) * SIZE
    y = (idx // 3) * SIZE
    sheet.alpha_composite(icon, (x, y))
sheet.save(OUT / "preview-sheet.png")
print(OUT)


