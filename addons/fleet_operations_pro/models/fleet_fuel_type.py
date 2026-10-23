# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FleetFuelType(models.Model):
    _name = 'fleet.fuel.type'
    _description = 'Fuel Type'
    _order = 'sequence, name'

    name = fields.Char(string='Fuel Type', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description', translate=True)
    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Fuel type code must be unique!'),
    ]

