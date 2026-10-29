-- The public changelog of accepted corrections (CORRECTIONS.md): which record changed, how, why,
-- and when. It never repeats removed content, so amended values are left out; the corrected
-- record shows them.
SELECT
    id AS correction_id,
    target_id,
    action,
    amend_field,
    reason,
    decided_at,
    request_ref,
    public_note
FROM silver.corrections
ORDER BY decided_at DESC, correction_id
