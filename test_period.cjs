// Run with Node.js: node university-hub/test_period.cjs
const fs = require('node:fs');
const vm = require('node:vm');
const assert = require('node:assert/strict');
const source = fs.readFileSync(__dirname + '/app.js', 'utf8');
new vm.Script(source); // Also verify syntax of the complete application.
const helpers = source.slice(source.indexOf('function koreanDay('), source.indexOf('let exportRows='));
const fixedNow = Date.parse('2026-10-27T07:00:00Z');
class FixedDate extends Date {
  constructor(...args) { super(...(args.length ? args : [fixedNow])); }
}
const state = { period: 'today', startDate: '', endDate: '' };
const context = vm.createContext({state, Date: FixedDate});
vm.runInContext(helpers, context);
const bounds = () => context.periodBounds();
const accepts = date => context.withinPeriod({date}, bounds());
assert.equal(bounds().start, '2026-10-27');
assert.equal(accepts('2026-10-26T14:59:59Z'), false);
assert.equal(accepts('2026-10-26T15:00:00Z'), true);
assert.equal(accepts('2026-10-27T14:59:59Z'), true);
assert.equal(accepts('2026-10-27T15:00:00Z'), false);
state.period = '7days';
assert.equal(bounds().start, '2026-10-21');
assert.equal(accepts('2026-10-20T15:00:00Z'), true);
assert.equal(accepts('2026-10-20T14:59:59Z'), false);
state.period = '30days';
assert.equal(bounds().start, '2026-09-28');
state.period = 'custom';
assert.ok(bounds().error);
assert.equal(accepts('2026-10-27T07:00:00Z'), false);
state.startDate = '2026-10-25'; state.endDate = '2026-10-26';
assert.equal(accepts('2026-10-24T15:00:00Z'), true);
assert.equal(accepts('2026-10-26T14:59:59Z'), true);
assert.equal(accepts('2026-10-26T15:00:00Z'), false);
state.startDate = '2026-10-27';
assert.ok(bounds().error);
assert.equal(accepts('2026-10-27T07:00:00Z'), false);
state.period = 'all';
assert.equal(accepts(''), true);
state.period = 'today';
assert.equal(accepts(''), false);
assert.equal(accepts('invalid date'), false);
console.log('PASS: Period filters, Korean midnight boundaries, inclusive dates, invalid ranges, missing dates and app syntax.');
