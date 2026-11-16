// R&D 공고 메뉴: D-day, NTIS 마감일·공고규모 구간, 카테고리 필터, 정렬과 데이터 파일 형식을 확인합니다.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/rnd.js','utf8');
new vm.Script(source);
// 샌드박스에서 만든 배열은 프로토타입이 달라 Array.from으로 바꿔 비교합니다.
const context=vm.createContext({});vm.runInContext(source,context);
const today='2026-11-16';
assert.equal(context.rndKoreanDay('2026-11-15T15:30:00Z'),'2026-11-16');
assert.equal(context.rndDday('2026-11-16',today),0);
assert.equal(context.rndDday('2026-11-19T18:00:00',today),3);
assert.equal(context.rndDday('2026-11-10',today),-6);
assert.equal(context.rndDday('',today),null);
assert.deepEqual([0,3,4,7,8,21,22,30,31,-1].map(d=>context.rndDeadlineBucket(d)),
  ['마감3일전','마감3일전','마감1주전','마감1주전','마감3주전','마감3주전','마감1달전','마감1달전','마감1달이상','']);
assert.deepEqual([50000000,100000000,299999999,300000000,500000000,null].map(w=>context.rndScaleBucket(w)),
  ['1억미만','1억이상 ~ 3억미만','1억이상 ~ 3억미만','3억이상 ~ 5억미만','5억이상','']);
assert.deepEqual([0,5,-2,null].map(d=>context.rndDdayLabel(d)),['D-Day','D-5','마감','']);

const items=[
  {id:'a',title:'2027년 AI 반도체 핵심기술 개발사업 신규과제 공고',ministry:'과학기술정보통신부',status:'접수중',type:'본공고',form:'개별공고',budget_won:400000000,posted_date:'2026-11-10',close_date:'2026-11-18'},
  {id:'b',title:'스마트팜 실증 연구 수요조사',ministry:'농림축산식품부',status:'접수예정',type:'수요조사',form:'개별공고',budget_won:80000000,posted_date:'2026-11-14',close_date:'2026-12-30'},
  {id:'c',title:'2026년 하반기 통합공고',ministry:'다부처',status:'마감',type:'본공고',form:'통합공고',posted_date:'2026-10-01',close_date:'2026-11-01'},
  {id:'d',title:'해양 탄소중립 기술개발',ministry:'해양수산부',status:'접수중',type:'사전공고',form:'개별공고',budget_won:150000000,posted_date:'2026-11-12',close_date:'2026-11-30'}];
const none={query:'',status:new Set(),ministry:new Set(),type:new Set(),form:new Set(),scale:new Set(),deadline:new Set()};
const ids=f=>Array.from(context.rndFilter(items,{...none,...f},today),x=>x.id);
assert.deepEqual(ids({}),['a','b','c','d']);
assert.deepEqual(ids({status:new Set(['접수중'])}),['a','d']);
assert.deepEqual(ids({ministry:new Set(['과학기술정보통신부','해양수산부'])}),['a','d']);
assert.deepEqual(ids({status:new Set(['접수중']),type:new Set(['본공고'])}),['a']);
assert.deepEqual(ids({form:new Set(['통합공고'])}),['c']);
assert.deepEqual(ids({scale:new Set(['1억미만'])}),['b']);
assert.deepEqual(ids({deadline:new Set(['마감3일전'])}),['a']);
assert.deepEqual(ids({deadline:new Set(['마감1달이상'])}),['b']);
assert.deepEqual(ids({query:'반도체'}),['a']);
assert.deepEqual(ids({query:'해양 수산'}),['d']);
assert.deepEqual(Array.from(context.rndSort(items,'deadline',today),x=>x.id),['a','d','b','c']);
assert.deepEqual(Array.from(context.rndSort(items,'latest',today),x=>x.id),['b','d','a','c']);

// 데이터 파일: NTIS와 같은 카테고리 목록과 출처를 갖추고, 공고는 목록 형식이어야 합니다.
const data=JSON.parse(fs.readFileSync(__dirname+'/rnd-announcements.json','utf8'));
assert.ok(Array.isArray(data.items));
assert.equal(data.source.url,'https://www.ntis.go.kr/rndgate/eg/un/ra/mng.do');
for(const key of ['form','status','ministry','type','scale','deadline'])assert.ok(Array.isArray(data.categories[key])&&data.categories[key].length,key);
assert.ok(data.categories.ministry.includes('과학기술정보통신부')&&data.categories.ministry.includes('다부처'));
assert.deepEqual(data.categories.deadline,['마감3일전','마감1주전','마감3주전','마감1달전','마감1달이상']);
console.log('PASS: R&D announcements D-day, NTIS deadline and budget buckets, category filters, sorting and data file.');
