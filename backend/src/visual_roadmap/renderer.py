from html import escape
import textwrap

from src.schemas.visual_roadmap import RoadmapStructure


def _lines(value: str, width: int = 28, maximum: int = 4) -> list[str]:
    return textwrap.wrap(value, width=width, break_long_words=False)[:maximum] or [""]


def _text(x: int, y: int, value: str, *, width=28, css="body") -> str:
    return f'<text x="{x}" y="{y}" class="{css}">' + "".join(
        f'<tspan x="{x}" dy="{0 if i == 0 else 18}">{escape(line)}</tspan>'
        for i, line in enumerate(_lines(value, width))
    ) + "</text>"


def render_svg(data: RoadmapStructure) -> str:
    n = len(data.nodes)
    width = 1200
    header = 150
    footer = 100 + 24 * len(data.exam_points)
    if data.visual_type in {"flowchart", "process"}:
        height = header + n * 170 + footer
        positions = [(400, header + i * 170) for i in range(n)]
    elif data.visual_type == "concept_map":
        height = max(720, header + ((n + 2) // 3) * 190 + footer)
        positions = [(80 + (i % 3) * 380, header + (i // 3) * 190) for i in range(n)]
    elif data.visual_type == "comparison":
        cols = min(3, max(2, n))
        height = header + ((n + cols - 1) // cols) * 190 + footer
        positions = [(35 + (i % cols) * (1130 // cols), header + (i // cols) * 190) for i in range(n)]
    elif data.visual_type == "cause_effect":
        height = max(620, header + n * 105 + footer)
        positions = [(70 if i < n - 1 else 760, header + i * 105 if i < n - 1 else header + max(0, n - 2) * 52) for i in range(n)]
    else:
        height = max(600, header + 360 + footer)
        positions = [(35 + i * (1130 // max(1, n)), header + (35 if i % 2 else 0)) for i in range(n)]
    box_w = 330 if data.visual_type != "timeline" else max(150, min(260, 1040 // max(1, n)))
    box_h = 130
    pos = {node.id: positions[i] for i, node in enumerate(data.nodes)}
    arrows = []
    for connection in data.connections:
        x1, y1 = pos[connection.from_id]; x2, y2 = pos[connection.to]
        arrows.append(f'<line x1="{x1 + box_w/2}" y1="{y1 + box_h}" x2="{x2 + box_w/2}" y2="{y2}" class="arrow" marker-end="url(#arrow)"/>')
    boxes = []
    for node, (x, y) in zip(data.nodes, positions):
        marker = ", ".join(node.source_ids)
        boxes.append(f'<g><rect x="{x}" y="{y}" width="{box_w}" height="{box_h}" rx="16" class="node"/>'
            + _text(x + 16, y + 27, (node.year + " · " if node.year else "") + node.label, width=30, css="label")
            + _text(x + 16, y + 70, node.description, width=38, css="body")
            + f'<text x="{x + 16}" y="{y + box_h - 12}" class="source">Sources: {escape(marker)}</text></g>')
    exam_y = height - footer + 35
    exams = _text(40, exam_y, "UPSC exam points", css="section") + "".join(
        _text(55, exam_y + 28 + i * 24, "• " + point, width=105) for i, point in enumerate(data.exam_points)
    )
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" role="img" aria-labelledby="roadmap-title roadmap-desc">
<title id="roadmap-title">{escape(data.title)}</title><desc id="roadmap-desc">{escape(data.summary)}</desc>
<defs><marker id="arrow" markerWidth="10" markerHeight="10" refX="7" refY="3" orient="auto"><path d="M0,0 L0,6 L8,3 z" fill="#8b5cf6"/></marker></defs>
<style>.bg{{fill:#0e1729}}.node{{fill:#17243d;stroke:#50658d;stroke-width:1.5}}.arrow{{stroke:#8b5cf6;stroke-width:2;fill:none}}text{{font-family:Inter,Arial,sans-serif;fill:#dce7fa}}.title{{font-size:28px;font-weight:700}}.summary{{font-size:14px;fill:#9eacc5}}.label{{font-size:15px;font-weight:700}}.body{{font-size:12px;fill:#b6c3d9}}.source{{font-size:10px;fill:#9f8df1}}.section{{font-size:17px;font-weight:700;fill:#f4f7ff}}</style>
<rect width="100%" height="100%" class="bg"/>{_text(40, 48, data.title, width=75, css="title")}{_text(40, 90, data.summary, width=120, css="summary")}
{''.join(arrows)}{''.join(boxes)}{exams}</svg>'''
