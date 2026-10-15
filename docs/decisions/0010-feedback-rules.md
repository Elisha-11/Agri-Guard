# 0010. Feedback: owner or officer, self-reported role, append-only

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-15
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

Feedback becomes training labels, so who gave it matters: an extension officer's correction is worth more than a
farmer's guess. In practice, an officer visiting a farm will often look at the result on the **farmer's** phone,
not log in on their own. The contract allows `given_by_role` in the request but doesn't say who may send what.

## Decisions

1. **Farmers can give feedback on their own diagnoses; extension-officer accounts on any diagnosis.** Anything else
   reads as "no synced diagnosis", so the API never reveals another farmer's records.
2. **`given_by_role` is stored as reported, and `given_by` always records the sending account.** That supports
   "officer on the farmer's phone" without a second login. Analysis can weight
   `given_by.role = extension_officer` (verified) above a self-reported officer role.
3. **Append-only, idempotent on `client_id`, duplicate before validation.** These are the same rules as diagnosis
   sync, so the phone's queue always drains.
4. **409 `conflict`** when another account used the `client_id`, as for farms. This is an additive contract
   change (0.3.0), with the 201/200 response body `{id, client_id}`.

## Alternatives considered

- **Only accept the account's own role:** the common "officer on the farmer's phone" case would be recorded as
  farmer feedback, losing the most valuable labels.
- **One feedback per diagnosis, latest wins:** loses the farmer's view when an officer later disagrees, and
  disagreement is itself useful data.

## Consequences

- Self-reported officer feedback can be wrong or abused. Treat it as a signal, not ground truth, until officer
  accounts are in use.
- An export of corrections for retraining is a follow-up.
