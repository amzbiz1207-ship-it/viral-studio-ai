"""Friendly Markdown, Word and PDF download bytes with safe filenames."""
from __future__ import annotations
import io
import re
import unicodedata
from datetime import datetime
from html import unescape
from xml.sax.saxutils import escape


def filename(kind, subject, ext, now=None):
    now=now or datetime.now()
    stem=unicodedata.normalize('NFKD', f'{kind}_{subject}')
    stem=''.join(c if (c.isascii() and c.isalnum()) else '_' for c in stem)
    stem=re.sub('_+', '_', stem).strip('_')[:75] or 'result'
    return f'{stem}_{now:%Y%m%d_%H%M%S}.{ext}'


def plain(text):
    text=unescape(re.sub(r'<br\s*/?>','\n',text, flags=re.I))
    text=re.sub(r'<[^>]+>', '', text)
    return re.sub(r'\*\*(.*?)\*\*',r'\1',text)


def docx_bytes(title, md):
    from docx import Document
    from docx.shared import Inches, Pt
    doc=Document()
    sec=doc.sections[0]
    sec.top_margin=sec.bottom_margin=Inches(.75)
    doc.styles['Normal'].font.size=Pt(10)
    doc.add_heading(plain(title),0)
    lines=md.splitlines()
    index=0
    while index<len(lines):
        line=lines[index]
        if not line.strip():
            index+=1; continue
        s=plain(line).strip()
        if line.strip().startswith('|') and not re.fullmatch(r'[|\s:\-]+',line):
            rows=[]
            while index<len(lines) and lines[index].strip().startswith('|'):
                candidate=lines[index].strip()
                if not re.fullmatch(r'[|\s:\-]+',candidate):
                    rows.append([plain(c.strip()) for c in candidate.strip('|').split('|')])
                index+=1
            if rows:
                width=max(len(r) for r in rows)
                if width<=7:
                    table=doc.add_table(rows=1,cols=width)
                    table.style='Light Shading Accent 1'
                    for j,value in enumerate(rows[0]): table.rows[0].cells[j].text=value
                    for row in rows[1:]:
                        cells=table.add_row().cells
                        for j,value in enumerate(row): cells[j].text=value
                    for cell in table.rows[0].cells:
                        for paragraph in cell.paragraphs:
                            for run in paragraph.runs: run.bold=True
                else:
                    for row in rows:doc.add_paragraph(' • '.join(row))
            continue
        if s.startswith('#'):
            doc.add_heading(s.lstrip('# ').strip(),level=min(3,len(s)-len(s.lstrip('#'))))
        elif re.match(r'^\s*[-*] ',line):
            doc.add_paragraph(plain(re.sub(r'^\s*[-*] ', '',line)),style='List Bullet')
        elif re.match(r'^\s*\d+[.)] ',line):
            doc.add_paragraph(plain(re.sub(r'^\s*\d+[.)] ', '',line)),style='List Number')
        elif s not in ('---','***'):
            doc.add_paragraph(s)
        index+=1
    stream=io.BytesIO();doc.save(stream);return stream.getvalue()


def pdf_bytes(title, md):
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib import colors
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from pathlib import Path
    font_path='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
    if not Path(font_path).exists():
        raise RuntimeError('Unicode PDF font unavailable')
    if 'ViralUnicode' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ViralUnicode',font_path))
    styles=getSampleStyleSheet()
    base=ParagraphStyle('VBase',parent=styles['Normal'],fontName='ViralUnicode',fontSize=9.2,leading=14,spaceAfter=7)
    h=ParagraphStyle('VHeading',parent=base,fontSize=14,leading=19,textColor=colors.HexColor('#183149'),spaceBefore=12,spaceAfter=7)
    main=ParagraphStyle('VTitle',parent=h,fontSize=20,leading=26,spaceAfter=18)
    b=io.BytesIO();doc=SimpleDocTemplate(b,pagesize=(595,842),leftMargin=42,rightMargin=42,topMargin=44,bottomMargin=44)
    story=[Paragraph(escape(plain(title)),main)]
    for line in md.splitlines():
        s=plain(line).strip()
        if not s or s in ('---','***'): continue
        if s.startswith('#'):
            story.append(Paragraph(escape(s.lstrip('# ').strip()),h))
        elif s.startswith('|'):
            if not re.fullmatch(r'[|\s:\-]+',s):
                story.append(Paragraph(escape('  •  '.join(x.strip() for x in s.strip('|').split('|'))),base))
        else:
            story.append(Paragraph(escape(s),base))
    doc.build(story)
    return b.getvalue()
