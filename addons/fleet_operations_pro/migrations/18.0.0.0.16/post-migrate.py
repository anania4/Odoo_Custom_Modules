# -*- coding: utf-8 -*-
"""The Vehicle Analysis report (fleet.vehicle.report) was removed. Odoo deletes its
model and menu on upgrade but cannot drop the SQL view that backed it, so do it here."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("DROP VIEW IF EXISTS fleet_vehicle_report")
