import json
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4


def timestamp(seconds):
    seconds = int(seconds)
    return f'{seconds // 3600:02}:{seconds % 3600 // 60:02}:{seconds % 60:02}'


def export_lines(project, segments, mode='edited', draft=None):
    names = json.loads(project['speakers'])
    lines = [project['title'], f"녹음 파일: {project['filename']}"]
    if draft:
        lines.append('AI 생성 초안 · 원문 대조와 사실 확인이 필요합니다.')
        mapping = {s['id']: s for s in segments}
        for section in json.loads(draft['content']):
            lines.extend(['', section['heading'], section['body']])
            sources = [timestamp(mapping[i]['start']) for i in section['segment_ids'] if i in mapping]
            lines.append('근거 녹취: ' + ', '.join(sources))
    else:
        label = {'original': '자동 녹취 원문 · 완전한 축어록을 보장하지 않습니다.',
                 'edited': '편집 녹취 · 미검토 문장이 포함될 수 있습니다.',
                 'reviewed': '검토 완료로 표시된 발언만 내보냈습니다.'}[mode]
        lines.append(label)
        for segment in segments:
            if mode == 'reviewed' and not segment['reviewed']:
                continue
            text = segment['original_text'] if mode == 'original' else segment['text']
            label = names.get(segment['speaker'], '화자 미지정')
            state = '자동 원문' if mode == 'original' else ('검토 완료' if segment['reviewed'] else '미검토')
            lines.extend(['', f"[{timestamp(segment['start'])} – {timestamp(segment['end'])}] {label} · {state}", text])
    return lines


def build_pdf(path: Path, lines):
    font = Path(__file__).parent / 'static' / 'fonts' / 'NanumGothic-Regular.ttf'
    if not font.is_file():
        raise RuntimeError('PDF용 한글 글꼴이 없습니다. 앱 설치 파일을 확인해 주세요.')
    if 'ArchiveKorean' not in pdfmetrics.getRegisteredFontNames():
        pdfmetrics.registerFont(TTFont('ArchiveKorean', str(font)))
    style = ParagraphStyle('body', fontName='ArchiveKorean', fontSize=10, leading=17, wordWrap='CJK', alignment=TA_LEFT,
                           textColor=colors.HexColor('#263C3C'), spaceAfter=6)
    title = ParagraphStyle('title', parent=style, fontSize=20, leading=28, spaceAfter=20)
    document = SimpleDocTemplate(str(path), pagesize=A4, rightMargin=48, leftMargin=48, topMargin=48, bottomMargin=48)
    story = []
    for index, line in enumerate(lines):
        story.append(Paragraph(escape(line).replace('\n', '<br/>'), title if index == 0 else style) if line else Spacer(1, 8))

    def footer(canvas, doc):
        canvas.setFont('ArchiveKorean', 8)
        canvas.setFillColor(colors.HexColor('#748383'))
        canvas.drawString(48, 26, '목소리 기록실 · 로컬 녹취')
        canvas.drawRightString(A4[0] - 48, 26, str(doc.page))

    document.build(story, onFirstPage=footer, onLaterPages=footer)
