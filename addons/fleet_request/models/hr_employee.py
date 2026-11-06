# -*- coding: utf-8 -*-

from odoo import api, fields, models

# Vehicle status a driver's car must have to take a new fleet request
ACTIVE_CODES = ('active',)


class HrEmployee(models.Model):
    _inherit = 'hr.employee'

    has_active_vehicle = fields.Boolean(
        string='Has an Active Vehicle',
        compute='_compute_has_active_vehicle',
        search='_search_has_active_vehicle',
        help='The vehicle of the current driver assignment is Active (not In Use, In Maintenance...)',
    )

    def _active_vehicle_employee_ids(self):
        """Employees whose current assignment's vehicle has the Active status"""
        today = fields.Date.today()
        # sudo: whoever picks a driver may not be allowed to read assignments
        assignments = self.env['fleet.driver.assignment'].sudo().search([
            ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today),
            ('vehicle_id.status_code', 'in', list(ACTIVE_CODES)),
        ])
        return assignments.employee_id.ids

    def _compute_has_active_vehicle(self):
        employee_ids = set(self._active_vehicle_employee_ids())
        for employee in self:
            employee.has_active_vehicle = employee.id in employee_ids

    @api.model
    def _search_has_active_vehicle(self, operator, value):
        positive = (operator == '=') == bool(value)
        return [('id', 'in' if positive else 'not in', self._active_vehicle_employee_ids())]
