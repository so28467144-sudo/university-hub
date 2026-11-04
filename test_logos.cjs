const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(__dirname+'/app.js','utf8');
new vm.Script(source);
const escape=source.slice(source.indexOf('const escapeHtml='),source.indexOf('const dateLabel='));
const helpers=source.slice(source.indexOf('const DEFAULT_UNIVERSITY_MARK='),source.indexOf('function normalizeSearch('));
const context=vm.createContext({});vm.runInContext(escape+helpers+';this.findUniversityLogo=findUniversityLogo;this.universityMarkHtml=universityMarkHtml;',context);
// 등록 파일 자체도 문법 오류 없이 읽히고, 공식 출처·사용 조건이 없는 항목이 없어야 합니다.
const registryContext=vm.createContext({window:{}});vm.runInContext(fs.readFileSync(__dirname+'/university-logos.js','utf8'),registryContext);
const registry=registryContext.window.UNIVERSITY_LOGOS;
assert.ok(Array.isArray(registry.entries)&&Array.isArray(registry.reviewed));
for(const entry of registry.entries){
 for(const key of ['school','file','source_url','terms_url','terms','verified_at'])assert.ok(entry[key],`${entry.school} ${key}`);
 assert.ok(fs.existsSync(__dirname+'/'+entry.file),entry.file);
}
const sample={entries:[
 {school:'가나대학교',file:'logos/ganada.svg'},
 {school:'가나대학교',campus:'세종캠퍼스',file:'logos/ganada-sejong.svg'},
 {school:'다라대학교',aliases:['다라대학교 글로컬'],file:'logos/dara.png'},
 {school:'위험대학교',file:'https://example.com/logo.png'},
 {school:'상위대학교',file:'logos/../secret.svg'}]};
const find=article=>context.findUniversityLogo(article,sample)?.file||null;
assert.equal(find({school_names:['가나대학교']}),'logos/ganada.svg');
assert.equal(find({school_names:['가나대학교'],universities:[{name:'가나대학교',campus_status:'matched',campus_names:['세종캠퍼스']}]}),'logos/ganada-sejong.svg');
// 캠퍼스가 확인되지 않으면 캠퍼스 전용 로고를 쓰지 않습니다.
assert.equal(find({school_names:['가나대학교'],universities:[{name:'가나대학교',campus_status:'unverified',campus_names:['세종캠퍼스']}]}),'logos/ganada.svg');
assert.equal(find({school_names:['다라대학교 글로컬']}),'logos/dara.png');
for(const article of [{school_names:['대학명 미확인']},{school_names:['가나대학교','다라대학교']},{school_names:[]},{},{school_names:['없는대학교']},
                      {school_names:['위험대학교']},{school_names:['상위대학교']}])assert.equal(find(article),null,JSON.stringify(article));
assert.equal(context.findUniversityLogo({school_names:['가나대학교']},undefined),null);
assert.match(context.universityMarkHtml({school_names:['가나대학교']},sample),/<img src="logos\/ganada.svg" alt=""/);
assert.match(context.universityMarkHtml({school_names:['대학명 미확인']},sample),/mark-default/);
assert.doesNotMatch(context.universityMarkHtml({school_names:['대학명 미확인'],mark:'N'},sample),/>N</);
console.log('PASS: Logo mapping by school, alias and verified campus; neutral icon for unknown, multiple, unlisted and unsafe entries.');
