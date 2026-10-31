# -*- coding: utf-8 -*-
"""New access model: Fleet User / Fuel Filler / Fleet Viewer / Fleet Manager.

Remove the old record rules (noupdate, so Odoo would keep them) and the unused
Fleet Driver / Fleet Maintenance Team groups. Their rules must go first: a rule
whose groups are all deleted becomes a global rule and would restrict everyone.
"""

from odoo import api, SUPERUSER_ID

OLD_RULES = [
    'fleet_vehicle_manager_rule',
    'fleet_vehicle_user_rule',
    'fleet_driver_own_trips_rule',
    'fleet_driver_own_fuel_rule',
    'fleet_driver_assigned_vehicles_rule',
    'fleet_maintenance_vehicle_rule',
    'fleet_maintenance_maintenance_rule',
    'fleet_viewer_vehicle_rule',
]
OLD_GROUPS = ['group_fleet_driver', 'group_fleet_maintenance']


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid in OLD_RULES:
        rule = env.ref(f'fleet_operations_pro.{xmlid}', raise_if_not_found=False)
        if rule:
            rule.unlink()
    for xmlid in OLD_GROUPS:
        group = env.ref(f'fleet_operations_pro.{xmlid}', raise_if_not_found=False)
        if group:
            group.write({'users': [(5, 0, 0)]})
            group.unlink()
