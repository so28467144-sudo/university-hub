// 엑셀 저장 창: 버튼을 누르면 파일 이름 창이 열리고, 기본 이름·입력한 이름·취소가 그대로 반영되는지 확인합니다.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/app.js','utf8');
new vm.Script(source);
const helpers=source.slice(source.indexOf('function defaultExcelName('),source.indexOf('// GitHub Pages에서 news.json'));
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

// 실제 버튼·창 핸들러를 실행합니다.
const exportCode=source.slice(source.indexOf("$('exportExcel').onclick = () =>"),source.indexOf('// GitHub Pages에서 news.json'));
const dateCode=source.slice(source.indexOf('function koreanDay('),source.indexOf('function periodBounds('));
class FixedDay extends Date {constructor(...args){super(...(args.length?args:['2026-11-16T03:00:00Z']));}}
function page(){
  const saved=[];
  const XLSX={utils:{aoa_to_sheet(values){return {data:values};},book_new(){return {sheets:[]};},book_append_sheet(book,sheet){book.sheets.push(sheet);}},
    writeFile(book,filename){saved.push(filename);}};
  const field={value:'',selected:false,focus(){},select(){this.selected=true;}};
  const dialog={open:false,showModal(){this.open=true;},close(){this.open=false;}};
  const elements={exportExcel:{},exportFilename:field,exportDialogSummary:{},exportCancel:{},exportForm:{},exportDialog:dialog};
  const ctx=vm.createContext({exportRows:[{title:'t',school:'s',url:'https://example.org/a',date:'2026-11-16T00:00:00Z'}],exporting:false,
    $:id=>elements[id],render(){},clearExportNotice(){},async loadXlsxLibrary(){return XLSX;},dateLabel:v=>v,showExportNotice(){},Date:FixedDay});
  vm.runInContext(dateCode,ctx);vm.runInContext(exportCode,ctx);
  return {elements,field,dialog,saved};
}
(async()=>{
  // 버튼을 누르면 창이 열리고 기본 이름이 선택된 상태로 채워집니다.
  let p=page();
  p.elements.exportExcel.onclick();
  assert.equal(p.dialog.open,true);assert.equal(p.field.value,'대학기사_2026-11-16');assert.equal(p.field.selected,true);
  assert.match(p.elements.exportDialogSummary.textContent,/1건/);
  await p.elements.exportForm.onsubmit({preventDefault(){}});
  assert.deepEqual(p.saved,['대학기사_2026-11-16.xlsx']);assert.equal(p.dialog.open,false);
  // 이름을 고쳐 저장합니다.
  p=page();p.elements.exportExcel.onclick();p.field.value='우리 학과 정리';
  await p.elements.exportForm.onsubmit({preventDefault(){}});
  assert.deepEqual(p.saved,['우리 학과 정리.xlsx']);
  // 이름을 지우고 저장하면 기본 이름입니다.
  p=page();p.elements.exportExcel.onclick();p.field.value='';
  await p.elements.exportForm.onsubmit({preventDefault(){}});
  assert.deepEqual(p.saved,['대학기사_2026-11-16.xlsx']);
  // 취소와 바깥 클릭은 저장하지 않고 창만 닫습니다.
  p=page();p.elements.exportExcel.onclick();p.elements.exportCancel.onclick();
  assert.equal(p.dialog.open,false);assert.deepEqual(p.saved,[]);
  p=page();p.elements.exportExcel.onclick();p.elements.exportDialog.onclick({target:p.dialog});
  assert.equal(p.dialog.open,false);assert.deepEqual(p.saved,[]);
  // 다시 열면 이전에 입력한 이름 대신 기본 이름이 채워집니다.
  p=page();p.elements.exportExcel.onclick();p.field.value='임시';p.elements.exportCancel.onclick();p.elements.exportExcel.onclick();
  assert.equal(p.field.value,'대학기사_2026-11-16');
  console.log('PASS: Excel save dialog opens with the default name, saves custom or default names, cancels without saving.');
})().catch(error=>{console.error(error);process.exit(1);});
