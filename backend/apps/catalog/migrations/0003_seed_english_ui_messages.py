"""English defaults for the app's fixed messages.

`uncertain` and `consult` are the wording in docs/model-output.md §4. `rejected` and `no_advice` were written by
the dev team and should be reviewed with the advice text. Editing them later happens in the admin, not here.
"""

from django.db import migrations

ENGLISH = {
    "uncertain": "We are not sure. Please take another photo.",
    "consult": "Please show this plant to an extension officer.",
    "rejected": "This photo is too dark, blurry or far away. Please take another one in daylight, close to the leaf.",
    "no_advice": (
        "We recognised this problem, but advice for it has not been checked by an expert yet. "
        "Please show this plant to an extension officer."
    ),
}


def seed(apps, schema_editor):
    UiMessage = apps.get_model("catalog", "UiMessage")
    for key, text in ENGLISH.items():
        UiMessage.objects.get_or_create(key=key, lang="en", defaults={"text": text})


def unseed(apps, schema_editor):
    apps.get_model("catalog", "UiMessage").objects.filter(lang="en", key__in=ENGLISH).delete()


class Migration(migrations.Migration):
    dependencies = [("catalog", "0002_uimessage")]
    operations = [migrations.RunPython(seed, unseed)]
