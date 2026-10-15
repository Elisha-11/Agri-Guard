# 0004. Store coordinates as two decimals, not as a PostGIS point (for now)

- **Status:** Proposed (confirm at the Wednesday technical sync, then mark Accepted)
- **Date:** 2026-10-15
- **Deciders:** Elisha Lungu, Robert Ng'onga Chishangila

## Context

Farms and diagnoses can carry an optional location. The plan names PostGIS, and `docker-compose.yml` and CI use a
PostGIS image. But GeoDjango needs the GDAL and GEOS system libraries, which are hard to install on Windows laptops,
and the default local setup uses SQLite so a fresh clone runs without Docker. For now, the only use for location is
district-level outbreak counts. The phone rounds coordinates to 3 decimal places (~110 m) for privacy.

## Decision

Store `latitude` and `longitude` as `DecimalField(max_digits=6, decimal_places=3)` through
`apps.core.models.GeoPointMixin`. Validators keep them inside Zambia's bounding box, and a database constraint makes
sure they're either both set or both empty.

## Alternatives considered

- **GeoDjango `PointField` now:** proper spatial queries, but every developer would need GDAL/GEOS installed and
  PostgreSQL running before they could run a single test.
- **One JSON field `{lat, lng}`:** matches the contract shape exactly, but can't be validated, indexed or range-
  queried in SQL.

## Consequences

- Three decimal places in the schema mean the database can't hold more precise locations, even if a buggy client
  sent them. That's a privacy guarantee.
- Bounding-box queries (`latitude__range`) work everywhere, SQLite included.
- If we need real spatial queries later (for example "diagnoses within 20 km"), add a PostGIS `PointField`
  populated from these two columns in a migration, and record that in a new ADR that supersedes this one.
