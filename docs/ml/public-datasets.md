# Public image datasets

Open datasets that could add photos for our 19 classes before and alongside the field trips (Build Step 3). Searched
27 Oct 2026 across Zenodo, Mendeley Data, Harvard Dataverse, Dryad, Lacuna Fund and the papers that describe them.

Public photos give the model a head start; they do not replace Zambian field photos. Test scores on them overstate
accuracy on real farms (see [ADR 0014](../decisions/0014-baseline-model-and-export.md)), and a model trained on
another country's fields may miss differences in soil, light and varieties.

## Rules before any public image reaches training

1. **Licence checked on the dataset's own page** (not the paper's licence) and recorded in the table below. Only
   licences that allow reuse (CC0, CC BY, CC BY-SA) are used. Credit the authors in the model's release notes.
2. **Download from the original record** into `<data root>/raw/public/<short-name>/` and check the file checksum
   against the record. The data root is `ml/data/` (git-ignored; tracked with DVC like field batches), or a folder
   outside OneDrive or any synced folder when the repo lives in one: syncing gigabytes of images can exhaust memory
   and bandwidth; for example `C:gri-guard-data`.
3. **Look at a sample of photos before mapping.** Reject a dataset if labels, boxes or text are drawn on the images,
   if the labels are clearly wrong, or if it is a copy of another dataset under a new name.
4. **Map folders with a mapping CSV** as in [training.md](training.md#input). Name the mapping
   `<data root>/raw/public/<short-name>/mapping.csv`.
5. Keep public photos out of the **test** split once field photos exist, so the test score stays a farm score.

## Status by class

| Our classes | Best dataset found | Photos from | Licence | Status |
|-------------|--------------------|-------------|---------|--------|
| `maize__grey_leaf_spot`, `maize__northern_leaf_blight`, `maize__streak_virus`, `maize__healthy` | Zambia Maize Leaf Dataset (ZMLD), [Zenodo 10.5281/zenodo.18430185](https://doi.org/10.5281/zenodo.18430185) | Zambia (Lusaka, Central, Eastern, Northern) | CC BY 4.0 | **Rejected as published** (see below); ask the author for the original photos |
| `maize__lethal_necrosis`, `maize__streak_virus`, `maize__healthy` | NM-AIST / TARI Tanzania maize set: [Harvard Dataverse 10.7910/DVN/GDON8Q](https://doi.org/10.7910/DVN/GDON8Q), update described in [Data in Brief 2024](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC10998077/); copies on [Zenodo](https://zenodo.org/records/15685236) and [Mendeley](https://data.mendeley.com/datasets/fkw49mz3xs/1) | Tanzania, farm phone photos | CC0 1.0 (per Dataverse) | **Accepted** (see below): 14,933 photos ready |
| `maize__streak_virus`, `maize__healthy` | [KaraAgro AI Maize, Harvard Dataverse 10.7910/DVN/CXUMDS](https://doi.org/10.7910/DVN/CXUMDS) (Lacuna Fund) | Ghana | CC0 1.0 (per Dataverse) | Candidate |
| `cassava__mosaic_disease`, `cassava__brown_streak`, `cassava__healthy` | Makerere AI Lab cassava leaf images ([Mak-CAD](https://air.ug/?page_id=3464), [Dataset Ninja](https://datasetninja.com/makerere-university-cassava)) | Uganda fields | To check | Candidate |
| `groundnut__rosette`, `groundnut__early_leaf_spot`, `groundnut__late_leaf_spot`, `groundnut__healthy` | [Mendeley x6x5jkk873](https://data.mendeley.com/datasets/x6x5jkk873/2) (1,720 photos, has rosette); [Mendeley 22p2vcbxfk](https://doi.org/10.17632/22p2vcbxfk.3) (leaf spots, no rosette) | India fields | To check | Candidate; no African set found |
| `soybean__rust`, `soybean__frogeye_leaf_spot`, `soybean__healthy` | Auburn Soybean Disease Image Dataset (ASDID), [Dryad 10.5061/dryad.41ns1rnj3](https://doi.org/10.5061/dryad.41ns1rnj3) (about 1,600 per disease) | Alabama, USA fields | To check | Candidate; no African set found |
| `cotton__bacterial_blight`, `cotton__alternaria_leaf_spot`, `cotton__healthy` | [Mendeley t9hgvk2h9p](https://data.mendeley.com/datasets/t9hgvk2h9p/1) (218 blight, 173 Alternaria) | Bangladesh | To check | Candidate, small; no African set found |
| `maize__common_rust` | No African set found. Lab-style sets (PlantVillage) only, not yet checked | — | — | Gap |

**Biggest gaps:** groundnut rosette from Africa, and anything African for soybean, cotton and common rust. Ask ZARI
(at the M1 agronomist sign-off) and ICRISAT Malawi whether they hold labelled photos.

## Tanzania maize set: accepted

Checked 27 Oct 2026. Four files from Dataverse version 6 (`MLN.zip`, `MSV_1.zip`, `MSV_2.zip`, `HEATHLY.zip`, 4.2 GB),
each matching its published MD5. Field close-ups of single leaves from smartphones, nothing drawn on the images;
labels come from the zip name (the COCO files inside hold no annotations).

| Folder | Class id | Photos kept | Set aside as blurry |
|--------|----------|------------:|--------------------:|
| `HEALTHY` | `maize__healthy` | 4,770 | 347 |
| `MLN` | `maize__lethal_necrosis` | 3,913 | 67 |
| `MSV` | `maize__streak_virus` | 6,250 | 2 |
| **Total** | | **14,933** | **416** |

- **Where:** `<data root>/raw/public/tz-maize/images/` (for example under `C:gri-guard-data`), with
  `mapping.csv` (the `_blurry` folder maps to `skip`), `report.json` and the original zips. The training loader
  reads it as is: `--images <data root>/raw/public/tz-maize/images --mapping
  <data root>/raw/public/tz-maize/mapping.csv`.
- **Fewer than the datasheet:** 15,350 images in the files against 17,277 in the datasheet. One healthy image is
  truncated and unreadable.
- **Blur:** variance of a Laplacian on the image resized to 224 px wide; below 40 is set aside (chosen by eye: 31
  was visibly blurred, 62 sharp). Blurry photos are moved, never deleted.
- **Duplicates:** no byte-identical files. Perceptual hashes (64- and 256-bit dHash) matched *different* photos,
  because close-ups of striped leaves with the midrib across the middle look alike to them; don't use them to
  remove duplicates from leaf close-ups.
- **Limits:** all photos are close-ups of the leaf surface, while farmers will often photograph a whole leaf, so
  the model may not transfer well; and lethal necrosis and streak virus can look alike up close. Ask the
  agronomist to spot-check about 50 photos per class. No farmer or field information, so the split is random
  (training prints a warning).

## Zambia Maize Leaf Dataset: why the Zenodo copy is rejected

The [paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC12976002/) (Kalunga, Kunda and Zimba, ZCAS University, Lusaka)
describes 19,990 phone photos from Zambian smallholder farms, with disease, severity and lesion boxes. The Zenodo record
(`Zambia_Maize_Leaf_Dataset_split.zip`, 143 MB, md5 `9e26e70da3c2f6a75334caa0435d2b02`, checked 27 Oct 2026)
does not match that description:

- **1,388 images**, not 19,990, with 19,164 YOLO label files; most label files have no image.
- **Boxes and text are drawn into the pixels** (class name and `Processed: 2025-10-09`): these are a model's output
  pictures, not original photos. A model trained on them can learn the drawn box instead of the leaf.
- **Every train and val label is class 0 (`Healthy`)** with a whole-image box, including clear streak-virus leaves.
- **About 60% are `Corn_Gray_Spot (n).JPG` files**, the naming of a Kaggle copy of the US PlantVillage lab photos.
  About 560 are WhatsApp / phone photos, probably Zambian.

**Next step:** email the corresponding author (address in the paper) for the original, unannotated photos and their
labels, explain AgriGuard, and offer credit and a share of our field photos in return. If they arrive, they go
through the rules above like any other dataset.
