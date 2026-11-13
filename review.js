/* Deterministic review rules. No AI calls or inferred causes. */
const ReviewTools = {
    matches(record, deadline, evidence) {
        const deadlineMatch = deadline === 'all' || deadline === record.deadline_code ||
            (deadline === 'overdue' && record.deadline_code === 'late' && !record.credited_at) ||
            (deadline === 'completed-late' && record.deadline_code === 'late' && !!record.credited_at);
        const evidenceMatch = evidence === 'all' ||
            (evidence === 'missing-confirmation' && !record.confirmed_at) ||
            (evidence === 'missing-credit' && !record.credited_at) ||
            (evidence === 'complete' && !!record.confirmed_at && !!record.credited_at);
        return deadlineMatch && evidenceMatch;
    },
    findings(records) {
        const overdue = records.filter(r => r.deadline_code === 'late' && !r.credited_at);
        const confirmed = overdue.filter(r => r.confirmed_at).length;
        const late = records.filter(r => r.deadline_code === 'late' && r.credited_at);
        const before = late.filter(r => r.before_confirmation_minutes > r.after_confirmation_minutes).length;
        const after = late.filter(r => r.after_confirmation_minutes > r.before_confirmation_minutes).length;
        return [
            `Overdue without recorded credit: ${overdue.length} — ${confirmed} with confirmation evidence; ${overdue.length - confirmed} without it.`,
            `Completed late: ${late.length} — ${before} with more recorded waiting before confirmation; ${after} after; ${late.length - before - after} equally split.`,
            `Unresolved and not yet due: ${records.filter(r => r.deadline_code === 'pending').length}. These are excluded from the target-attainment denominator.`,
        ];
    },
    nextCheck(record) {
        if (record.deadline_code === 'pending') return {
            title: 'Recheck after the target boundary',
            text: 'This record is not yet overdue. Recalculate after the target boundary has passed, or when new source events arrive. Missing timestamps alone do not establish a processing failure.'
        };
        if (record.deadline_code === 'within') return {
            title: 'Retain the supporting records',
            text: 'The recorded credit met the selected target. No delay investigation is indicated by these timestamps alone; retain the source events so the result can be checked.'
        };
        if (!record.confirmed_at) return {
            title: 'Locate the missing confirmation evidence first',
            text: 'Neither confirmation nor credit is recorded. First search the source system using this deposit ID for a confirmation event; also reconcile any credit recorded elsewhere. Until those records are located, the waiting stage cannot be determined.'
        };
        if (!record.credited_at) return {
            title: 'Trace account credit after the recorded confirmation',
            text: 'Confirmation is recorded, but credit is not. Use the confirmation timestamp as the starting point: check subsequent account-credit events and reconcile the customer ledger. Establish whether credit occurred without appearing in this extract before concluding it is still pending.'
        };
        if (record.after_confirmation_minutes > record.before_confirmation_minutes) return {
            title: 'Review the confirmation-to-credit interval',
            text: 'Retrieve audit events between the recorded confirmation and credit. Check intermediate states, timestamp meanings and clock consistency. The larger wait occurred in this interval; its cause is not established.'
        };
        if (record.before_confirmation_minutes > record.after_confirmation_minutes) return {
            title: 'Review the initiation-to-confirmation interval',
            text: 'Retrieve source events between initiation and confirmation. Verify identifiers, timestamp meanings and clock consistency. The larger recorded wait occurred here; this alone does not establish a network or process cause.'
        };
        return {
            title: 'Review both recorded intervals',
            text: 'The recorded waiting time is equally split before and after confirmation. Retrieve audit events for both intervals and verify timestamp meanings and clock consistency before proposing a cause.'
        };
    }
};
if (typeof module !== 'undefined') module.exports = ReviewTools;
