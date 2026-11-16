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
| Zambia Maize Leaf Dataset | CC BY 4.0 | The Zenodo upload holds 1,388 of the 19,990 images described, mostly Kaggle/PlantVillage copies, with contradictory labels. We have asked the author for the full set. | Kalunga, P. (2026). *Zambia Maize Leaf Dataset* [Data set]. Zenodo. https://doi.org/10.5281/zenodo.18430185 |

## Approved for licence, not downloaded

These need the team's agreement on download size first. If used, attribute them as follows (CC BY 4.0):

- Mduma, N., & Mayo, F. (2023). *Maize imagery dataset - Tanzania* (Version 1) [Data set]. Mendeley Data.
  https://doi.org/10.17632/fkw49mz3xs.1. Described in Mduma & Mayo, *Data in Brief* 54 (2024) 110359.
- Mensah Kwabena, P., Akoto-Adjepong, V., Adu, K., et al. (2023). *Dataset for Crop Pest and Disease
  Detection* (Version 1) [Data set]. Mendeley Data. https://doi.org/10.17632/bwh3zbpkpv.1.
  (Author order to be checked against the Mendeley page before publication.)

## Not usable

- Wiesner-Hanks et al. (2018), maize NLB field images on OSF (https://osf.io/p67rz/): no licence is recorded on
  the OSF project, so it must not be downloaded until the authors confirm one.
