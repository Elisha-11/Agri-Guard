# 0006. Sign in with SMS codes; 60-minute access tokens, 90-day rotating refresh tokens

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-15
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

The contract signs farmers in with a phone number and an SMS code. Farmers use cheap Android phones, often share
them, and may be offline for weeks during the season. SMS costs money per message, and a sign-in endpoint is a
target for guessing codes and for "SMS pumping" (making us send messages to premium numbers).

## Decision

**Codes**
- 6 random digits, valid 10 minutes, stored only as an HMAC-SHA256 hash keyed by `SECRET_KEY`.
- At most 3 codes per phone per 15 minutes, and 5 wrong guesses per code. A new code cancels the old one.
- Every failure to verify returns the same `invalid_code` error, and requesting a code always returns 202, so the
  API never reveals whether a number has an account.
- Limits are counted in the database (the `OtpCode` table), not in a cache, so they hold across server processes
  without needing Redis.

**SMS**
- A swappable backend (`SMS_BACKEND`), like Django's email backends: console for development, in-memory for tests,
  Africa's Talking for staging and production. Production refuses to start with a backend that would log codes.

**Tokens** (djangorestframework-simplejwt)
- Access tokens last 60 minutes. Refresh tokens last 90 days and **rotate**: each refresh returns a new one and
  blacklists the old one.

## Alternatives considered

- **Short refresh tokens (for example 7 days):** a farmer offline for two weeks would have to sign in again, which
  costs an SMS and needs signal at that moment.
- **Non-rotating long refresh tokens:** a token copied from a shared phone would work for 90 days with no way to
  notice. With rotation, the next legitimate refresh makes the copy useless.
- **Rate limiting in Redis or Django's cache:** faster, but the default local cache is per-process, and requiring
  Redis would break the "runs on a fresh clone without Docker" goal. Sign-in traffic is low enough for the database.
- **WhatsApp or USSD codes:** worth revisiting. SMS is the one channel every phone has.
- **Storing codes in plain text:** anyone with database or admin access could sign in as any farmer.

## Consequences

- Rotating `SECRET_KEY` signs everyone out and cancels outstanding codes. That's acceptable, and it's useful after
  a leak.
- Each verify and refresh writes to the database (attempt counts, token blacklist). That's fine at MVP scale.
  `purge_otp_codes`, and simplejwt's `flushexpiredtokens`, keep the tables small.
- The PWA must store the new refresh token after every refresh, and avoid refreshing from two places at once.
