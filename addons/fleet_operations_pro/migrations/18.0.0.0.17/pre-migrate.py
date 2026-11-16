# -*- coding: utf-8 -*-
"""The "In Use" vehicle status is now shipped with the module (driver switch and
fleet request assignment need it). Databases where it was created by hand keep
their record: link it to the new XML ID so the data file does not add a duplicate."""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT 1 FROM ir_model_data
        WHERE module = 'fleet_operations_pro' AND name = 'vehicle_status_in_use'
    """)
    if cr.fetchone():
        return
    cr.execute("""
        SELECT id FROM fleet_vehicle_status
        WHERE lower(trim(code)) IN ('in use', 'in_use')
        ORDER BY id LIMIT 1
    """)
    row = cr.fetchone()
    if row:
        cr.execute("""
            INSERT INTO ir_model_data (module, name, model, res_id, noupdate)
            VALUES ('fleet_operations_pro', 'vehicle_status_in_use', 'fleet.vehicle.status', %s, true)
        """, (row[0],))
