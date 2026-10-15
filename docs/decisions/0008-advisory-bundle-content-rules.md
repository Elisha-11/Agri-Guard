# 0008. Advisory bundle: English fallback per disease, content-hash versions, editable app messages

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-15
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

The contract defines the bundle's shape but not what to do when a translation is missing, how the version is
chosen, or where the `ui` messages come from. Translations into Nyanja, Bemba and Tonga will arrive slowly, one
disease at a time, and each needs an agronomist's review.

## Decisions

1. **Fall back to English per disease, and say so.** If a disease's advice isn't published in the requested
   language, the English version is included. Each entry gets a `lang` field saying which language it's in.
   This is an additive contract change (contract 0.3.0).
2. **Leave out diseases with no published advice at all.** The PWA shows a fixed `no_advice` message instead.
   Unreviewed advice is never shown, even as a fallback.
3. **Version = latest change date + content hash.** `bundle_version` and the ETag change exactly when the content
   does, including deletions and unpublishing, which a timestamp alone would miss. The date part keeps it
   readable.
4. **`ui` messages are database content (`UiMessage`), not code.** They're safety messages ("show this plant to an
   extension officer"), so the people who review advice should be able to edit and translate them without a
   deploy. English defaults are seeded by a data migration.
5. **The endpoint is public, with `Cache-Control: no-cache` and ETags.** The app needs the advice before sign-in
   and offline. Revalidating with an ETag costs a few hundred bytes.

## Alternatives considered

- **No fallback (omit untranslated diseases):** a Bemba speaker would get "no advice" for a disease we have
  reviewed English advice for.
- **Fall back silently, without `lang`:** the app couldn't choose the right narration voice or tell the farmer the
  text is in English.
- **A hand-bumped version number:** easy to forget, and stale bundles would stay on phones.
- **`ui` strings in the PWA's translation files:** fine for buttons, but these messages carry safety meaning and
  belong with the reviewed content.

## Consequences

- The bundle is built on every request (4 small queries). That's fine at this size. If it becomes hot, cache it
  per language and invalidate on save.
- The contract gets an optional `lang` on `DiseaseAdvice`.
