"""기존 XLSX에 대학별 집계표와 편집 가능한 Excel 차트를 추가합니다."""
from collections import Counter, defaultdict
from io import BytesIO
from xml.sax.saxutils import escape
import xml.etree.ElementTree as ET
from zipfile import ZipFile, ZIP_DEFLATED

S = 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'
R = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'
P = 'http://schemas.openxmlformats.org/package/2006/relationships'
C = 'http://schemas.openxmlformats.org/drawingml/2006/chart'
A = 'http://schemas.openxmlformats.org/drawingml/2006/main'
CATEGORIES = ['입시·모집','연구·성과','행사·특강','장학·지원','캠퍼스','대학 소식']


def statistics(items):
    by_school = defaultdict(Counter)
    for item in items:
        by_school[item.get('school') or '대학명 미확인'][item.get('category') or '대학 소식'] += 1
    totals = Counter()
    for counts in by_school.values():
        totals.update(counts)
    categories = CATEGORIES + sorted(set(totals)-set(CATEGORIES))
    return dict(schools=dict(sorted(by_school.items())), totals=totals,
                categories=categories, count=len(items))


def text_cell(ref, value, style=0):
    return f'<c r="{ref}" s="{style}" t="inlineStr"><is><t>{escape(str(value))}</t></is></c>'


def number_cell(ref, value, style=0, formula=None):
    return f'<c r="{ref}" s="{style}">'+(f'<f>{escape(formula)}</f>' if formula else '')+f'<v>{value}</v></c>'


def summary_parts(items):
    stats = statistics(items)
    cats, total = stats['categories'], stats['count']
    last_col = chr(66+len(cats))
    rows = []
    def row(index, cells):
        rows.append(f'<row r="{index}">'+''.join(cells)+'</row>')
    row(1, [text_cell('A1','대학 기사 집계',5),text_cell('K1','보도자료 건수와 비율',5)])
    row(2, [text_cell('A2',f'다운로드 조건에 해당하는 기사 {total}건 · 대학명 표기별 집계 · 복수 대학 기사는 하나의 묶음으로 집계')])
    row(3, [text_cell('A3','대학명',2)]+[text_cell(f'{chr(66+i)}3',cat,2) for i,cat in enumerate(cats)]+[text_cell(f'{last_col}3','총계',2)])
    index = 4
    for school, counts in stats['schools'].items():
        row(index,[text_cell(f'A{index}',school)]+[number_cell(f'{chr(66+i)}{index}',counts[cat]) for i,cat in enumerate(cats)]+[number_cell(f'{last_col}{index}',sum(counts.values()))])
        index += 1
    row(index,[text_cell(f'A{index}','총계',3)]+[number_cell(f'{chr(66+i)}{index}',stats['totals'][cat],3) for i,cat in enumerate(cats)]+[number_cell(f'{last_col}{index}',total,3)])
    ratio_heading = index+3
    row(ratio_heading,[text_cell(f'A{ratio_heading}','구분별 비율',5)])
    row(ratio_heading+1,[text_cell(f'{chr(65+i)}{ratio_heading+1}',name,2) for i,name in enumerate(['구분','건수','비율','표시용'])])
    start = ratio_heading+2
    for i,cat in enumerate(cats):
        count = stats['totals'][cat]
        ratio = count/total if total else 0
        j = start+i
        row(j,[text_cell(f'A{j}',cat),number_cell(f'B{j}',count),number_cell(f'C{j}',ratio,4),text_cell(f'D{j}',f'{count}건 ({ratio:.1%})')])
    j = start+len(cats)
    row(j,[text_cell(f'A{j}','합계',3),number_cell(f'B{j}',total,3),number_cell(f'C{j}',1 if total else 0,4),text_cell(f'D{j}',f'{total}건 ({"100.0%" if total else "0.0%"})',3)])
    sheet = f'<worksheet xmlns="{S}" xmlns:r="{R}"><sheetViews><sheetView workbookViewId="0"><pane ySplit="3" topLeftCell="A4" activePane="bottomLeft" state="frozen"/></sheetView></sheetViews><cols><col min="1" max="1" width="38" customWidth="1"/><col min="2" max="9" width="17" customWidth="1"/><col min="11" max="20" width="12" customWidth="1"/></cols><sheetData>'+''.join(rows)+f'</sheetData><autoFilter ref="A3:{last_col}{index-1 if index>4 else 3}"/><drawing r:id="rId1"/></worksheet>'
    def cache(values,numeric=False):
        tag='numCache' if numeric else 'strCache'
        return f'<c:{tag}>'+('<c:formatCode>0</c:formatCode>' if numeric else '')+f'<c:ptCount val="{len(values)}"/>'+''.join(f'<c:pt idx="{i}"><c:v>{escape(str(v))}</c:v></c:pt>' for i,v in enumerate(values))+f'</c:{tag}>'
    end=start+len(cats)-1
    labels=[]
    for i,cat in enumerate(cats):
        n=stats['totals'][cat]
        label=f'{n}건 ({n/total:.1%})' if total else '0건 (0.0%)'
        labels.append(f'<c:dLbl><c:idx val="{i}"/><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="ko-KR"/><a:t>{label}</a:t></a:r></a:p></c:rich></c:tx><c:dLblPos val="outEnd"/></c:dLbl>')
    chart = f'<c:chartSpace xmlns:c="{C}" xmlns:a="{A}"><c:lang val="ko-KR"/><c:chart><c:title><c:tx><c:rich><a:bodyPr/><a:lstStyle/><a:p><a:r><a:rPr lang="ko-KR" b="1" sz="1600"/><a:t>보도자료 건수와 비율</a:t></a:r></a:p></c:rich></c:tx></c:title><c:plotArea><c:layout/><c:barChart><c:barDir val="bar"/><c:grouping val="clustered"/><c:ser><c:idx val="0"/><c:order val="0"/><c:tx><c:v>기사 건수</c:v></c:tx><c:spPr><a:solidFill><a:srgbClr val="A4CFBE"/></a:solidFill><a:ln><a:noFill/></a:ln></c:spPr><c:cat><c:strRef><c:f>\'요약 통계\'!$A${start}:$A${end}</c:f>'+cache(cats)+f'</c:strRef></c:cat><c:val><c:numRef><c:f>\'요약 통계\'!$B${start}:$B${end}</c:f>'+cache([stats['totals'][cat] for cat in cats],True)+'</c:numRef></c:val></c:ser><c:dLbls>'+''.join(labels)+'<c:showLegendKey val="0"/><c:showVal val="0"/><c:showCatName val="0"/><c:showSerName val="0"/><c:showPercent val="0"/></c:dLbls><c:gapWidth val="65"/><c:axId val="100"/><c:axId val="200"/></c:barChart><c:catAx><c:axId val="100"/><c:scaling><c:orientation val="maxMin"/></c:scaling><c:axPos val="l"/><c:tickLblPos val="nextTo"/><c:crossAx val="200"/><c:crosses val="autoZero"/><c:lblAlgn val="ctr"/><c:lblOffset val="100"/></c:catAx><c:valAx><c:axId val="200"/><c:scaling><c:orientation val="minMax"/><c:min val="0"/></c:scaling><c:axPos val="b"/><c:majorGridlines/><c:numFmt formatCode="0" sourceLinked="0"/><c:tickLblPos val="nextTo"/><c:crossAx val="100"/><c:crosses val="max"/><c:crossBetween val="between"/></c:valAx></c:plotArea><c:plotVisOnly val="1"/></c:chart></c:chartSpace>'
    drawing = f'<xdr:wsDr xmlns:xdr="http://schemas.openxmlformats.org/drawingml/2006/spreadsheetDrawing" xmlns:a="{A}"><xdr:twoCellAnchor><xdr:from><xdr:col>10</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>2</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:from><xdr:to><xdr:col>20</xdr:col><xdr:colOff>0</xdr:colOff><xdr:row>23</xdr:row><xdr:rowOff>0</xdr:rowOff></xdr:to><xdr:graphicFrame macro=""><xdr:nvGraphicFramePr><xdr:cNvPr id="2" name="기사 구분별 통계"/><xdr:cNvGraphicFramePr/></xdr:nvGraphicFramePr><xdr:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/></xdr:xfrm><a:graphic><a:graphicData uri="{C}"><c:chart xmlns:c="{C}" xmlns:r="{R}" r:id="rId1"/></a:graphicData></a:graphic></xdr:graphicFrame><xdr:clientData/></xdr:twoCellAnchor></xdr:wsDr>'
    return sheet,chart,drawing


def add_summary(workbook, items):
    sheet,chart,drawing=summary_parts(items)
    with ZipFile(BytesIO(workbook)) as source:
        files={name:source.read(name) for name in source.namelist()}
    def modify(path, callback):
        root=ET.fromstring(files[path]);callback(root);files[path]=ET.tostring(root,encoding='utf-8',xml_declaration=True)
    def content_types(root):
        ns=root.tag.split('}')[0]+'}'
        for path,kind in [('worksheets/sheet2.xml','spreadsheetml.worksheet'),('drawings/drawing1.xml','drawing'),('charts/chart1.xml','drawingml.chart')]:
            mime='application/vnd.openxmlformats-officedocument.'+kind+'+xml'
            ET.SubElement(root,ns+'Override',PartName='/xl/'+path,ContentType=mime)
    modify('[Content_Types].xml',content_types)
    def workbook_xml(root):
        sheets=root.find('{'+S+'}sheets')
        sheets.insert(0,ET.Element('{'+S+'}sheet',{'name':'요약 통계','sheetId':'2','{'+R+'}id':'rId3'}))
    modify('xl/workbook.xml',workbook_xml)
    modify('xl/_rels/workbook.xml.rels',lambda root:ET.SubElement(root,'{'+P+'}Relationship',Id='rId3',Type=R+'/worksheet',Target='worksheets/sheet2.xml'))
    def styles(root):
        fonts=root.find('{'+S+'}fonts');f=ET.SubElement(fonts,'{'+S+'}font');ET.SubElement(f,'{'+S+'}b');ET.SubElement(f,'{'+S+'}sz',val='11');ET.SubElement(f,'{'+S+'}name',val='Calibri');fonts.set('count',str(len(fonts)))
        fills=root.find('{'+S+'}fills');fill=ET.SubElement(fills,'{'+S+'}fill');pattern=ET.SubElement(fill,'{'+S+'}patternFill',patternType='solid');ET.SubElement(pattern,'{'+S+'}fgColor',rgb='FFD8EEE5');ET.SubElement(pattern,'{'+S+'}bgColor',indexed='64');fills.set('count',str(len(fills)))
        formats=ET.Element('{'+S+'}numFmts',count='1');ET.SubElement(formats,'{'+S+'}numFmt',numFmtId='164',formatCode='0.0%');root.insert(0,formats)
        xfs=root.find('{'+S+'}cellXfs')
        for font,fill,num in [(2,2,0),(2,2,0),(0,0,164),(2,0,0)]:
            ET.SubElement(xfs,'{'+S+'}xf',fontId=str(font),fillId=str(fill),borderId='0',numFmtId=str(num),xfId='0',applyFont='1',applyFill='1',applyNumberFormat='1')
        xfs.set('count',str(len(xfs)))
    modify('xl/styles.xml',styles)
    files.update({'xl/worksheets/sheet2.xml':sheet.encode(),'xl/charts/chart1.xml':chart.encode(),'xl/drawings/drawing1.xml':drawing.encode(),
        'xl/worksheets/_rels/sheet2.xml.rels':f'<Relationships xmlns="{P}"><Relationship Id="rId1" Type="{R}/drawing" Target="../drawings/drawing1.xml"/></Relationships>'.encode(),
        'xl/drawings/_rels/drawing1.xml.rels':f'<Relationships xmlns="{P}"><Relationship Id="rId1" Type="{R}/chart" Target="../charts/chart1.xml"/></Relationships>'.encode()})
    output=BytesIO()
    with ZipFile(output,'w',ZIP_DEFLATED) as target:
        for name,body in files.items():target.writestr(name,body)
    return output.getvalue()
