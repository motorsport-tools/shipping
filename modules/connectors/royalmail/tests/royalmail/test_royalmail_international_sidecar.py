"""Royal Mail international sidecar rate-table tests."""

import csv
import pathlib
import unittest
from collections import Counter

import karrio.providers.royalmail.units as provider_units


class TestRoyalMailInternationalSidecar(unittest.TestCase):
    def setUp(self):
        self.maxDiff = None

    def _services_csv_path(self):
        return pathlib.Path(
            getattr(
                provider_units,
                "SERVICES_CSV",
                pathlib.Path(provider_units.__file__).with_name("services.csv"),
            )
        )

    def _sidecar_csv_path(self):
        return pathlib.Path(
            getattr(
                provider_units,
                "ROYALMAIL_INTERNATIONAL_SERVICES_CSV",
                pathlib.Path(provider_units.__file__).with_name(
                    "royalmail-international-services.csv"
                ),
            )
        )

    def _read_services_rows(self):
        with open(self._services_csv_path(), newline="", encoding="utf-8-sig") as csvfile:
            return list(csv.DictReader(csvfile))

    def _read_sidecar_rows(self):
        with open(self._sidecar_csv_path(), newline="", encoding="utf-8-sig") as csvfile:
            return list(csv.DictReader(csvfile))

    def test_royalmail_international_sidecar_file_is_packaged(self):
        self.assertTrue(
            self._sidecar_csv_path().exists(),
            msg="royalmail-international-services.csv must be packaged.",
        )

        rows = self._read_sidecar_rows()

        self.assertGreater(
            len(rows),
            0,
            msg="royalmail-international-services.csv must contain rate rows.",
        )

    def test_services_csv_no_longer_contains_active_royalmail_international_rate_rows(self):
        """
        The main services.csv should be a compact catalogue.

        Active Royal Mail international rate-table rows should live in the
        sidecar, not in services.csv.
        """
        rows = self._read_services_rows()

        cluttered_codes = Counter(
            row.get("service_code")
            for row in rows
            if str(row.get("service_code") or "").startswith(
                "royal_mail_international_"
            )
            and provider_units.service_is_active(row)
            and row.get("rate") not in [None, ""]
            and row.get("zone_min_weight") not in [None, ""]
            and row.get("zone_max_weight") not in [None, ""]
        )

        self.assertEqual(
            dict(cluttered_codes),
            {},
            msg=(
                "Royal Mail international rate rows should be moved to "
                "royalmail-international-services.csv."
            ),
        )

    def test_sidecar_activates_tracked_small_parcel_and_loads_germany_rate_band(self):
        service = provider_units.SERVICE_LEVEL_BY_CODE.get(
            "royal_mail_international_tracked_small_parcel"
        )

        self.assertIsNotNone(service)
        self.assertTrue(provider_units.service_is_active(service))

        germany_zones = [
            zone
            for zone in service.zones or []
            if "DE" in (zone.country_codes or [])
        ]

        self.assertGreater(len(germany_zones), 0)

        first_band = next(
            zone
            for zone in germany_zones
            if zone.min_weight == 0.001
        )

        self.assertEqual(first_band.rate, 8.15)

    def test_sidecar_preserves_grouped_zone_rows_for_standard_letter(self):
        service = provider_units.SERVICE_LEVEL_BY_CODE.get(
            "royal_mail_international_standard_letter"
        )

        self.assertIsNotNone(service)
        self.assertTrue(provider_units.service_is_active(service))

        zones_by_label = {
            zone.label: zone
            for zone in service.zones or []
        }

        self.assertEqual(
            set(zones_by_label),
            {
                "Europe Zone 1",
                "Europe Zone 2",
                "Europe Zone 3",
                "World Zone 1",
                "World Zone 2",
                "World Zone 3",
            },
        )

        self.assertEqual(
            zones_by_label["Europe Zone 1"].country_codes,
            ["IE", "FR", "DE", "DK", "MC"],
        )

        self.assertEqual(
            zones_by_label["World Zone 3"].country_codes,
            ["US"],
        )