# 0013. Split the dataset by farmer, and never move a farmer once assigned

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-21
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

Photos from one farm look alike: the same light, soil, crop variety, phone and photographer. If one farmer's
photos are in both train and test, the model is partly tested on things it has already seen, and the test
accuracy (the M4 target is ≥ 85%) is higher than it will be in a new farmer's field. Photos arrive in batches
over several weeks, so the split is redone as data grows.

## Decisions

1. **The unit of splitting is `farmer_code`** (ADR 0012). All of a farmer's fields and photos go to one split.
   A field always belongs to one farmer, which the scripts check within and across batches.
2. **Assignments are permanent.** `ml/splits/farmers.csv` (in git) records each farmer's split. A rerun only places
   new farmers; it never moves existing ones, even if that leaves the ratios uneven.
3. **New farmers are placed greedily, largest first.** Each goes to the split that keeps every class's count
   closest to its target (70 / 15 / 15 by default). There is no randomness, so the same data always gives the
   same split.
4. **Only checked batches are split.** `split.py` refuses to run if any batch fails `check_batch.py`.
5. **A class with fewer than 30 photos in val or test gets a warning.** Its score there means little, and the fix
   is more farmers, not moving photos.

## Alternatives considered

- **Random split per photo:** leaks farm look-alikes into test and overstates accuracy, the failure the
  ml/README warns about.
- **Split by field:** better than per photo, but neighbouring fields of one farmer share the phone, photographer
  and variety.
- **Re-split from scratch each time:** farmers would move between splits as data arrives, so a "test" farmer from
  last week could be in training now, and no two model versions would be scored on the same test set.
- **Random assignment of farmers (with a seed):** simple, but with few farmers per class it often leaves a class
  out of val or test entirely.

## Consequences

- Rare classes, seen at only a few farms (MLN may be one), may not reach every split. Collection should aim for
  several farmers per class, not just many photos.
- `farmers.csv` must be committed right after each split run, and the split run on one machine at a time, so two
  people don't assign the same new farmer differently.
- Label changes (expert review) don't move farmers, so the test set stays the same from one model version to the next.
