"""Preserve real clickable hyperlinks in email-printout PDFs.

No URL is automatically visited. Newsletter trackers are retained as leads,
not mistaken for original publisher article URLs. Image-only one-page route
announcements can be sent to vision extraction with explicit API consent.
"""
from __future__ import annotations
import base64
import io
from urllib.parse import urlsplit


def extract_pdf(data, max_pages=60, max_links=150):
    from pypdf import PdfReader
    reader=PdfReader(io.BytesIO(data))
    pages=reader.pages[:max_pages]
    text='\n'.join(p.extract_text() or '' for p in pages)[:90000]
    links=[];seen=set()
    for n,page in enumerate(pages,1):
        for ann_ref in page.get('/Annots') or []:
            try:
                ann=ann_ref.get_object()
                action=ann.get('/A') or {}
                raw=str(action.get('/URI') or '').strip()
                p=urlsplit(raw)
                if p.scheme not in ('https','http') or not p.netloc or raw in seen:continue
                seen.add(raw)
                links.append({'page':n,'url':raw})
                if len(links)>=max_links:break
            except (AttributeError,KeyError,TypeError,ValueError):continue
        if len(links)>=max_links:break
    # Most Gmail printouts retain link annotations even when the visible anchor
    # says only 'Read more'. Keep anchors separate from headlines until verified.
    if links:
        text+='\n\nEMBEDDED CLICKABLE PDF LINKS — unverified destination, not automatically fetched:\n'
        text+='\n'.join(f"Page {l['page']}: {l['url']}" for l in links)
    image_b64=None
    if not text.strip():
        try:
            import fitz  # optional PyMuPDF for graphical one-page announcements
            doc=fitz.open(stream=data,filetype='pdf')
            if len(doc)>0:
                pix=doc[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False)
                image_b64=base64.b64encode(pix.tobytes('png')).decode('ascii')
                text='Image-only document; visual facts must be extracted and checked by an analyst.'
        except (ImportError,RuntimeError,ValueError) as exc:
            raise ValueError('Image-only PDF requires optional PyMuPDF for visual extraction') from exc
    return text[:90000],links,image_b64
