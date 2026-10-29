# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetService(models.Model):
    _name = 'fleet.service'
    _description = 'Fleet Service'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Service Reference',
        default='New',
        readonly=True,
        copy=False,
        help='Service reference'
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help='Vehicle that received this service'
    )

    service_type_id = fields.Many2one(
        'fleet.maintenance.type',
        string='Service Type',
        required=True,
        tracking=True,
        help='Type of service performed'
    )

    date = fields.Date(
        string='Service Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date the service was performed'
    )

    description = fields.Text(
        string='Description',
        help='Detailed description of the service work'
    )

    service_provider = fields.Char(
        string='Service Provider',
        help='Garage, vendor or workshop that performed the service'
    )

    odometer = fields.Float(
        string='Odometer (km)',
        tracking=True,
        help='Vehicle odometer reading at the time of service'
    )

    contract_id = fields.Many2one(
        'fleet.contract',
        string='Contract',
        ondelete='set null',
        index=True,
        tracking=True,
        help='Contract covering this service (if billed under a contract)'
    )

    notes = fields.Text(
        string='Notes',
        help='Additional notes about this service'
    )

    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company this service belongs to'
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the service'
    )

    _sql_constraints = [
        ('service_odometer_positive', 'CHECK(odometer >= 0)', 'Odometer reading must be positive!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Assign the service reference from the sequence"""
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.service') or 'New'
        return super().create(vals_list)

    @api.constrains('contract_id', 'vehicle_id')
    def _check_contract_vehicle(self):
        """A service under a running contract should be for the contract's vehicle"""
        for service in self:
            if service.contract_id and service.vehicle_id and \
                    service.contract_id.vehicle_id != service.vehicle_id:
                raise ValidationError(_(
                    'The contract %s is for vehicle %s, not for vehicle %s.'
                ) % (service.contract_id.name,
                     service.contract_id.vehicle_id.name,
                     service.vehicle_id.name))
