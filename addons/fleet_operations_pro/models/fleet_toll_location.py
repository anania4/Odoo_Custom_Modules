# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class FleetTollLocation(models.Model):
    _name = 'fleet.toll.location'
    _description = 'Fleet Toll Location'
    _order = 'name'
    
    name = fields.Char(
        string='Location Name',
        required=True,
        help='Name of the toll location'
    )
    
    code = fields.Char(
        string='Code',
        help='Short code for the toll location'
    )
    
    address = fields.Text(
        string='Address',
        help='Full address of the toll location'
    )
    
    city = fields.Char(
        string='City',
        help='City where the toll is located'
    )
    
    state = fields.Char(
        string='State/Province',
        help='State or province'
    )
    
    country_id = fields.Many2one(
        'res.country',
        string='Country',
        help='Country where the toll is located'
    )
    
    description = fields.Text(
        string='Description',
        help='Additional information about this toll location'
    )
    
    # Stats
    toll_count = fields.Integer(
        string='Toll Records',
        compute='_compute_toll_count',
        store=False,
        help='Number of toll records at this location'
    )
    
    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        help='Company this toll location belongs to'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the toll location'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Display order'
    )
    
    # SQL Constraints
    _sql_constraints = [
        ('name_unique', 'unique(name, company_id)', 'Toll location name must be unique per company!'),
    ]
    
    @api.depends('name')
    def _compute_toll_count(self):
        """Count toll records at this location"""
        for location in self:
            location.toll_count = self.env['fleet.toll.record'].search_count([
                ('toll_location_id', '=', location.id)
            ])
    
    def name_get(self):
        """Custom name display"""
        result = []
        for location in self:
            if location.city:
                name = f"{location.name} ({location.city})"
            else:
                name = location.name
            result.append((location.id, name))
        return result

