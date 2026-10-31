# -*- coding: utf-8 -*-
"""Rename vin_sn -> chassis_no so existing chassis numbers are kept."""


def _column_exists(cr, table, column):
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = %s AND column_name = %s
    """, (table, column))
    return bool(cr.fetchone())


def migrate(cr, version):
    if not version:
        return
    if _column_exists(cr, 'fleet_vehicle', 'vin_sn') and \
            not _column_exists(cr, 'fleet_vehicle', 'chassis_no'):
        cr.execute("ALTER TABLE fleet_vehicle DROP CONSTRAINT IF EXISTS fleet_vehicle_vin_sn_unique")
        cr.execute("ALTER TABLE fleet_vehicle RENAME COLUMN vin_sn TO chassis_no")
