// 실제 app.js 내보내기 핸들러를 실행합니다. SheetJS 직렬화만 테스트 대역입니다.
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/app.js','utf8');
const news=JSON.parse(fs.readFileSync(__dirname+'/news.json','utf8')).news;
const exportCode=source.slice(source.indexOf("$('exportExcel').onclick = async"),source.indexOf('// GitHub Pages에서 news.json'));
const dateCode=source.slice(source.indexOf('function koreanDay('),source.indexOf('function periodBounds('));
class KoreanMidnight extends Date {constructor(...args){super(...(args.length?args:['2026-10-28T15:30:00Z']));}}
async function verify(rows){
  let output;const button={};
  const XLSX={utils:{aoa_to_sheet(values){const sheet={data:values};values.forEach((row,i)=>row.forEach((v,j)=>sheet[String.fromCharCode(65+j)+(i+1)]={v}));return sheet;},
    book_new(){return {sheets:[]};},book_append_sheet(book,sheet,name){book.sheets.push({sheet,name});}},writeFile(book,filename){output={book,filename};}};
  const context=vm.createContext({exportRows:rows,exporting:false,$:()=>button,render(){},clearExportNotice(){},
    async loadXlsxLibrary(){return XLSX;},dateLabel:value=>value,showExportNotice(){},Date:KoreanMidnight});
  vm.runInContext(dateCode,context);vm.runInContext(exportCode,context);await button.onclick();
  assert.ok(output);assert.equal(output.filename,'대학기사_2026-10-29.xlsx');
  const sheet=output.book.sheets[0].sheet;assert.equal(sheet.data.length,rows.length+1);
  rows.forEach((item,i)=>{assert.equal(sheet.data[i+1][1],item.title);assert.equal(sheet.data[i+1][2],item.school);
    assert.equal(sheet['J'+(i+2)].l.Target,item.original_url||item.url);});
  assert.equal(sheet['!autofilter'].ref,`A1:J${rows.length+1}`);
}
(async()=>{
  assert.equal(news.length,5000);
  await verify(news);
  const selected=news.filter(n=>n.regions.includes('충북')).slice(0,40);assert.ok(selected.length);await verify(selected);
  await verify(news.slice(0,5).reverse());
  const article=news[0],id=(article.duplicate_ids||[article.id])[0];
  const context=vm.createContext({saved:new Set([id]),article});
  vm.runInContext(source.slice(source.indexOf('const isArticleSaved='),source.indexOf('function normalizeSearch(')),context);
  assert.equal(vm.runInContext('isArticleSaved(article)',context),true);
  console.log('PASS: Pages export 5000 rows, selection, ordering, original hyperlinks, KST filename and saved IDs.');
})().catch(error=>{console.error(error);process.exitCode=1;});
