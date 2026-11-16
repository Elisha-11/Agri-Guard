# Crop priorities: which crops to add after the first five

Evidence for [ADR 0018](decisions/0018-finish-five-crops-then-add-beans.md). Researched 27 Oct 2026. Every figure has a
source; "not found" means we looked and found none, never zero.

## Main source and its limits

[2024 Integrated Agricultural Survey (IAS 2024)](https://www.zamstats.gov.zm/wp-content/uploads/2026/08/2024-Integrated-Agriculture-Survey-IAS.pdf),
ZamStats with the Ministry of Agriculture, 2023/24 season. Page numbers below are the report's printed numbers.

- 2023/24 was a **severe drought year**: area harvested, production and yields are far below normal. The household
  counts (who planted the crop) are the most useful column for us.
- IAS 2024 does **not** cover cassava, Irish potato, bambara nut, sugarcane, coffee or any vegetable.
- Provincial rows are suppressed when fewer than 30 sampled households grow a crop, so a missing province is not a
  zero.
- "Smallholder" means the survey's small and medium scale households; the share is our calculation (their tonnes
  divided by all-sector tonnes).
- Yield is on area **planted**.

## Crops in the survey (2023/24)

| Crop | Smallholder households | Area planted (ha) | Production (t) | Yield (t/ha) | Smallholder share | Main provinces | IAS table |
|------|-----------------------:|------------------:|---------------:|-------------:|------------------:|----------------|-----------|
| Maize | 1,868,507 | 2,232,580 | 1,460,148 | 0.7 | 87% | Northern, Eastern, Muchinga, Luapula | 3.1, p.17 |
| Groundnut | 323,590 | 165,149 | 48,592 | 0.3 | 98% | Northern, Eastern, Luapula | 3.11, p.24 |
| Soybean | 260,342 | 311,124 | 130,912 | 0.4 | 42% | Eastern, Central | 3.8, p.22 |
| Sunflower | 216,604 | 204,792 | 19,853 | 0.1 | 96% | Eastern, Central, Southern | 3.7, p.21 |
| Mixed beans | 117,737 | 62,219 | 18,568 | 0.3 | 96% | Northern, North-Western, Muchinga, Luapula | 3.5, p.20 |
| Sweet potato | 82,139 | 28,746 | 43,101 | 1.5 | 99% | Central, Northern, Luapula | 3.9, p.23 |
| Millet | 59,212 | 38,039 | 11,852 | 0.3 | 100% | national only | 3.4, p.19 |
| Rice | 58,240 | 62,962 | 24,609 | 0.4 | 97% | Northern, Luapula, Eastern, Western | 3.3, p.19 |
| Sorghum | 34,295 | 28,525 | 2,054 | 0.1 | 70% | national only | 3.2, p.18 |
| Cowpea | 22,810 | 13,482 | 752 | 0.1 | 84% | national only | 3.6, p.21 |
| Seed cotton | 18,392 | 18,641 | 4,217 | 0.2 | 99% | national only | 3.10, p.23 |
| Virginia tobacco | 16,352 | 21,524 | 16,465 | 0.8 | 60% | Eastern, Western, Central | 3.12, p.25 |
| Wheat | 0 (101 large farms) | 22,504 | 120,183 | 5.3 | 0% | Central, Copperbelt | 3.13, p.26 |

Maize disagreement: the Crop Forecast Survey gives 1,511,143 t for 2023/24 and forecasts 3,655,646 t for 2024/25,
93% from small and medium farms ([ZamStats release](https://www.zamstats.gov.zm/zambia-projected-to-record-a-maize-surplus-of-over-500000-metric-tonnes/)).

## Crops not in the survey

| Crop | Best figure found | Confidence |
|------|-------------------|------------|
| Cassava | 3,167,650 t in 2024/25 (CFS, quoted in the IPC Zambia report; form not stated). No household count | Unverified: primary report not reached |
| Irish potato | 163,197 t in 2024/25 (same IPC report; may include sweet potato) | Unverified |
| Tomato, cabbage, rape, onion | No current count. About 650,000 small-scale horticulture households in 2000; cabbage, tomato and rape were about 85% of smallholder vegetable sales in 1997/98 ([review](https://www.researchgate.net/publication/367844642_Review_of_Options_for_Horticultural_Research_and_Development_A_Case_of_Zambia), [J. Sust. Dev. 2021](https://ccsenet.org/journal/index.php/jsd/article/download/0/0/46154/49188)) | Low, old |
| Bambara nut, garlic, okra, sugarcane, coffee | Not found | — |

FAOSTAT was not checked; it is the fallback for these crops.

## Disease pressure in Zambia

| Crop | Main threats | Zambian evidence |
|------|--------------|------------------|
| Mixed beans | Angular leaf spot; rust, anthracnose, bean common mosaic virus, bean stem maggot | Angular leaf spot in all 41 fields surveyed in 9 districts; 60–100% loss cited ([UNZA 2023](https://dspace.unza.zm/bitstreams/85745dfd-ebba-441b-ac09-0ffa88aa4fde/download)) |
| Tomato | Tuta absoluta (leaf miner) | Present since 2016, widespread; 80–100% loss possible ([IPPC Zambia report](https://www.ippc.int/en/countries/zambia/pestreports/2017/02/tuta-absoluta-report/)) |
| Sweet potato | Sweet potato virus disease; weevils | Viruses confirmed in Lusaka and North-Western, 1998 ([APS](https://apsnet.org/publications/plantdisease/1998/September/Pages/82_9_1063.3.aspx)); loss figures only from Uganda and South Africa |
| Sunflower | Alternaria leaf blight | Recorded in Zambia per a general reference only; low confidence |
| Wheat | Wheat blast | First found in Mpika 2017/18 ([PMC7505438](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7505438/)) |
| Cabbage, rape | Diamondback moth, aphids, black rot | No Zambian source; Zimbabwe and general sources |
| Irish potato, rice, millet, sorghum, cowpea | Late blight; blast; anthracnose | No Zambian loss source found |

## Ranking

Each factor is scored 1–5 and weighted: households × 3, losses × 2, symptoms visible on leaves × 2, spread × 1
(maximum 40).

- **Households:** 5 = 200,000+; 4 = 100,000–199,999; 3 = 50,000–99,999; 2 = 20,000–49,999; 1 = fewer or unknown.
- **Losses:** 5 = a Zambian source cites 60%+; 3 = loss figures only from other countries; 2 = no figure found.
- **Leaves:** 5 = the main threats show clearly on leaves; 3 = some are hidden (e.g. in roots).
- **Spread:** provinces with published figures: 6–8 = 4; 4–5 = 3; 2–3 = 2; national only = 1.

`*` = assumed, because no household count exists.

| Rank | Crop | Households | Losses | Leaves | Spread | Total |
|-----:|------|-----------:|-------:|-------:|-------:|------:|
| 1 | Common beans | 4 | 5 | 5 | 4 | **36** |
| 2 | Sunflower | 5 | 2 | 4 | 2 | **29** |
| 3 | Tomato | 2\* | 5 | 5 | 3\* | **29** |
| 4 | Rice | 3 | 3 | 4 | 3 | **26** |
| 5 | Sweet potato | 3 | 3 | 3 | 4 | **25** |
| 6 | Cabbage and rape | 2\* | 2 | 5 | 3\* | **23** |
| 7 | Millet | 3 | 2 | 4 | 1 | **22** |
| 8 | Sorghum | 2 | 2 | 4 | 1 | **19** |

Sorghum ties with Irish potato and cowpea at 19 and wins on household count. Wheat (no smallholders), tobacco and
crops without data are not ranked.

## Data sources checked

| Source | Result |
|--------|--------|
| [ZamStats NADA](https://nada.zamstats.gov.zm/index.php/catalog/22/study-description) | 2024/25 Crop Forecast Survey microdata. Free after a confidentiality declaration; no redistribution. Best source for the next update |
| Zambia Pest Risk Register (PQPS with CABI) | Exists; covers pests not yet in Zambia. Website named in [CABI's 2026 IPPC report](https://assets.ippc.int/static/media/files/publication/en/2026/02/INF_07_CPM_2026_CABI_report.pdf); no download or licence found |
| [SADC AIMS](https://aims.sadc.int/) | Exists (SADC with FAO); member-state data; licence not found |
| CABI PRISE | Ran in Zambia from about 2017; current status not found |
| Zambia open data portal | zambia.opendataforafrica.org (AfDB) listed; district agriculture data not confirmed |
| "Agriculture Statistics Archive 2011–2025" | Not found |
| District boundaries | [HDX COD-AB / COD-EM](https://data.humdata.org/dataset/cod-em-zmb) (COD-EM CC BY-IGO) and geoBoundaries (district level). Check they show all 116 districts |
| 2022 Census Analytical Report, ch. 12 | Share of households farming only (65.9%; 88.0% rural); no per-crop data |
