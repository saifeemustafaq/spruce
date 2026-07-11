# Irvine Company — North Park (Affordable / BMR) API Reference

Notes on how to pull live BMR/affordable unit availability for the Irvine
Company's **North Park** community in San Jose. This is a *different backend*
from the Prometheus API used for Spruce/Kensington (see `scraper/fetcher.py`),
so it needs its own fetcher + parser.

- Community page: <https://www.irvinecompanyapartments.com/locations/northern-california/san-jose/north-park/affordable-housing.html>
- Backend: **Algolia** hosted search (not a plain REST API)
- How it was discovered: the page's inline config (`page-properties-provider`
  Vue component) exposes the Algolia app ID, public search key, and index names.

## Endpoint

```
POST https://JV59LDJGMN-dsn.algolia.net/1/indexes/*/queries
```

There is also a cache proxy the site itself uses:
`https://search.irvinecompanyapartments.com` (same Algolia contract). Hitting
Algolia directly works fine and is what we use below.

### Credentials (public search key — safe for client-side use)

| Item | Value |
|---|---|
| Algolia Application ID | `JV59LDJGMN` |
| Algolia API Key (search-only) | `daadf4691bf18ebb7d7065bd85f0c972` |

### Headers

```
X-Algolia-Application-Id: JV59LDJGMN
X-Algolia-API-Key: daadf4691bf18ebb7d7065bd85f0c972
Content-Type: application/json
```

## Algolia indices (from the page config)

| Purpose | Index name |
|---|---|
| BMR / affordable unit availability | `prod_ica_bmrUnitAvailability` |
| All unit availability | `prod_ica_unitAvailability` |
| Units sorted earliest available | `prod_ica_unitAvailability_unitEarliestAvailable_asc` |
| Units sorted by price asc | `prod_ica_unitAvailability_unitStartingPrice_asc` |
| Floor plans | `prod_ica_floorplan` |
| Community | `prod_ica_community` |
| Property | `prod_ica_property` |
| Market / City / Collection | `prod_ica_market` / `prod_ica_city` / `prod_ica_collection` |

For BMR tracking we only need **`prod_ica_bmrUnitAvailability`** — every hit in
that index is inherently a BMR unit, so no separate "is this a deal?" filtering
is required.

## North Park identifiers

| Item | Value | Source |
|---|---|---|
| AEM Community ID (`communityIDAEM`) | `d44b004c-6b62-4d26-9381-15bcd314d16e` | `contact_aemCommunityId` hidden input |
| Property ID | `1078197` | `contact_propertyId` hidden input |

North Park is a *collection* of named sub-communities, each surfaced as its own
`propertyName` in the results:

- The Cypress Apartment Homes (siteId 1078197)
- The Laurels Apartment Homes (siteId 1078198)
- The Oaks Apartment Homes (siteId 1078199)
- The Sycamores Apartment Homes (siteId 1078200)
- The Redwoods Apartment Homes
- The Pines Apartment Homes

> **Important:** the correct filter attribute is **`communityIDAEM`**, *not*
> `communityId`. Filtering on the wrong name returns `nbHits: 0` with no error.

## Working request

```bash
curl -s "https://JV59LDJGMN-dsn.algolia.net/1/indexes/*/queries" \
  -H "X-Algolia-Application-Id: JV59LDJGMN" \
  -H "X-Algolia-API-Key: daadf4691bf18ebb7d7065bd85f0c972" \
  -H "Content-Type: application/json" \
  -d '{"requests":[{"indexName":"prod_ica_bmrUnitAvailability","params":"filters=communityIDAEM:d44b004c-6b62-4d26-9381-15bcd314d16e&hitsPerPage=100"}]}'
```

Response is standard Algolia: `{"results":[{"hits":[...],"nbHits":N,...}]}`.

## Response schema (fields we care about, per hit)

| Field | Example | Meaning |
|---|---|---|
| `objectID` | `5578484_19_461` | Stable unique key (use for change tracking) |
| `propertyName` | `The Oaks Apartment Homes` | Sub-community / building |
| `unitMarketingName` | `1150` | Unit number |
| `unitTypeName` | `Studio` | Unit type label |
| `floorplanBed` / `floorplanBath` | `0` / `1` | Beds / baths |
| `unitSqFt` | `533` | Square footage |
| `unitStartingPrice.price` / `.term` | `1530` / `12` | Rent + lease term (months) |
| `unitEarliestAvailable.date` | `20260711` | Available date (`YYYYMMDD`) |
| `unitEarliestAvailable.dateTimeStamp` | `1783728000` | Unix timestamp of availability |
| `bmrType` | `VeryLow` / `Moderate` | Affordability tier |
| `unitLeasePrice[]` | array | Per-day price/term options |
| `unitProfileOccupancyStatus` | `Vacant - Ready` | Occupancy status |
| `floorplanUniqueID` | `5578484_19` | Floor plan key |
| `unitAmenities[]` / `unitSyndicatedAmenities[]` | array | Amenities |
| `_geoloc` | `{lat,lng}` | Coordinates |

## Field mapping to the tracker's expected format

The tracker (`scraper/parser.py` → `parse_listings`) expects a dict keyed by a
unit ID with `plan`, `sqft`, `floor`, `available`, `price`, `bedrooms`,
`bathrooms`. Suggested mapping for North Park:

| Tracker field | Source |
|---|---|
| key | `objectID` (or `propertyName` + `unitMarketingName`) |
| `plan` | `unitTypeName` (+ `bmrType`, e.g. `Studio BMR (VeryLow)`) |
| `sqft` | `f"{unitSqFt} sq. ft."` |
| `floor` | `f"Floor {unitFloor}"` |
| `available` | reformat `unitEarliestAvailable.date` (`YYYYMMDD` → `Mon DD, YYYY`) |
| `price` | `f"${unitStartingPrice.price}/{unitStartingPrice.term}mo"` |
| `bedrooms` | `floorplanBed` |
| `bathrooms` | `floorplanBath` |

## Notes / gotchas

- The whole `prod_ica_bmrUnitAvailability` index (all Irvine communities) had
  **153** BMR units at time of discovery; North Park had **11**.
- `unitEarliestAvailable.date` is a plain `YYYYMMDD` string — needs its own
  date parser (the Prometheus parser handles `m/d/Y` and `Y-m-d`).
- The search API key is a *public search-only* key embedded in the page HTML;
  it is safe to commit but may rotate. If requests start returning 403/invalid
  key, re-scrape it from the community page's `page-properties-provider` config
  (`searchAPIKey` / `searchAccountId`).
- To add other Irvine communities later, grab their `communityIDAEM` from the
  respective community page and reuse everything else.
