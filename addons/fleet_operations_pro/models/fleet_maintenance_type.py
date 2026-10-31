# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FleetMaintenanceType(models.Model):
    _name = 'fleet.maintenance.type'
    _description = 'Maintenance Type'
    _order = 'sequence, name'

    name = fields.Char(
        string='Service Type',
        required=True,
        translate=True,
        help='Type of service / maintenance'
    )
    code = fields.Char(
        string='Code',
        help='Optional internal code'
    )
    sequence = fields.Integer(
        string='Sequence',
        default=10
    )
    description = fields.Text(
        string='Description',
        translate=True,
        help='Description of this maintenance type'
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Maintenance type code must be unique!'),
    ]

