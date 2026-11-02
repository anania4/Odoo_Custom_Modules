# -*- coding: utf-8 -*-
"""Driver fields now only accept employees on the Fleet > Drivers list.

Register every employee who already drives (vehicle delegations, trips,
fuel logs, tolls) on that list, so existing data stays selectable.
"""

from odoo import api, SUPERUSER_ID

SOURCES = [
    ('fleet_driver_assignment', 'employee_id'),
    ('fleet_trip', 'driver_id'),
    ('fleet_fuel_log', 'driver_id'),
    ('fleet_toll_record', 'driver_id'),
]


def migrate(cr, version):
    if not version:
        return
    employee_ids = set()
    for table, column in SOURCES:
        cr.execute(f"SELECT DISTINCT {column} FROM {table} WHERE {column} IS NOT NULL")
        employee_ids.update(row[0] for row in cr.fetchall())
    if not employee_ids:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Driver = env['fleet.driver'].with_context(active_test=False)
    existing = set(Driver.search([]).employee_id.ids)
    missing = env['hr.employee'].browse(sorted(employee_ids - existing)).exists()
    if missing:
        Driver.create([{'employee_id': employee.id} for employee in missing])
