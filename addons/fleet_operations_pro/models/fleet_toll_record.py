# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetTollRecord(models.Model):
    _name = 'fleet.toll.record'
    _description = 'Fleet Toll Record'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
        help='Toll record reference'
    )
    
    # Vehicle & Driver
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Vehicle that passed through toll'
    )
    
    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver',
        tracking=True,
        help='Driver (employee) who paid the toll'
    )
    
    # Date & Location
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date when toll was paid'
    )
    
    # Odometer
    odometer = fields.Float(
        string='Odometer (km)',
        tracking=True,
        help='Vehicle odometer reading at time of toll'
    )
    
    # Receipt & Notes
    receipt = fields.Binary(
        string='Receipt',
        attachment=True,
        help='Toll receipt attachment'
    )
    

    receipt_name = fields.Char(
        string='Receipt Filename'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this toll'
    )
    
    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company this toll belongs to'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the toll record'
    )
    
    # SQL Constraints
    _sql_constraints = [
        ('odometer_positive', 'CHECK(odometer >= 0)', 'Odometer reading must be positive!'),
    ]
    
    # Compute Methods
    @api.depends('vehicle_id', 'vehicle_id.license_plate', 'date')
    def _compute_name(self):
        """Generate reference name"""
        for record in self:
            if record.vehicle_id:
                record.name = f"{record.vehicle_id.license_plate} ({record.date})"
            else:
                record.name = f"Toll Record {record.id or 'New'}"
    
    # Constraints
    @api.constrains('odometer')
    def _check_odometer(self):
        """Validate odometer"""
        for record in self:
            if record.odometer and record.odometer < 0:
                raise ValidationError(_('Odometer reading cannot be negative!'))
    
    # Onchange Methods
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Set odometer from vehicle"""
        if self.vehicle_id:
            self.odometer = self.vehicle_id.odometer

