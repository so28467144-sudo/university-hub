'use strict';
const { categories } = window.CAMPUS_DATA;
let news=window.CAMPUS_DATA.news;
let rssStatus=window.CAMPUS_DATA.status;
const escapeHtml=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const dateLabel=value=>{
 const date=new Date(value);
 if(!value||Number.isNaN(date.getTime()))return '게시 시각 미제공';
 const parts=new Intl.DateTimeFormat('ko-KR',{timeZone:'Asia/Seoul',year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(date);
 const part=type=>parts.find(p=>p.type===type).value;
 return `${part('year')}.${part('month')}.${part('day')} ${part('hour')}:${part('minute')}`;
};
const inRegion=(n,region)=>{
 const assigned=(Array.isArray(n.regions)?n.regions:[n.region]).filter(r=>r&&r!=='지역 미분류');
 return region==='지역 미분류'?assigned.length===0:assigned.includes(region);
};
// 소식 데이터 유무와 관계없이 모든 시·도 버튼을 표시합니다.
const regions = ['전체 지역', '서울', '부산', '대구', '인천', '광주', '대전', '울산', '세종', '경기도', '강원', '충북', '충남', '전북', '전남', '경북', '경남', '제주', '해외', '지역 미분류'];
let saved=new Set();try{const value=JSON.parse(localStorage.getItem('campus-on-saved')||'[]');if(Array.isArray(value))saved=new Set(value.filter(x=>typeof x==='string'));}catch{}
const isArticleSaved=article=>(article.duplicate_ids||[article.id]).some(id=>saved.has(id));
function normalizeSearch(value){return String(value||'').normalize('NFKC').toLowerCase().replace(/\s+/g,'');}
function matchesSearch(article,query){
 if(!query.trim())return true;
 const text=normalizeSearch([article.school,...(article.school_names||[]),...(article.school_aliases||[]),article.title,article.body,article.city,article.region,article.source].join(' '));
 if(text.includes(normalizeSearch(query)))return true;
 return query.trim().split(/\s+/).every(term=>text.includes(normalizeSearch(term)));
}
const state={selectedRegions:new Set(),category:'전체',query:'',sort:'newest',savedOnly:false,limit:7,period:'all',startDate:'',endDate:''};
const $=id=>document.getElementById(id);
function koreanDay(value){
 const stamp=new Date(value).getTime();
 return Number.isNaN(stamp)?'':new Date(stamp+9*60*60*1000).toISOString().slice(0,10);
}
function periodBounds(period=state.period){
 if(period==='all')return {start:'',end:'',error:''};
 if(period==='custom'){
 const error=!state.startDate||!state.endDate?'시작일과 종료일을 모두 선택해 주세요.':state.startDate>state.endDate?'종료일은 시작일보다 빠를 수 없습니다.':'';
 return {start:state.startDate,end:state.endDate,error};
 }
 const today=koreanDay(new Date());
 const days=period==='7days'?7:period==='30days'?30:1;
 const start=new Date(Date.parse(today+'T00:00:00Z')-(days-1)*86400000).toISOString().slice(0,10);
 return {start,end:today,error:''};
}
function withinPeriod(article,bounds,period=state.period){
 if(period==='all')return true;
 if(bounds.error||!article.date)return false;
 const day=koreanDay(article.date);
 return !!day&&day>=bounds.start&&day<=bounds.end;
}
let exportRows=[];
let exporting=false;
let exportNoticeTimer;
function clearExportNotice(){
 clearTimeout(exportNoticeTimer);
 $('exportStatus').textContent='';
}
function showExportNotice(message){
 clearExportNotice();
 $('exportStatus').textContent=message;
 exportNoticeTimer=setTimeout(()=>{$('exportStatus').textContent='';},5000);
}
function showUniversityAddresses(article){
 $('detailDuplicates').textContent=article.duplicate_count>1?`같은 내용의 기사 ${article.duplicate_count}건 중 RSS 요약과 제목에 확인된 정보가 더 많은 대표 기사를 표시합니다.`:'';
 const box=$('detailLocations');box.replaceChildren();
 if(article.foreign_universities?.length){const p=document.createElement('p');p.textContent='기사의 해외 대학: '+article.foreign_universities.join(' / ');box.append(p);}
 if(article.background_universities?.length){const p=document.createElement('p');p.textContent='학력·출신 정보로만 언급되어 소재지에서 제외: '+[...new Set(article.background_universities.map(u=>u.name))].join(' / ');box.append(p);}
 if(article.mentioned_regions?.length){const p=document.createElement('p');p.textContent='기사에 명시된 지역: '+article.mentioned_regions.map(place=>`${place.region} (${place.method==='summary_region'?'RSS 요약':'제목'}: “${place.text}”)`).join(' / ');box.append(p);}
 for(const program of article.education_programs||[]){
 const p=document.createElement('p');p.textContent=`${program.name} · ${program.region}\n${program.kind} / 운영 지자체: ${program.locality} (일반 대학교와 구분)`;box.append(p);
 const link=document.createElement('a');link.href=program.source;link.target='_blank';link.rel='noopener noreferrer';link.textContent='교육과정 운영 근거 확인 ↗';box.append(link);
 }
 if(!article.universities?.length){if(!article.mentioned_regions?.length)box.textContent='국내 대학 주소나 명시된 지역을 확인하지 못해 지역 미분류로 표시합니다.';return;}
 const heading=document.createElement('strong');heading.textContent='대학 · 캠퍼스 소재지 확인';box.append(heading);
 for(const university of article.universities){
 const p=document.createElement('p');
 const status=university.method==='national_network'?'대학명은 확인했지만 기사에 캠퍼스가 명시되지 않아 지역을 특정하지 못했습니다.':university.affiliation_type==='university_hospital'?`확인된 대학 부속기관: ${university.campus_names.join(' / ')}`:university.campus_status==='matched'?`확인된 캠퍼스: ${university.campus_names.join(' / ')}`:university.campus_status==='region_only'?`캠퍼스 지역 확인: ${university.campus_names.join(' / ')} (시·군·구만 확인, 상세 주소 미확인)`:university.campus_status==='unresolved'?`주소 미확인: ${university.campus_names.join(' / ')} (본교 주소로 대체하지 않습니다)`:'기사에서 캠퍼스를 특정하지 못했습니다. 아래는 등록된 소재지 후보입니다.';
 p.textContent=`${university.name} · ${university.regions.join(' / ')||'지역 미분류'}\n${status}`;
 box.append(p);
 if(university.campuses?.length){
 for(const campus of university.campuses){
 const address=document.createElement('p');address.className='campus-address';
 address.textContent=`${campus.name} · ${campus.region}\n${campus.address||'상세 주소 미확인'}`;box.append(address);
 if(campus.source){const source=document.createElement('a');source.href=campus.source;source.target='_blank';source.rel='noopener noreferrer';source.textContent=campus.source.includes('data.go.kr')?'공공 주소 데이터 확인 ↗':campus.source.includes('mois.go.kr')?'시·군·구 확인 근거 ↗':'캠퍼스 공식 주소 안내 ↗';box.append(source);}
 }
 }else if(!university.campus_status){const address=document.createElement('p');address.textContent=university.addresses.join('\n');box.append(address);}
 }
}
function render(){
 const bounds=periodBounds();
 const baseRows=news.filter(n=>(state.selectedRegions.size===0||[...state.selectedRegions].some(r=>inRegion(n,r)))&&(state.category==='전체'||n.category===state.category)&&(!state.savedOnly||isArticleSaved(n))&&matchesSearch(n,state.query));
 const periodLabels={all:'전체',today:'오늘','7days':'최근 7일','30days':'최근 30일',custom:'직접 선택'};
 document.querySelectorAll('[data-period]').forEach(button=>{
 const period=button.dataset.period,active=period===state.period,range=periodBounds(period);
 const count=baseRows.filter(n=>withinPeriod(n,range,period)).length;
 button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));
 button.textContent=periodLabels[period]+(period==='all'||range.error?'':` (${count}건)`);
 button.title=range.error?range.error:`현재 지역·검색·유형 조건에서 ${count}건`;
 });
 $('customDates').hidden=state.period!=='custom';
 $('periodError').textContent=bounds.error;
 $('periodHint').textContent=state.period==='all'?'저장된 전체 기사 · 한국 시간 기준':bounds.error?'':`${bounds.start} ~ ${bounds.end} · 양 끝 날짜 포함 · 한국 시간 기준`;
 $('regions').replaceChildren(...regions.map((name,i)=>{
 const b=document.createElement('label');
 const count=i===0?news.length:news.filter(n=>inRegion(n,name)).length;
 const checked=i===0?state.selectedRegions.size===0:state.selectedRegions.has(name);
 b.className='region-option'+(checked?' selected':'');
 const input=document.createElement('input');input.type='checkbox';input.checked=checked;input.value=name;
 input.setAttribute('aria-label',`${name}, 소식 ${count}건`);
 const text=document.createElement('span');text.textContent=i===0?'전체':name;
 const badge=document.createElement('small');badge.textContent=`${count}건`;
 b.append(input,text,badge);
 input.onchange=()=>{
 if(i===0)state.selectedRegions.clear();
 else if(input.checked)state.selectedRegions.add(name);
 else state.selectedRegions.delete(name);
 state.limit=7;render();
 [...$('regions').querySelectorAll('input')].find(el=>el.value===name)?.focus({preventScroll:true});};
 return b;
 }));
 $('categories').replaceChildren(...categories.map(name=>{const b=document.createElement('button');b.textContent=name;b.className='category'+(state.category===name?' active':'');b.setAttribute('aria-pressed',String(state.category===name));b.onclick=()=>{state.category=name;state.limit=7;render();};return b;}));
 const regionLabel=state.selectedRegions.size?[...state.selectedRegions].join(' · '):'전국';
 let rows=baseRows.filter(n=>withinPeriod(n,bounds));
 if(!bounds.error)$('periodHint').textContent+=` · ${rows.length}건`;
 rows.sort((a,b)=>state.sort==='name'?a.school.localeCompare(b.school,'ko'):!a.date&&!b.date?0:!a.date?1:!b.date?-1:state.sort==='oldest'?a.date.localeCompare(b.date):b.date.localeCompare(a.date));
 exportRows=rows;
 $('exportExcel').disabled=exporting||rows.length===0;
 $('exportExcel').textContent=exporting?'엑셀 만드는 중…':`엑셀 다운로드 (${rows.length}건)`;
 $('feedTitle').textContent=state.savedOnly?'관심 소식':`${regionLabel} 대학 소식`;
 $('resultCount').innerHTML=`소식 <b>${rows.length}</b>건`;
 const collecting=rssStatus.state==='collecting';
 const searchProgress=rssStatus.search_plan_total?` 확장 검색: 회차당 최대 ${rssStatus.search_batch_size}개, 전체 ${rssStatus.search_plan_total}개 검색을 순환${collecting?` (현재 ${rssStatus.search_completed||0}개 완료)`:''}.`:'';
 const stamp=rssStatus.lastSuccess?` 마지막 정상 수집: ${dateLabel(rssStatus.lastSuccess)}.`:'';
 const errorText=rssStatus.errors?.length?' 일부 수집에 실패했습니다. 이전에 저장된 기사가 있으면 계속 표시합니다.':'';
 const sourceNames=(rssStatus.sources||[]).map(s=>`${s.name}: ${s.ok?`전체 ${s.total??'?'}건 중 대학 관련 ${s.count}건`:'수집 실패'}`).join(' / ');
 $('rssStatus').textContent=(collecting?'RSS를 수집하고 있습니다. 기존 기사는 계속 조회할 수 있습니다.':rssStatus.state==='error'?'RSS를 가져오지 못했습니다. 인터넷 연결과 RSS 주소를 확인해 주세요.':'RSS에서 대학 관련 기사를 수집합니다. 30분 간격으로 갱신합니다.')+searchProgress+stamp+errorText+(sourceNames?` (${sourceNames})`:'')+' 지역은 대학명과 대학 주소록을 대조해 분류합니다. SBS RSS는 개인의 비상업적 이용 기준으로 연결했습니다.';
 $('savedCount').textContent=news.filter(isArticleSaved).length;$('allNews').classList.toggle('active',!state.savedOnly);$('savedNews').classList.toggle('active',state.savedOnly);
 $('newsList').replaceChildren(...rows.slice(0,state.limit).map(n=>{
 const card=document.createElement('article');card.className='news-card';
 const tone=n.region==='서울'?'#355d86':'#38664f';
 card.innerHTML=`<div class="university-mark" style="--tone:${tone};--tint:${n.region==='서울'?'#edf2f8':'#eef3ed'}" aria-hidden="true">${escapeHtml(n.mark)}</div><div class="card-main"><div class="meta"><strong>${escapeHtml(n.school)}</strong><span class="dot">·</span><span>${escapeHtml(n.city)}</span><span class="dot">·</span><span>${escapeHtml(n.source)}</span></div><button class="title-button">${escapeHtml(n.title)}</button><p class="excerpt">${escapeHtml(n.body)}</p><div class="published-at"><span>게시</span><time datetime="${escapeHtml(n.date)}">${escapeHtml(dateLabel(n.date))}</time><span class="timezone-label">한국 시간</span></div><span class="tag">${escapeHtml(n.category)}</span></div><button class="bookmark${isArticleSaved(n)?' saved':''}" aria-label="${escapeHtml(n.school)} 소식 ${isArticleSaved(n)?'저장 해제':'저장'}" aria-pressed="${isArticleSaved(n)}">${isArticleSaved(n)?'★':'☆'}</button>`;
 card.querySelector('.title-button').onclick=()=>{$('detailTitle').textContent=n.title;$('detailMeta').textContent=`${n.school} · ${n.city} · ${n.source} · ${dateLabel(n.date)}`;$('detailBody').textContent=n.body;showUniversityAddresses(n);$('official').href=n.original_url||n.url;$('official').textContent=n.via_google&&!n.original_url?'기사 보기 (구글 뉴스) ↗':'기사 원문 보기 ↗';$('detail').showModal();};
 card.querySelector('.bookmark').onclick=()=>{if(isArticleSaved(n)){for(const id of n.duplicate_ids||[n.id])saved.delete(id);}else saved.add(n.id);try{localStorage.setItem('campus-on-saved',JSON.stringify([...saved]));}catch{}render();};return card;
 }));$('empty').hidden=rows.length>0;$('more').hidden=rows.length<=state.limit;
 const regionHasNews=state.selectedRegions.size===0||news.some(n=>[...state.selectedRegions].some(r=>inRegion(n,r)));
 $('empty').querySelector('h3').textContent=regionHasNews?'조건에 맞는 소식이 없어요':'선택한 지역에 등록된 소식이 아직 없어요';
 $('empty').querySelector('p').textContent=regionHasNews?'다른 검색어나 지역으로 다시 찾아보세요.':'다른 시·도를 선택해 소식을 확인해 보세요.';
 if(!news.length){$('empty').querySelector('h3').textContent=collecting?'대학 소식을 가져오고 있어요':'수집된 대학 기사가 아직 없어요';$('empty').querySelector('p').textContent='RSS에 대학 관련 기사가 없거나 수집에 실패했을 수 있습니다. 예시 기사로 대체하지 않습니다.';}
}
$('search').addEventListener('input',e=>{state.query=e.target.value;state.limit=7;render();});
$('sort').onchange=e=>{state.sort=e.target.value;state.limit=7;render();};
$('allNews').onclick=()=>{state.savedOnly=false;state.limit=7;render();};
$('savedNews').onclick=()=>{state.savedOnly=true;state.limit=7;render();};
$('more').onclick=()=>{state.limit+=7;render();};
$('reset').onclick=()=>{Object.assign(state,{selectedRegions:new Set(),category:'전체',query:'',sort:'newest',limit:7,period:'all',startDate:'',endDate:''});$('search').value='';$('sort').value='newest';$('startDate').value='';$('endDate').value='';render();};
document.querySelectorAll('[data-period]').forEach(button=>button.onclick=()=>{state.period=button.dataset.period;state.limit=7;render();});
for(const id of ['startDate','endDate'])$(id).addEventListener('change',event=>{state[id]=event.target.value;state.limit=7;render();});
function setRegionPanel(open){$('regionPanel').hidden=!open;$('regionToggle').setAttribute('aria-expanded',String(open));}
$('regionToggle').onclick=()=>setRegionPanel($('regionPanel').hidden);
$('regionClose').onclick=()=>{setRegionPanel(false);$('regionToggle').focus();};
$('regionPanel').addEventListener('keydown',e=>{if(e.key==='Escape'){setRegionPanel(false);$('regionToggle').focus();}});
$('closeDetail').onclick=()=>$('detail').close();
$('detail').addEventListener('click',e=>{if(e.target===$('detail')){const r=e.target.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)e.target.close();}});
render();
$('exportExcel').onclick=async()=>{
 const ids=exportRows.map(item=>item.id);
 if(exporting||!ids.length)return;
 exporting=true;render();clearExportNotice();
 try{
 const response=await fetch('/export.xlsx',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({ids})});
 if(!response.ok)throw new Error(response.status===409?'기사 목록이 갱신되었습니다. 새로고침 후 다시 다운로드해 주세요.':'엑셀 다운로드에 실패했습니다. 서버 연결을 확인해 주세요.');
 const url=URL.createObjectURL(await response.blob());const link=document.createElement('a');
 link.href=url;link.download=`대학기사_${koreanDay(new Date())}.xlsx`;document.body.append(link);link.click();link.remove();setTimeout(()=>URL.revokeObjectURL(url),60000);
 showExportNotice(`선택한 조건의 기사 ${ids.length}건을 엑셀로 다운로드했습니다. ‘기사 URL’을 클릭하면 기사를 볼 수 있습니다.`);
 }catch(error){showExportNotice(error.message);}
 finally{exporting=false;render();}
};
// 페이지는 가볍게 상태를 확인하고, 외부 RSS 요청은 서버가 30분마다 수행합니다.
setInterval(async()=>{
 try{const response=await fetch('/news.json',{cache:'no-store'});if(!response.ok)throw new Error();
 const data=await response.json();news=data.news;rssStatus=data.status;render();}
 catch{$('rssStatus').textContent='서버에 연결할 수 없습니다. Python 서버가 실행 중인지 확인해 주세요. 기존 목록은 유지됩니다.';}
},15000);
