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
        help='Employee whose user has the Fleet Driver access right (shown on the Fleet > Drivers list)',
    )

    def _driver_employee_ids(self):
        """Employees whose user has the Fleet Driver access right"""
        # sudo: anyone picking a driver may not be allowed to read groups or the Drivers list
        group = self.env.ref('fleet_operations_pro.group_fleet_driver', raise_if_not_found=False)
        if not group:
            return []
        users = group.sudo().users.filtered('active')
        return self.sudo().search([('user_id', 'in', users.ids)]).ids

    @api.model_create_multi
    def create(self, vals_list):
        employees = super().create(vals_list)
        if any(vals.get('user_id') for vals in vals_list):
            self.env['fleet.driver']._sync_with_access_rights()
        return employees

    def write(self, vals):
        result = super().write(vals)
        if 'user_id' in vals or 'active' in vals:
            self.env['fleet.driver']._sync_with_access_rights()
        return result

    def _compute_is_fleet_driver(self):
        driver_ids = set(self._driver_employee_ids())
        for employee in self:
            employee.is_fleet_driver = employee.id in driver_ids

    @api.model
    def _search_is_fleet_driver(self, operator, value):
        positive = (operator == '=') == bool(value)
        return [('id', 'in' if positive else 'not in', self._driver_employee_ids())]
