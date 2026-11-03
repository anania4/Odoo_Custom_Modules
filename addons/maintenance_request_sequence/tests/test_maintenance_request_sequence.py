# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import re

from odoo import fields
from odoo.exceptions import ValidationError
from odoo.tests.common import TransactionCase


class TestMaintenanceRequestSequence(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.team_id = cls.env["maintenance.team"].create(
            {"name": "Maintenance Team", "code_prefix": "MT-TEST"}
        )
        cls.team_id_2 = cls.env["maintenance.team"].create({"name": "Maintenance Team"})

    def test_maintenance_request_sequence(self):
        year = fields.Date.context_today(self.env["maintenance.request"]).year
        sequence = self.env["ir.sequence"].search(
            [("prefix", "=", "MT-TEST/%s/" % "%(range_year)s")]
        )
        self.assertTrue(sequence)
        self.assertTrue(sequence.use_date_range)

        self.assertFalse(self.team_id_2.sequence_id)
        self.team_id_2.write({"code_prefix": "TEAM2-TEST"})
        self.assertTrue(self.team_id_2.sequence_id)
        self.assertTrue(self.team_id_2.sequence_id.use_date_range)

        request_1 = self.env["maintenance.request"].create(
            {"name": "Req 1", "maintenance_team_id": self.team_id.id}
        )
        self.assertRegex(request_1.code, r"^MT-TEST/%s/\d{5}$" % year)
        self.team_id.write({"code_prefix": "MT-TEST-2"})
        request_2 = self.env["maintenance.request"].create(
            {"name": "Req 2", "maintenance_team_id": self.team_id.id}
        )
        self.assertRegex(request_2.code, r"^MT-TEST-2/%s/\d{5}$" % year)

        res = self.env["maintenance.request"].name_search(request_2.code)
        self.assertTrue(res)

    def test_maintenance_request_default_sequence(self):
        year = fields.Date.context_today(self.env["maintenance.request"]).year
        request = self.env["maintenance.request"].create({"name": "Default Req"})
        self.assertRegex(request.code, r"^MR/%s/\d{5}$" % year)
        self.assertNotRegex(request.code, re.escape("%(range_year)s"))


class TestMaintenanceRequestAsset(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vehicle = cls.env["fleet.vehicle"].create(
            {
                "name": "Test Vehicle",
                "license_plate": "TEST-MR-001",
                "category_id": cls.env.ref(
                    "fleet_operations_pro.vehicle_category_car"
                ).id,
            }
        )
        cls.equipment = cls.env["maintenance.equipment"].create(
            {"name": "Test Machine"}
        )

    def test_vehicle_sets_asset_type(self):
        request = self.env["maintenance.request"].create(
            {"name": "Vehicle Req", "vehicle_id": self.vehicle.id}
        )
        self.assertEqual(request.asset_type, "vehicle")
        self.assertEqual(self.vehicle.maintenance_request_count, 1)

    def test_machinery_default_and_optional_equipment(self):
        request = self.env["maintenance.request"].create({"name": "Plain Req"})
        self.assertEqual(request.asset_type, "machinery")
        self.assertFalse(request.equipment_id)

    def test_asset_type_mismatch(self):
        with self.assertRaises(ValidationError):
            self.env["maintenance.request"].create(
                {
                    "name": "Bad Req",
                    "asset_type": "machinery",
                    "vehicle_id": self.vehicle.id,
                }
            )
        with self.assertRaises(ValidationError):
            self.env["maintenance.request"].create(
                {
                    "name": "Bad Req 2",
                    "vehicle_id": self.vehicle.id,
                    "equipment_id": self.equipment.id,
                }
            )

    def test_maintenance_cost(self):
        request = self.env["maintenance.request"].create(
            {"name": "Cost Req", "maintenance_cost": 250.0}
        )
        self.assertEqual(request.maintenance_cost, 250.0)
        self.assertEqual(request.currency_id, request.company_id.currency_id)
        self.assertFalse(request.copy().maintenance_cost)
        with self.assertRaises(ValidationError):
            request.maintenance_cost = -1
