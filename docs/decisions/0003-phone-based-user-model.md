# 0003. Make Farmer the user model, keyed on phone number

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-15
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

Many farmers have no email address. The contract signs them in with a phone number and an SMS code
(`/auth/otp/*`). Django's built-in user has a `username` and an `email`, and Django only lets you replace the user
model **before the first migration**: changing it later means rebuilding the database.

## Decision

- `accounts.Farmer` is `AUTH_USER_MODEL` from the first migration onward.
- `phone` (E.164, validated against the contract pattern) is the unique login field. There is no username or email.
- The primary key is a UUID, matching the contract's `Farmer.id`, so ids can't be guessed or counted.
- Farmers get an unusable password. Staff get a password for the Django admin.
- Extension officers are Farmers with `role = extension_officer`, not a separate model.

## Alternatives considered

- **Built-in User plus a Profile table:** keeps Django's `username`, which we'd fill with the phone number anyway.
  Every request would need a join, and it's two places to keep in sync.
- **Decide later:** not possible without rebuilding the database once real data exists.

## Consequences

- `createsuperuser` asks for a phone number instead of a username.
- A farmer who changes their number needs a support flow to change `phone` (no self-service yet).
- The OTP feature only has to create a code table. The user model is ready for it.
