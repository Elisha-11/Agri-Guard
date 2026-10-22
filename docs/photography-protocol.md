AgriGuard AI: Field Photography Protocol v1.0

Status: Proposed for team review
Purpose: Standardise field image collection for the AgriGuard AI crop disease detection and farmer advisory platform.

1. Collection objectives

Collect at least 6,000 field images by 28 October 2026, covering the five target crops:

- Maize
- Groundnut
- Cassava
- Soybean
- Cotton

Collection should cover three agro-ecological zones, different disease development stages, and healthy plants. Include suspected disease cases and visually similar conditions such as pest damage, nutrient deficiencies and water stress.

Collectors must record suspected classes only. They must not present field observations as confirmed diagnoses.

2. Types of photographs

Collect two types of images:

- Controlled images: Photographs taken under consistent conditions for benchmarking.
- In-the-wild images: Photographs taken under normal field conditions, including variation in lighting, backgrounds and devices.

For each photograph:

- Ensure the relevant leaf or plant symptoms are visible and in focus.
- Avoid cutting off important symptoms.
- Use natural, even lighting where possible.
- Do not use digital zoom, beauty filters or image enhancement.
- Keep original photographs unedited.
- Use JPEG format as a proposed standard, subject to team approval.

A distance of approximately 15–25 cm and a camera resolution around 12 MP are proposed starting guidelines. Test them during the pilot before adopting them as final requirements.

Minimum image dimensions and any automated image-quality thresholds must be confirmed against the actual validation script.

3. Additional views and image linking

Where useful, collect additional views of the same leaf or plant, such as:

- The underside of a leaf.
- A close-up of visible symptoms.
- A wider view showing the whole plant.

Save each view as a separate image with its own filename and metadata row.

Where reliable plant or leaf identifiers are available, use them to link the views. Do not count multiple views of the same leaf as independent examples when assessing dataset size or splitting data.

Plant and leaf identifier fields are proposed additions and must not be introduced into the existing metadata CSV without team approval.

4. Healthy plants and uncertain cases

Include healthy plants and, where available, cases that resemble disease symptoms but may have other causes, including:

- Nutrient deficiencies.
- Pest damage.
- Water stress.
- Physical damage.

Do not guess a disease when the symptoms are uncertain. Record the suspected class using only values permitted by the existing metadata schema.

The final disease class list must follow the approved "docs/class-taxonomy.md". Until the agronomist signs off on the taxonomy, class assignments and labelling remain provisional.

5. Metadata requirements

Every photograph must have a corresponding row in the batch metadata CSV.

The current "ml/README.md" specifies these nine metadata columns:

filename,crop,suspected_class,stage,gps_lat,gps_lng,captured_at,photographer,zone

Use these existing column names and the permitted values defined by the project's data tooling.

- "filename": Image filename.
- "crop": Crop represented in the image.
- "suspected_class": Suspected class, not a confirmed diagnosis.
- "stage": Observed disease or development stage, using the project's permitted values.
- "gps_lat": Latitude, where collection of GPS data is permitted and necessary.
- "gps_lng": Longitude, where collection of GPS data is permitted and necessary.
- "captured_at": Date and time of capture.
- "photographer": Approved collector identifier.
- "zone": Agro-ecological zone.

Do not add columns or change column names without approval.

Fields such as "field_id", "farmer_code", "notes", plant or leaf identifiers, reviewer, confidence and device information may be useful, but they are proposed additions. Confirm the metadata template, data-validation rules and dataset-splitting requirements before changing the schema.

6. Dataset balance and splitting

Track image counts across crops, suspected classes, stages and agro-ecological zones. Where the necessary identifiers are available, also monitor representation across farmers, fields and collectors.

Vary farms, planting dates and crop varieties where practical. Avoid collecting nearly identical images simply to increase the total count.

Dataset splitting must be performed by field and by farmer, never by random shuffle. This prevents images from the same field or farmer from appearing across training and test sets in ways that inflate performance.

Where multiple views of the same plant or leaf can be identified reliably, keep those views in the same dataset partition.

7. Consent and privacy

Before collection begins, agree on the consent process, languages and method of recording consent.

- Use approved anonymous identifiers.
- Do not include farmers' names or phone numbers in image filenames.
- Collect GPS coordinates only when necessary and permitted.
- Restrict access to raw images and metadata.
- Remove unnecessary identifying EXIF information before images are shared externally.
- Follow the team's agreed data-handling and storage procedures.

Do not begin independent collection until collectors have received a briefing on consent and privacy requirements.

8. File organisation and backups

Use the team's agreed batch folder naming convention. The following format is proposed:

"YYYY-MM-DD_place_initials/"

Example:

"2026-10-20_chisamba_ea/"

Use unique image filenames within each batch, for example:

"IMG_001.jpg"

Ensure each filename matches its metadata row.

Keep original photographs unedited and upload the raw field photos to Google Drive on the same evening they are collected. Confirm that the upload completed successfully before relying on it as a backup.

The project uses DVC to track datasets. Datasets must not be committed directly to Git. Follow the repository's established DVC workflow after the data has been validated.

9. Pilot collection

Before full-scale collection, conduct a pilot of approximately 50–100 photographs.

Use the pilot to assess:

- Photographing distance and focus.
- Lighting and background conditions.
- Image quality across available devices.
- Metadata completeness and permitted values.
- Filename and metadata-row matching.
- The practicality of collecting healthy and uncertain cases.
- Consent procedures and privacy.
- Backup and upload procedures.
- Compatibility with the existing validation tools.

The following are proposed pilot acceptance criteria, subject to team approval:

1. Every image has a matching metadata row.
2. Required metadata fields pass validation.
3. At least 90% of images pass the checker without errors on the first attempt.
4. Consent is documented according to the agreed process.
5. An agronomist reviews the provisional class assignments.
6. Problems and corrective actions are recorded.

Review the pilot findings with the team before adopting final collection rules.

10. Validation and dataset versioning

Use the repository's actual validation scripts and follow their documented commands. Confirm the current command-line arguments before running a batch; do not assume that an unverified command is correct.

Resolve validation errors before adding a batch to the versioned dataset. Have a designated reviewer assess warnings, and arrange independent checks of a sample of collected batches.

Passing automated validation does not establish that a disease label is scientifically correct. Expert review remains necessary.

Use DVC for dataset versioning, not Git. Preserve the raw originals and follow the team's established procedure for moving validated data into the appropriate dataset stages.

11. Decisions required before full collection

The team must agree on the following before finalising this protocol:

- Consent process, languages and recording method.
- Whether additional metadata fields are required and how they will be validated.
- How farmer and field identifiers will be managed to support leakage-free splitting.
- Final photographing distance, resolution and background guidance.
- Whether a colour reference card is required for every image or only selected controlled images.
- Rules for healthy and uncertain cases.
- The number of additional views permitted per leaf or plant.
- Pilot acceptance criteria and handling of validation warnings.
- Backup verification and access arrangements.
- The final disease taxonomy, following agronomist sign-off.

Approval: This protocol remains a proposal until reviewed and approved by the team. Changes to documentation under "docs/" must follow the repository's team-approval rules.