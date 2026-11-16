# Credits: public datasets

AgriGuard's model work uses openly licensed image datasets alongside our own field photos. Images are never
committed to this repository; they are downloaded by `ml/scripts/fetch_public.py`, which records each file's
URL, licence, DOI, checksum and download date in `ml/data/external/sources.json`.

CC BY 4.0 requires attribution wherever the data, or a model trained on it, is shared: keep this list with
every model release and in any publication or report that uses these datasets.

## Used

| Dataset | Licence | Attribution |
|---------|---------|-------------|
| The KaraAgro AI Maize Dataset (V4.1). Subset: `healthy_01`, `maize_streak_01` | CC0 1.0 (no attribution required; credited as a courtesy) | Akogo, D., Samori, I., Acquaye, C., Addo, M., Amoako, E., Ezroa-Cudjoe, F., Buaba, J., Seloame, T. N., Mavis, A., Bright, H., Gyasi-Darko, K., Ababio, Y. O., & Clinton, D. A. (2022). *The KaraAgro AI Maize Dataset* (V4.1) [Data set]. Harvard Dataverse. https://doi.org/10.7910/DVN/CXUMDS. Funded by Lacuna Fund. |

## Downloaded but not used

| Dataset | Licence | Why not used | Attribution (if it is used later) |
|---------|---------|--------------|-----------------------------------|
| Zambia Maize Leaf Dataset | CC BY 4.0 | The Zenodo upload holds 1,388 of the 19,990 images described, mostly Kaggle/PlantVillage copies, with contradictory labels. A request for the full set is drafted for the author (not yet sent). | Kalunga, P. (2026). *Zambia Maize Leaf Dataset* [Data set]. Zenodo. https://doi.org/10.5281/zenodo.18430185 |

## Accepted, reviewed by Elisha (27 Oct 2026)

| Dataset | Licence | Attribution |
|---------|---------|-------------|
| The Nelson Mandela African Institution of Science and Technology Maize dataset (V6) ("tz-maize") | CC0 1.0 (no attribution required; credited as a courtesy) | Mduma, N., Laizer, H., Loyani, L., Macheli, M., Msengi, Z., Karama, A., Msaki, I., Sanga, S., & Jomanga, K. (2023). *The Nelson Mandela African Institution of Science and Technology Maize dataset* (V6) [Data set]. Harvard Dataverse. https://doi.org/10.7910/DVN/GDON8Q |

The Mendeley copy of the Tanzania photos (Mduma & Mayo, 2023, https://doi.org/10.17632/fkw49mz3xs.1, CC BY 4.0) is
superseded by the Dataverse set above and was not downloaded.

## Licence fine, not yet downloaded

Needs the team's agreement first. If used, attribute it as follows (CC BY 4.0):

- Mensah Kwabena, P., Akoto-Adjepong, V., Adu, K., et al. (2023). *Dataset for Crop Pest and Disease
  Detection* (Version 1) [Data set]. Mendeley Data. https://doi.org/10.17632/bwh3zbpkpv.1.
  (Author order to be checked against the Mendeley page before publication.)

## Not usable

- Wiesner-Hanks et al. (2018), maize NLB field images on OSF (https://osf.io/p67rz/): no licence is recorded on
  the OSF project, so it must not be downloaded until the authors confirm one.
