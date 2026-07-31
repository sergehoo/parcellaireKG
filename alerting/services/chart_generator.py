"""Graphiques du rapport en SVG inline (Phase 4).

SVG généré côté serveur → rendu nativement par WeasyPrint, 100 % hors-ligne
(aucune dépendance lourde type Matplotlib, absente de l'environnement).
"""
from xml.sax.saxutils import escape

BLUE = "#2563eb"      # paiement
ORANGE = "#ea580c"    # construction
GREEN = "#059669"     # commercialisation
SEV_COLORS = {"INFORMATION": "#2563eb", "VIGILANCE": "#d97706",
              "IMPORTANT": "#ea580c", "CRITICAL": "#e11d48"}


def payment_vs_construction_svg(rows, width=520):
    """Barres horizontales groupées paiement vs construction par programme.
    `rows` : [{'label', 'payment', 'construction'}]. Valeurs en % (0-100)."""
    rows = [r for r in rows if r.get("label")][:12]
    if not rows:
        return ""
    row_h = 34
    pad_left = 150
    bar_w = width - pad_left - 60
    height = 30 + len(rows) * row_h
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'font-family="Helvetica, Arial, sans-serif" font-size="10">']
    y = 20
    for r in rows:
        label = escape(str(r["label"])[:24])
        pay = max(0, min(float(r.get("payment") or 0), 100))
        con = max(0, min(float(r.get("construction") or 0), 100))
        parts.append(f'<text x="8" y="{y + 11}" fill="#334155">{label}</text>')
        parts.append(f'<rect x="{pad_left}" y="{y}" width="{bar_w * pay / 100:.1f}" height="10" '
                     f'fill="{BLUE}" rx="2"/>')
        parts.append(f'<text x="{pad_left + bar_w * pay / 100 + 4:.1f}" y="{y + 9}" '
                     f'fill="#334155">{pay:.0f}%</text>')
        parts.append(f'<rect x="{pad_left}" y="{y + 13}" width="{bar_w * con / 100:.1f}" height="10" '
                     f'fill="{ORANGE}" rx="2"/>')
        parts.append(f'<text x="{pad_left + bar_w * con / 100 + 4:.1f}" y="{y + 22}" '
                     f'fill="#334155">{con:.0f}%</text>')
        y += row_h
    # légende
    parts.append(f'<rect x="{pad_left}" y="4" width="9" height="9" fill="{BLUE}"/>'
                 f'<text x="{pad_left + 13}" y="12" fill="#334155">Paiement</text>'
                 f'<rect x="{pad_left + 75}" y="4" width="9" height="9" fill="{ORANGE}"/>'
                 f'<text x="{pad_left + 88}" y="12" fill="#334155">Construction</text>')
    parts.append("</svg>")
    return "".join(parts)


def severity_distribution_svg(counts, width=320):
    """Barres de répartition des détections par sévérité.
    `counts` : {'CRITICAL': n, 'IMPORTANT': n, ...}."""
    order = ["CRITICAL", "IMPORTANT", "VIGILANCE", "INFORMATION"]
    labels = {"CRITICAL": "Critique", "IMPORTANT": "Important",
              "VIGILANCE": "Vigilance", "INFORMATION": "Information"}
    data = [(k, int(counts.get(k, 0))) for k in order]
    mx = max([n for _, n in data] + [1])
    row_h = 26
    pad_left = 90
    bar_w = width - pad_left - 40
    height = 10 + len(data) * row_h
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
             f'font-family="Helvetica, Arial, sans-serif" font-size="10">']
    y = 8
    for k, n in data:
        parts.append(f'<text x="8" y="{y + 12}" fill="#334155">{labels[k]}</text>')
        parts.append(f'<rect x="{pad_left}" y="{y + 3}" width="{bar_w * n / mx:.1f}" height="12" '
                     f'fill="{SEV_COLORS[k]}" rx="2"/>')
        parts.append(f'<text x="{pad_left + bar_w * n / mx + 5:.1f}" y="{y + 13}" '
                     f'fill="#334155">{n}</text>')
        y += row_h
    parts.append("</svg>")
    return "".join(parts)
