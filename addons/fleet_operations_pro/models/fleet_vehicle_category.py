# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FleetVehicleCategory(models.Model):
    _name = 'fleet.vehicle.category'
    _description = 'Vehicle Category'
    _order = 'sequence, name'

    name = fields.Char(string='Category Name', required=True, translate=True)
    code = fields.Char(string='Code', required=True)
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description', translate=True)
    active = fields.Boolean(string='Active', default=True)
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Category code must be unique!'),
    ]

