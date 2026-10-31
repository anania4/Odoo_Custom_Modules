# -*- coding: utf-8 -*-
"""Before this version every internal user could use the whole fleet system.

Keep existing internal users able to ask for vehicles and fuel: give the
Fleet User role to every internal user that has no fleet role yet.
Fleet Viewer / Fuel Filler / Fleet Manager must then be granted explicitly.
"""

from odoo import api, SUPERUSER_ID

FLEET_GROUPS = [
    'fleet_operations_pro.group_fleet_user',
    'fleet_operations_pro.group_fleet_viewer',
    'fleet_operations_pro.group_fleet_manager',
    'fleet_request.group_fuel_filler',
]


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    fleet_user = env.ref('fleet_operations_pro.group_fleet_user')
    groups = env['res.groups']
    for xmlid in FLEET_GROUPS:
        groups |= env.ref(xmlid, raise_if_not_found=False) or env['res.groups']
    internal = env['res.users'].search([('share', '=', False)])  # active users only, not the default user template
    without_role = internal.filtered(lambda u: not (u.groups_id & groups))
    if without_role:
        fleet_user.write({'users': [(4, uid) for uid in without_role.ids]})
