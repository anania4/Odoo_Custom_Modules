# -*- coding: utf-8 -*-

from odoo import models, fields, api


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
    
    _sql_constraints = [
        ('code_unique', 'unique(code)', 'Status code must be unique!'),
    ]

