"""Render the reviewed P&C Report Studio HTML into a real paginated PDF.

The HTML preview and PDF deliberately share one source: no plain-text fallback
that strips report headings, tables, citations or editorial formatting.
"""
from __future__ import annotations

import html

PRINT_CSS = """
@page {
    size: A4;
    margin: 20mm 16mm 20mm 16mm;
    @top-left {
        content: "POWER & CORRIDORS  /  INTELLIGENCE";
        font: 8pt Arial, sans-serif;
        letter-spacing: 1px;
        color: #7c8795;
    }
    @bottom-left {
        content: "POWER & CORRIDORS  •  SOURCE-QUALIFIED INTELLIGENCE";
        font: 7pt Arial, sans-serif;
        color: #7c8795;
    }
    @bottom-right {
        content: "PAGE " counter(page) " / " counter(pages);
        font: 8pt Arial, sans-serif;
        color: #7c8795;
    }
}
html, body { margin: 0; padding: 0; background: white; }
.pcpub { max-width: none !important; margin: 0 !important;
         padding: 5mm 0 0 !important; border-top: 2mm solid #a58028;
         font-size: 10pt !important; }
.pcpub h1 { font-size: 25pt !important; }
.pcpub h2 { font-size: 14pt !important; break-after: avoid; }
.pcpub p, .pcpub li { orphans: 3; widows: 3; }
.pcpub table { table-layout: auto; font-size: 8.5pt !important; }
.pcpub thead { display: table-header-group; }
.pcpub tr, .pcpub .judgment, .pcpub .source { break-inside: avoid; }
.pcpub .judgment { display: block !important; }
.pcpub .judgment b { display: inline-block; width: 10mm; }
.pcpub a { overflow-wrap: anywhere; }
section, blockquote { break-inside: auto; }
h1, h2, h3, th { break-after: avoid; }
img, svg { max-width: 100%; }
"""

def render_report_pdf(publication_html: str, *, title: str = "") -> bytes:
    """Return an actual PDF byte stream from an already-reviewed publication."""
    if not isinstance(publication_html, str) or not publication_html.strip():
        raise ValueError("Report HTML is empty")
    from weasyprint import HTML, CSS

    document = ("<!doctype html><html lang='en'><head>"
                "<meta charset='utf-8'><title>" + html.escape(title) +
                "</title></head><body>" + publication_html + "</body></html>")
    result = HTML(string=document).write_pdf(stylesheets=[CSS(string=PRINT_CSS)])
    if not result.startswith(b"%PDF-"):
        raise RuntimeError("PDF renderer returned an invalid document")
    return result
