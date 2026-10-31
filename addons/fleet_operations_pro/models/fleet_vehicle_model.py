# -*- coding: utf-8 -*-

from random import randint

from odoo import models, fields


class FleetVehicleModel(models.Model):
    _name = 'fleet.vehicle.model'
    _description = 'Vehicle Model'
    _order = 'brand, name'

    name = fields.Char(string='Model Name', required=True)
    brand = fields.Char(string='Brand/Make')
    active = fields.Boolean(string='Active', default=True)
    vehicle_ids = fields.One2many('fleet.vehicle', 'model_id', string='Vehicles')

    _sql_constraints = [
        ('name_brand_unique', 'unique(name, brand)', 'This vehicle model already exists!'),
    ]


class FleetVehicleTag(models.Model):
    _name = 'fleet.vehicle.tag'
    _description = 'Vehicle Tag'
    _order = 'name'

    def _default_color(self):
        return randint(1, 11)

    name = fields.Char(string='Tag Name', required=True, translate=True)
    color = fields.Integer(string='Color', default=_default_color)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'Tag name already exists!'),
    ]
