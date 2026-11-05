# -*- coding: utf-8 -*-
"""Fleet Viewer no longer includes Fleet Driver (viewers and managers are not drivers
just because they can see the fleet). XML only adds inclusions, so remove it here,
then align the Drivers list with the Fleet Driver access right."""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    viewer = env.ref('fleet_operations_pro.group_fleet_viewer')
    driver = env.ref('fleet_operations_pro.group_fleet_driver')
    if driver in viewer.implied_ids:
        viewer.write({'implied_ids': [(3, driver.id)]})
    env['fleet.driver']._sync_with_access_rights()
