# -*- coding: utf-8 -*-
"""Convert the old free-text brand/model columns into fleet.vehicle.model records."""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'fleet_vehicle' AND column_name IN ('brand', 'model')
    """)
    columns = {row[0] for row in cr.fetchall()}
    if 'model' not in columns:
        return
    brand_sql = 'brand' if 'brand' in columns else 'NULL'
    cr.execute(f"""
        SELECT id, TRIM(model), NULLIF(TRIM({brand_sql}), '')
        FROM fleet_vehicle
        WHERE model_id IS NULL AND COALESCE(TRIM(model), '') != ''
    """)
    rows = cr.fetchall()
    if not rows:
        return

    env = api.Environment(cr, SUPERUSER_ID, {})
    Model = env['fleet.vehicle.model'].with_context(active_test=False)
    cache = {}
    for vehicle_id, model_name, brand in rows:
        key = (model_name, brand)
        if key not in cache:
            existing = Model.search([('name', '=', model_name), ('brand', '=', brand or False)], limit=1)
            cache[key] = existing or Model.create({'name': model_name, 'brand': brand or False})
        cr.execute("UPDATE fleet_vehicle SET model_id = %s WHERE id = %s", (cache[key].id, vehicle_id))
