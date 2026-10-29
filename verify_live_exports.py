"""실행 중인 로컬 서버의 목록과 XLSX를 대조합니다. python verify_live_exports.py"""
from datetime import datetime,timedelta,timezone
import io
import json
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from zipfile import ZipFile
import xml.etree.ElementTree as ET

BASE='http://127.0.0.1:8001'
NS={'s':'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}

def main():
    news=json.load(urlopen(BASE+'/news.json',timeout=20))['news']
    kst=timezone(timedelta(hours=9));today=datetime.now(kst).date();start=today-timedelta(days=6)
    scenarios={'all':news,'period_region_category':[n for n in news if n.get('date') and start<=datetime.fromisoformat(n['date']).astimezone(kst).date()<=today and '충남' in n['regions'] and n['category']=='장학·지원'],
               'empty':[],'reverse':list(reversed(news[:5]))}
    results={}
    for name,rows in scenarios.items():
        ids=[n['id'] for n in rows];payload=ids+ids[:1] if len(ids)<5000 else ids
        request=Request(BASE+'/export.xlsx',data=json.dumps({'ids':payload}).encode(),headers={'Content-Type':'application/json'})
        with ZipFile(io.BytesIO(urlopen(request,timeout=40).read())) as archive:
            sheet=ET.fromstring(archive.read('xl/worksheets/sheet1.xml'))
            output=sheet.findall('.//s:row',NS)[1:]
            assert len(output)==len(rows),(name,len(output),len(rows))
            for xml,item in zip(output,rows):
                cells={c.get('r').rstrip('0123456789'):''.join(c.itertext()) for c in xml.findall('s:c',NS)}
                assert cells['A']==item['school'] and cells['E']==item['title']
                assert cells['F']==(item.get('original_url') or item['url'])
            summary=ET.fromstring(archive.read('xl/worksheets/sheet2.xml'))
            assert str(len(rows))+'건' in ''.join(summary.itertext())
        results[name]=len(rows)
        print('PASS export',name,len(rows))
    try:
        request=Request(BASE+'/export.xlsx',data=b'{"ids":["nonexistent-audit-id"]}',headers={'Content-Type':'application/json'})
        urlopen(request,timeout=10)
        raise AssertionError('Expected stale selection rejection')
    except HTTPError as error:assert error.code==409
    print('PASS stale selection handling')
    return results

if __name__=='__main__':main()
