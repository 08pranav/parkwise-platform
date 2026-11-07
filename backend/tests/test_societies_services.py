import json
from datetime import timedelta
from decimal import Decimal
from unittest import mock
from urllib.error import URLError

import pytest
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.societies import services as geo

from .factories import SlotFactory, SocietyFactory

# Gateway of India and Chhatrapati Shivaji Terminus, Mumbai: about 1.9 km apart.
GATEWAY = (18.9220, 72.8347)
CSMT = (18.9398, 72.8355)


def test_haversine_known_distance():
    assert geo.haversine_distance_km(*GATEWAY, *CSMT) == pytest.approx(1.98, abs=0.1)
    assert geo.haversine_distance_km(*GATEWAY, *GATEWAY) == 0


RAW = {
    "place_id": 42,
    "display_name": "Colaba Causeway, Colaba, Mumbai, Maharashtra, India",
    "lat": "18.91",
    "lon": "72.83",
    "address": {
        "road": "Colaba Causeway",
        "suburb": "Colaba",
        "city": "Mumbai",
        "state": "Maharashtra",
        "postcode": "400005",
    },
}


def test_format_location_result_extracts_the_address_parts():
    result = geo._format_location_result(RAW)
    assert result["title"] == "Colaba Causeway"
    assert result["city"] == "Mumbai" and result["pincode"] == "400005"
    assert result["address"] == "Colaba Causeway, Colaba"
    assert result["latitude"] == 18.91


def test_format_location_result_falls_back_when_details_are_missing():
    result = geo._format_location_result({"lat": "1", "lon": "2"}, fallback_label="1.0, 2.0")
    assert result["label"] == "1.0, 2.0" and result["city"] == ""


def test_autocomplete_maps_provider_results():
    with mock.patch.object(geo, "_request_location_json", return_value=[RAW]) as call:
        results = geo.autocomplete_destinations("colaba", limit=3)
    assert results[0]["place_id"] == "42"
    assert call.call_args.args[1]["limit"] == 3


def test_autocomplete_returns_nothing_when_the_provider_fails():
    with mock.patch.object(geo, "_request_location_json", return_value=None):
        assert geo.autocomplete_destinations("x") == []


def test_reverse_geocode_error_becomes_a_validation_error():
    with mock.patch.object(geo, "_request_location_json", return_value={"error": "nope"}):
        with pytest.raises(ValidationError):
            geo.reverse_geocode_destination(1.0, 2.0)
    with mock.patch.object(geo, "_request_location_json", return_value=None):
        with pytest.raises(ValidationError):
            geo.reverse_geocode_destination(1.0, 2.0)


def test_reverse_geocode_success():
    with mock.patch.object(geo, "_request_location_json", return_value=RAW):
        assert geo.reverse_geocode_destination(18.91, 72.83)["city"] == "Mumbai"


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def read(self):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_request_returns_parsed_json():
    with mock.patch.object(geo, "urlopen", return_value=FakeResponse(json.dumps([1]).encode())):
        assert geo._request_location_json("https://example.test", {"q": "x"}) == [1]


@pytest.mark.parametrize("error", [URLError("down"), TimeoutError(), OSError()])
def test_request_swallows_network_errors(error):
    with mock.patch.object(geo, "urlopen", side_effect=error):
        assert geo._request_location_json("https://example.test", {"q": "x"}) is None


def test_request_swallows_invalid_json():
    with mock.patch.object(geo, "urlopen", return_value=FakeResponse(b"<html>")):
        assert geo._request_location_json("https://example.test", {"q": "x"}) is None


@pytest.mark.django_db
class TestSearch:
    def search(self, **kw):
        start = timezone.now() + timedelta(minutes=10)
        return geo.search_societies_by_availability(
            destination_lat=GATEWAY[0],
            destination_lng=GATEWAY[1],
            start_time=start,
            end_time=start + timedelta(hours=2),
            vehicle_type="car",
            **kw,
        )

    def test_only_nearby_societies_with_free_slots_are_returned_nearest_first(self):
        near = SocietyFactory(latitude=Decimal("18.9300"), longitude=Decimal("72.8350"))
        nearer = SocietyFactory(latitude=Decimal("18.9230"), longitude=Decimal("72.8350"))
        far = SocietyFactory(latitude=Decimal("19.2000"), longitude=Decimal("72.9700"))
        empty = SocietyFactory(latitude=Decimal("18.9250"), longitude=Decimal("72.8350"))
        for society, rate in ((near, "40"), (nearer, "25"), (far, "10")):
            SlotFactory(society=society, hourly_rate=Decimal(rate))
        result = self.search()
        assert [r["id"] for r in result["results"]] == [str(nearer.id), str(near.id)]
        assert result["results"][0]["starting_hourly_rate"] == "25.00"
        assert str(empty.id) not in [r["id"] for r in result["results"]]

    def test_radius_can_be_widened(self):
        far = SocietyFactory(latitude=Decimal("19.2000"), longitude=Decimal("72.9700"))
        SlotFactory(society=far)
        assert self.search()["results"] == []
        assert len(self.search(search_radius_km=50)["results"]) == 1

    def test_societies_without_coordinates_and_inactive_ones_are_skipped(self):
        SlotFactory(society=SocietyFactory(latitude=None, longitude=None))
        SlotFactory(
            society=SocietyFactory(
                latitude=Decimal("18.92"), longitude=Decimal("72.83"), is_active=False
            )
        )
        assert self.search()["results"] == []
