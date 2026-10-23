# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FleetCostCategory(models.Model):
    """
    Model for categorizing fleet costs.
    Categories include Fuel, Maintenance, Insurance, Tax, etc.
    """
    _name = 'fleet.cost.category'
    _description = 'Fleet Cost Category'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Category Name',
        required=True,
        translate=True,
        help='Name of the cost category (e.g., Fuel, Maintenance, Insurance)'
    )
    
    code = fields.Char(
        string='Category Code',
        required=True,
        help='Short code for the category'
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of this cost category'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of display in lists'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to hide this category without deleting it'
    )
    
    auto_generated = fields.Boolean(
        string='Auto Generated',
        default=False,
        help='True if costs in this category are automatically generated from other records'
    )
    
    color = fields.Integer(
        string='Color Index',
        help='Color for display in charts and graphs'
    )
    
    # Statistics
    cost_record_count = fields.Integer(
        string='Cost Records',
        compute='_compute_cost_record_count'
    )
    
    @api.depends('name')
    def _compute_cost_record_count(self):
        """Count cost records per category"""
        for record in self:
            record.cost_record_count = self.env['fleet.cost.record'].search_count([
                ('category_id', '=', record.id)
            ])
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Category code must be unique!'),
        ('name_unique', 'UNIQUE(name)', 'Category name must be unique!'),
    ]

