# -*- coding: utf-8 -*-
"""From now on the Fleet Driver access right decides who is a driver.

Keep today's drivers: give the Fleet Driver access right to the user of every
employee currently on the Drivers list (before the new rules archive them).
"""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    group = env.ref('fleet_operations_pro.group_fleet_driver', raise_if_not_found=False)
    if not group:
        return
    cr.execute("""
        SELECT DISTINCT e.user_id
        FROM fleet_driver d
        JOIN hr_employee e ON e.id = d.employee_id
        WHERE d.active AND e.user_id IS NOT NULL
    """)
    user_ids = [row[0] for row in cr.fetchall()]
    if user_ids:
        group.write({'users': [(4, uid) for uid in user_ids]})
