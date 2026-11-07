import threading
from datetime import timedelta

import pytest
from django.db import connection
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.bookings.models import Booking
from apps.bookings.services import create_booking

from .factories import SlotFactory, SocietyFactory, UserFactory, VehicleFactory

pytestmark = pytest.mark.django_db(transaction=True)


def run_concurrently(workers):
    results = []
    barrier = threading.Barrier(len(workers))

    def wrap(fn):
        def runner():
            try:
                barrier.wait()
                results.append(("ok", fn()))
            except ValidationError as exc:
                results.append(("rejected", exc))
            finally:
                connection.close()

        return runner

    threads = [threading.Thread(target=wrap(fn)) for fn in workers]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return results


def test_only_one_of_many_simultaneous_requests_gets_the_slot():
    society = SocietyFactory()
    slot = SlotFactory(society=society)
    start = timezone.now() + timedelta(minutes=10)
    end = start + timedelta(hours=2)
    people = [UserFactory(society=society) for _ in range(8)]
    vehicles = [VehicleFactory(user=p) for p in people]

    results = run_concurrently(
        [
            (lambda p=p, v=v: create_booking(p, slot.id, v, start, end))
            for p, v in zip(people, vehicles, strict=True)
        ]
    )

    outcomes = [r[0] for r in results]
    assert outcomes.count("ok") == 1
    assert outcomes.count("rejected") == 7
    assert Booking.objects.filter(slot=slot).count() == 1
