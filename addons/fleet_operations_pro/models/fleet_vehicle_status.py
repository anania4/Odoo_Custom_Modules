# -*- coding: utf-8 -*-

from odoo import _, api, fields, models
from odoo.exceptions import UserError

# Statuses the system relies on (dashboard, driver switch, request assignment, maintenance):
# they cannot be deleted or edited
LOCKED_STATUS_CODES = ('active', 'in use', 'in_use', 'in_maintenance')
# Changes still allowed on a locked status: its position in the list / kanban columns
LOCKED_ALLOWED_FIELDS = {'sequence'}


class FleetVehicleStatus(models.Model):
    _name = 'fleet.vehicle.status'
    _description = 'Vehicle Status'
    _order = 'sequence, name'

    name = fields.Char(string='Status Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    color = fields.Integer(string='Color', default=0)
    description = fields.Text(string='Description', translate=True)
    active = fields.Boolean(string='Active', default=True)
    is_locked = fields.Boolean(
        string='Locked',
        compute='_compute_is_locked',
        help='System status: cannot be deleted or changed',
    )

    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Status code must be unique!'),
    ]

    @api.depends('code')
    def _compute_is_locked(self):
        for status in self:
            status.is_locked = (status.code or '') in LOCKED_STATUS_CODES

    def _locked(self):
        # data loading and migrations (superuser mode) may still update it
        return self.browse() if self.env.su else self.filtered('is_locked')

    def write(self, vals):
        if set(vals) - LOCKED_ALLOWED_FIELDS:
            locked = self._locked()
            if locked:
                raise UserError(_(
                    'The "%s" status is used by the fleet system (dashboard, driver switch, maintenance) '
                    'and cannot be changed.') % locked[0].name)
        return super().write(vals)

    @api.ondelete(at_uninstall=False)
    def _unlink_except_locked(self):
        locked = self._locked()
        if locked:
            raise UserError(_(
                'The "%s" status is used by the fleet system (dashboard, driver switch, maintenance) '
                'and cannot be deleted.') % locked[0].name)
