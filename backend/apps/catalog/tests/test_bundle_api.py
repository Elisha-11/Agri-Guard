"""GET /api/v1/advisory/bundle/: content rules, language fallback and ETag caching."""

from datetime import date

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from rest_framework.test import APIClient

from apps.catalog.models import DiseaseAdvice, UiMessage
from apps.core.tests.contract import assert_matches_contract
from apps.core.tests.factories import DiseaseAdviceFactory

URL = "/api/v1/advisory/bundle/"
REVIEW = {"is_published": True, "reviewed_by": "Dr. Mwale, ZARI", "reviewed_at": date(2026, 10, 20)}


@pytest.fixture
def api():
    return APIClient()


def publish(taxonomy, class_id, lang="en", **fields):
    return DiseaseAdviceFactory(disease=taxonomy[class_id], lang=lang, **{**REVIEW, **fields})


def get(api, lang="en", **headers):
    return api.get(URL, {"lang": lang}, **headers)


def bundle(api, lang="en"):
    response = get(api, lang)
    assert response.status_code == 200, response.json()
    body = response.json()
    assert_matches_contract(body, "AdvisoryBundle")
    return body


def by_id(body):
    return {d["class_id"]: d for d in body["diseases"]}


class TestContent:
    def test_contract_shape(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot", local_name="", safety_warning="")
        body = bundle(api)
        assert body["lang"] == "en"
        assert body["taxonomy_version"] == "0.1"
        [entry] = body["diseases"]
        assert entry["class_id"] == "maize__grey_leaf_spot"
        assert entry["local_name"] is None and entry["safety_warning"] is None
        assert entry["reviewed_at"] == "2026-10-20"
        assert set(entry["treatment"]) == {"title", "steps", "audio_url"}

    def test_only_published_advice(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot")
        DiseaseAdviceFactory(disease=taxonomy["maize__common_rust"])  # draft: not reviewed or published
        assert set(by_id(bundle(api))) == {"maize__grey_leaf_spot"}

    def test_diseases_in_model_output_order(self, api, taxonomy):
        for class_id in ["cotton__healthy", "maize__healthy", "groundnut__rosette"]:
            publish(taxonomy, class_id)
        assert [d["class_id"] for d in bundle(api)["diseases"]] == [
            "maize__healthy",
            "groundnut__rosette",
            "cotton__healthy",
        ]

    def test_chemical_advice_carries_its_safety_warning(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot", involves_chemicals=True, safety_warning="Wear gloves.")
        assert by_id(bundle(api))["maize__grey_leaf_spot"]["safety_warning"] == "Wear gloves."

    def test_empty_catalog_is_still_a_valid_bundle(self, api, db):
        body = bundle(api)
        assert body["diseases"] == []
        assert set(body["ui"]) == {"uncertain", "consult", "rejected", "no_advice"}


class TestLanguages:
    def test_requested_language_is_used_when_published(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot", name="Grey Leaf Spot")
        publish(taxonomy, "maize__grey_leaf_spot", lang="ny", name="Matenda a masamba")
        entry = by_id(bundle(api, "ny"))["maize__grey_leaf_spot"]
        assert (entry["lang"], entry["name"]) == ("ny", "Matenda a masamba")

    def test_falls_back_to_english_per_disease(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot")
        publish(taxonomy, "maize__common_rust")
        publish(taxonomy, "maize__common_rust", lang="bem", name="Bemba name")
        entries = by_id(bundle(api, "bem"))
        assert entries["maize__grey_leaf_spot"]["lang"] == "en"
        assert entries["maize__common_rust"]["lang"] == "bem"

    def test_unpublished_translation_falls_back_to_english(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot", name="Grey Leaf Spot")
        DiseaseAdviceFactory(disease=taxonomy["maize__grey_leaf_spot"], lang="toi", name="Draft")
        entry = by_id(bundle(api, "toi"))["maize__grey_leaf_spot"]
        assert (entry["lang"], entry["name"]) == ("en", "Grey Leaf Spot")

    def test_ui_messages_fall_back_key_by_key(self, api, db):
        UiMessage.objects.create(key="consult", lang="ny", text="Nyanja consult message")
        ui = bundle(api, "ny")["ui"]
        assert ui["consult"] == "Nyanja consult message"
        assert ui["uncertain"] == "We are not sure. Please take another photo."  # English default

    @pytest.mark.parametrize("lang", ["fr", "", "EN"])
    def test_unknown_language_is_a_400(self, api, db, lang):
        response = get(api, lang)
        assert response.status_code == 400
        assert_matches_contract(response.json(), "Error")
        assert "lang" in response.json()["fields"]

    def test_lang_is_required(self, api, db):
        assert api.get(URL).status_code == 400


class TestCaching:
    def test_etag_and_no_cache(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot")
        response = get(api)
        body = response.json()
        assert response["ETag"] == f'"{body["bundle_version"]}"'
        assert response["Cache-Control"] == "no-cache"

    def test_unchanged_bundle_is_a_304_with_no_body(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot")
        etag = get(api)["ETag"]
        response = get(api, HTTP_IF_NONE_MATCH=etag)
        assert response.status_code == 304
        assert not response.content
        assert response["ETag"] == etag

    def test_weak_and_listed_etags_match(self, api, taxonomy):
        etag = get(api)["ETag"]
        assert get(api, HTTP_IF_NONE_MATCH=f'"other", W/{etag}').status_code == 304

    @pytest.mark.parametrize(
        "change",
        [
            lambda t: publish(t, "maize__common_rust"),  # new advice
            lambda t: DiseaseAdvice.objects.update(name="Renamed"),  # edited
            lambda t: DiseaseAdvice.objects.update(is_published=False),  # unpublished
            lambda t: DiseaseAdvice.objects.all().delete(),  # deleted
            lambda t: UiMessage.objects.filter(key="consult").update(text="New wording"),  # ui text
        ],
    )
    def test_any_content_change_gives_a_new_version(self, api, taxonomy, change):
        publish(taxonomy, "maize__grey_leaf_spot")
        before = get(api)
        change(taxonomy)
        after = get(api, HTTP_IF_NONE_MATCH=before["ETag"])
        assert after.status_code == 200
        assert after["ETag"] != before["ETag"]

    def test_each_language_has_its_own_version(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot")
        assert get(api, "en")["ETag"] != get(api, "ny")["ETag"]

    def test_version_starts_with_the_latest_change_date(self, api, taxonomy):
        publish(taxonomy, "maize__grey_leaf_spot")
        assert bundle(api)["bundle_version"][:4].isdigit()


def test_is_public(api, db):
    assert get(api).status_code == 200  # no token: the PWA fetches it on first launch


class TestSampleAdvice:
    def test_loads_published_placeholders_in_debug(self, api, taxonomy, settings):
        settings.DEBUG = True
        call_command("load_sample_advice", "--all-languages", verbosity=0)
        assert DiseaseAdvice.objects.count() == 19 * 4
        entry = by_id(bundle(api, "ny"))["maize__healthy"]
        assert entry["lang"] == "ny"
        assert entry["reviewed_by"] == "SAMPLE DATA - NOT FOR FARMERS"

    def test_refuses_without_debug(self, taxonomy, settings):
        settings.DEBUG = False
        with pytest.raises(CommandError, match="DEBUG"):
            call_command("load_sample_advice", verbosity=0)
        assert not DiseaseAdvice.objects.exists()
