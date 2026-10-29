"""추가 라이브러리 없이 만드는 표준 XLSX 파일."""
from datetime import datetime, timedelta, timezone
from io import BytesIO
import re
from xml.sax.saxutils import escape, quoteattr
from urllib.parse import urlsplit
from zipfile import ZipFile, ZIP_DEFLATED
from excel_summary import add_summary

HEADERS = ['대학명', '보도일자 (한국 시간)', '소재지 (시·도)', '구분', '기사명',
           '기사 URL', '언론사', '캠퍼스·주소', '수집 경로']


def article_row(item):
    date = item.get('date', '')
    try:
        date = datetime.fromisoformat(date).astimezone(timezone(timedelta(hours=9))).strftime('%Y-%m-%d %H:%M:%S')
    except (ValueError, TypeError):
        date = '게시 시각 미제공'
    addresses = []
    for university in item.get('universities', []):
        for campus in university.get('campuses', []):
            addresses.append(f"{university['name']} / {campus['name']} / {campus['address'] or '상세 주소 미확인'}")
    article_url = item.get('original_url') or item.get('url', '')
    return [item.get('school', '대학명 미확인'), date, ' · '.join(item.get('regions', [])) or '지역 미분류',
            item.get('category', ''), item.get('title', ''), article_url,
            item.get('source', ''), '\n'.join(addresses), item.get('feed_source', item.get('source', ''))]


def make_workbook(items):
    items = list(items)
    rows = [HEADERS] + [article_row(item) for item in items]
    xml_rows = []
    hyperlinks, relationships = [], []
    for row_number, values in enumerate(rows, 1):
        cells = []
        for index, value in enumerate(values):
            value = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', str(value))[:32767]
            reference = f'{chr(65+index)}{row_number}'
            is_link = row_number > 1 and index == 5 and urlsplit(value).scheme in ('http','https') and bool(urlsplit(value).netloc)
            if is_link:
                relationship_id = f'rId{len(relationships)+1}'
                hyperlinks.append(f'<hyperlink ref="{reference}" r:id="{relationship_id}"/>')
                relationships.append(f'<Relationship Id="{relationship_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/hyperlink" Target={quoteattr(value)} TargetMode="External"/>')
            # 문자열 셀로 저장하므로 '='로 시작하는 제목도 수식이 되지 않습니다.
            style = ' s="1"' if is_link else ''
            cells.append(f'<c r="{reference}" t="inlineStr"{style}><is><t xml:space="preserve">{escape(value)}</t></is></c>')
        xml_rows.append(f'<row r="{row_number}">{"".join(cells)}</row>')
    worksheet = ('<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews>'
        '<cols><col min="1" max="1" width="26" customWidth="1"/><col min="2" max="2" width="24" customWidth="1"/>'
        '<col min="3" max="4" width="20" customWidth="1"/><col min="5" max="5" width="65" customWidth="1"/>'
        '<col min="6" max="6" width="55" customWidth="1"/><col min="7" max="7" width="22" customWidth="1"/>'
        '<col min="8" max="8" width="70" customWidth="1"/><col min="9" max="9" width="25" customWidth="1"/></cols>'
        f'<sheetData>{"".join(xml_rows)}</sheetData><autoFilter ref="A1:I{len(rows)}"/>'
        + (f'<hyperlinks>{"".join(hyperlinks)}</hyperlinks>' if hyperlinks else '') + '</worksheet>')
    output = BytesIO()
    with ZipFile(output, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        archive.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        archive.writestr('xl/workbook.xml', '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="대학 기사" sheetId="1" r:id="rId1"/></sheets></workbook>')
        archive.writestr('xl/_rels/workbook.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>')
        archive.writestr('xl/worksheets/sheet1.xml', worksheet)
        if relationships:
            archive.writestr('xl/worksheets/_rels/sheet1.xml.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'+''.join(relationships)+'</Relationships>')
        archive.writestr('xl/styles.xml', '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/><name val="Calibri"/></font><font><sz val="11"/><color rgb="FF0563C1"/><name val="Calibri"/><u/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>')
    return add_summary(output.getvalue(), items)
