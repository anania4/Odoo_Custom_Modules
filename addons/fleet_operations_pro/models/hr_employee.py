# -*- coding: utf-8 -*-

from odoo import api, fields, models

# Domain for every "driver" field in the fleet system: only employees on the Drivers list
DRIVER_DOMAIN = "[('is_fleet_driver', '=', True)]"


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    is_fleet_driver = fields.Boolean(
        string='Is a Fleet Driver',
        compute='_compute_is_fleet_driver',
        search='_search_is_fleet_driver',
        help='Employee registered on the Fleet > Drivers list',
    )

    def _driver_employee_ids(self):
        # sudo: anyone picking a driver may not have read access to the Drivers list itself
        return self.env['fleet.driver'].sudo().search([]).employee_id.ids

    def _compute_is_fleet_driver(self):
        driver_ids = set(self._driver_employee_ids())
        for employee in self:
            employee.is_fleet_driver = employee.id in driver_ids

    @api.model
    def _search_is_fleet_driver(self, operator, value):
        positive = (operator == '=') == bool(value)
        return [('id', 'in' if positive else 'not in', self._driver_employee_ids())]
