const test = require('node:test');
const assert = require('node:assert/strict');
const review = require('../review.js');
const record = (overrides={}) => ({deadline_code:'late', confirmed_at:null, credited_at:null, before_confirmation_minutes:null, after_confirmation_minutes:null, ...overrides});
const missing = record();
const confirmed = record({confirmed_at:'recorded'});
const before = record({confirmed_at:'recorded',credited_at:'recorded',before_confirmation_minutes:150,after_confirmation_minutes:5});
const after = record({...before,before_confirmation_minutes:5,after_confirmation_minutes:150});
const equal = record({...before,before_confirmation_minutes:70,after_confirmation_minutes:70});
const pending = record({deadline_code:'pending'});
const within = record({...before,deadline_code:'within'});

test('deadline and evidence filters intersect without treating pending cases as overdue', () => {
    const records=[missing,confirmed,before,after,equal,pending,within];
    assert.deepEqual(records.filter(r=>review.matches(r,'overdue','all')), [missing,confirmed]);
    assert.deepEqual(records.filter(r=>review.matches(r,'completed-late','complete')), [before,after,equal]);
    assert.deepEqual(records.filter(r=>review.matches(r,'overdue','missing-confirmation')), [missing]);
    assert.deepEqual(records.filter(r=>review.matches(r,'pending','missing-confirmation')), [pending]);
    assert.deepEqual(records.filter(r=>review.matches(r,'within','missing-credit')), []);
    assert.equal(records.filter(r=>review.matches(r,'all','missing-credit')).length,3);
});
test('findings reconcile every late stage and unresolved evidence group, including empty data', () => {
    assert.deepEqual(review.findings([missing,confirmed,before,after,equal,pending,within]), [
        'Overdue without recorded credit: 2 — 1 with confirmation evidence; 1 without it.',
        'Completed late: 3 — 1 with more recorded waiting before confirmation; 1 after; 1 equally split.',
        'Unresolved and not yet due: 1. These are excluded from the target-attainment denominator.'
    ]);
    assert.ok(review.findings([]).every(line=>line.includes('0')));
});
test('suggested checks distinguish missing evidence, recorded delay stages and non-overdue cases', () => {
    assert.match(review.nextCheck(missing).title, /missing confirmation/);
    assert.match(review.nextCheck(confirmed).title, /account credit/);
    assert.notEqual(review.nextCheck(missing).text, review.nextCheck(confirmed).text);
    assert.match(review.nextCheck(missing).text, /Neither confirmation nor credit/);
    assert.match(review.nextCheck(confirmed).text, /Confirmation is recorded/);
    assert.match(review.nextCheck(before).title, /initiation-to-confirmation/);
    assert.match(review.nextCheck(after).title, /confirmation-to-credit/);
    assert.match(review.nextCheck(equal).title, /both/);
    assert.match(review.nextCheck(pending).text, /not yet overdue/);
    assert.match(review.nextCheck(within).text, /met the selected target/);
});
