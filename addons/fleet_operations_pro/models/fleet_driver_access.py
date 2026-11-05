# -*- coding: utf-8 -*-
"""The Fleet Driver access right decides who is a driver.

Granting the right puts the user's employee on the Drivers list (Fleet > Drivers);
removing it archives the driver record. Every driver field of the fleet system
only offers these employees (see hr.employee.is_fleet_driver).
"""

from odoo import _, api, models
from odoo.exceptions import ValidationError

DRIVER_GROUP = 'fleet_operations_pro.group_fleet_driver'


class FleetDriver(models.Model):
    _inherit = 'fleet.driver'

    @api.model
    def _sync_with_access_rights(self):
        """Make the Drivers list match the users who have the Fleet Driver access right"""
        Driver = self.sudo().with_context(active_test=False, fleet_driver_sync=True)
        Employee = self.env['hr.employee'].sudo()
        driver_employees = Employee.browse(Employee._driver_employee_ids())
        records = Driver.search([])
        by_employee = {record.employee_id.id: record for record in records}

        to_create = []
        for employee in driver_employees:
            record = by_employee.get(employee.id)
            if not record:
                to_create.append({'employee_id': employee.id})
            elif not record.active:
                record.active = True
        if to_create:
            Driver.create(to_create)
        records.filtered(lambda r: r.active and r.employee_id not in driver_employees).write({'active': False})

    @api.constrains('employee_id', 'active')
    def _check_driver_access_right(self):
        if self.env.context.get('fleet_driver_sync'):
            return
        group = self.env.ref(DRIVER_GROUP, raise_if_not_found=False)
        for driver in self.filtered('active'):
            user = driver.employee_id.user_id
            if not user or not group or group not in user.groups_id:
                raise ValidationError(_(
                    '%s cannot be a driver: give their user the "Fleet Driver" access right '
                    '(Settings > Users > Access Rights > Fleet Operations). '
                    'They are then added to the Drivers list automatically.'
                ) % driver.employee_id.name)


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model_create_multi
    def create(self, vals_list):
        users = super().create(vals_list)
        self.env['fleet.driver']._sync_with_access_rights()
        return users

    def write(self, vals):
        result = super().write(vals)
        # the user form sends access rights as groups_id or as in_group_* / sel_groups_* fields
        if any(key == 'groups_id' or key.startswith(('in_group_', 'sel_groups_')) or key == 'active'
               for key in vals):
            self.env['fleet.driver']._sync_with_access_rights()
        return result


class ResGroups(models.Model):
    _inherit = 'res.groups'

    def write(self, vals):
        result = super().write(vals)
        if 'users' in vals or 'implied_ids' in vals:
            self.env['fleet.driver']._sync_with_access_rights()
        return result
