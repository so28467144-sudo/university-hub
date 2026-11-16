// 엑셀 파일 이름 입력: 기본 이름, 사용자 이름, 쓸 수 없는 문자 처리와 실제 내보내기 경로를 확인합니다.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/app.js','utf8');
new vm.Script(source);
const helpers=source.slice(source.indexOf('function defaultExcelName('),source.indexOf('// 파일 이름 칸은 기본 이름으로'));
const context=vm.createContext({});vm.runInContext(helpers,context);
const name=(value)=>context.excelFilename(value,'2026-11-16');
assert.equal(name(''),'대학기사_2026-11-16.xlsx');
assert.equal(name('   '),'대학기사_2026-11-16.xlsx');
assert.equal(name('서울 대학 소식'),'서울 대학 소식.xlsx');
assert.equal(name('보고서.xlsx'),'보고서.xlsx');
assert.equal(name('보고서.XLSX '),'보고서.xlsx');
assert.equal(name('11/16 대학:기사?'),'11_16 대학_기사_.xlsx');
assert.equal(name('a<b>"c"|d*'),'a_b__c__d_.xlsx');
assert.equal(name('///'),'대학기사_2026-11-16.xlsx');
assert.equal(name('끝에 점...'),'끝에 점.xlsx');
assert.equal(name('CON'),'CON_.xlsx');
assert.equal(name('가'.repeat(150)),'가'.repeat(100)+'.xlsx');

// 실제 내보내기 핸들러: 고친 이름은 그대로, 고치지 않은 기본값은 저장하는 날의 날짜로 씁니다.
const exportCode=source.slice(source.indexOf("$('exportExcel').onclick = async"),source.indexOf('// GitHub Pages에서 news.json'));
const dateCode=source.slice(source.indexOf('function koreanDay('),source.indexOf('function periodBounds('));
class FixedDay extends Date {constructor(...args){super(...(args.length?args:['2026-11-16T03:00:00Z']));}}
async function exportWith(input){
  let output;const button={};
  const XLSX={utils:{aoa_to_sheet(values){return {data:values};},book_new(){return {sheets:[]};},book_append_sheet(book,sheet){book.sheets.push(sheet);}},
    writeFile(book,filename){output=filename;}};
  const field={dataset:{}};const elements={exportFilename:field};
  const ctx=vm.createContext({exportRows:[{title:'t',school:'s',url:'https://example.org/a',date:'2026-11-16T00:00:00Z'}],exporting:false,
    $:id=>elements[id]||button,render(){},clearExportNotice(){},async loadXlsxLibrary(){return XLSX;},dateLabel:v=>v,showExportNotice(){},Date:FixedDay});
  vm.runInContext(dateCode,ctx);vm.runInContext(exportCode,ctx);
  // 페이지가 열리면 기본 이름이 채워집니다.
  assert.equal(field.value,'대학기사_2026-11-16');
  // 그다음 사용자가 이름을 고치거나 그대로 둔 상태로 저장합니다.
  field.value=input.value;field.dataset=input.dataset;
  await button.onclick();
  return output;
}
(async()=>{
  assert.equal(await exportWith({value:'우리 학과 정리',dataset:{edited:'true'}}),'우리 학과 정리.xlsx');
  assert.equal(await exportWith({value:'대학기사_2026-11-15',dataset:{edited:''}}),'대학기사_2026-11-16.xlsx');
  assert.equal(await exportWith({value:'',dataset:{edited:'true'}}),'대학기사_2026-11-16.xlsx');
  console.log('PASS: Excel filename default, custom names, unsafe characters, reserved names, length and export handler.');
})().catch(error=>{console.error(error);process.exit(1);});
