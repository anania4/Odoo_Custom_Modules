# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetTrip(models.Model):
    _name = 'fleet.trip'
    _description = 'Fleet Trip'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True,
        help='Trip reference'
    )
    
    # Vehicle & Driver
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Vehicle used for this trip'
    )
    
    driver_id = fields.Many2one(
        'fleet.driver',
        string='Driver',
        required=True,
        tracking=True,
        help='Driver who made this trip'
    )
    
    # Date & Time
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Trip date'
    )
    
    start_time = fields.Datetime(
        string='Start Time',
        tracking=True,
        help='Trip start time'
    )
    
    end_time = fields.Datetime(
        string='End Time',
        tracking=True,
        help='Trip end time'
    )
    
    duration_hours = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration_hours',
        store=True,
        digits=(10, 2),
        help='Trip duration in hours'
    )
    
    # Locations
    departure_location = fields.Char(
        string='Departure Location',
        required=True,
        help='Starting point of the trip'
    )
    
    destination = fields.Char(
        string='Destination',
        required=True,
        help='End point of the trip'
    )
    
    waypoints = fields.Text(
        string='Waypoints',
        help='Intermediate stops or route notes'
    )
    
    # Distance & Odometer
    start_odometer = fields.Float(
        string='Start Odometer (km)',
        required=True,
        tracking=True,
        help='Odometer reading at trip start'
    )
    
    end_odometer = fields.Float(
        string='End Odometer (km)',
        tracking=True,
        help='Odometer reading at trip end'
    )
    
    distance = fields.Float(
        string='Distance (km)',
        compute='_compute_distance',
        store=True,
        digits=(10, 2),
        help='Trip distance calculated from odometer readings'
    )
    
    average_speed = fields.Float(
        string='Average Speed (km/h)',
        compute='_compute_average_speed',
        store=True,
        digits=(10, 2),
        help='Average speed during trip'
    )
    
    # Purpose & Notes
    purpose = fields.Selection(
        [
            ('business', 'Business'),
            ('personal', 'Personal'),
            ('delivery', 'Delivery'),
            ('service', 'Service Call'),
            ('rental', 'Rental'),
            ('other', 'Other'),
        ],
        string='Purpose',
        default='business',
        required=True,
        tracking=True,
        help='Purpose of the trip'
    )
    
    purpose_description = fields.Char(
        string='Purpose Description',
        help='Detailed purpose description'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this trip'
    )
    
    # Documents
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_trip_attachment_rel',
        'trip_id',
        'attachment_id',
        string='Attachments',
        help='Trip-related documents'
    )
    
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count',
        store=False,
        help='Number of attachments'
    )
    
    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company this trip belongs to'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the trip'
    )
    
    # SQL Constraints
    _sql_constraints = [
        ('start_odometer_positive', 'CHECK(start_odometer >= 0)', 'Start odometer must be positive!'),
        ('end_odometer_positive', 'CHECK(end_odometer >= 0)', 'End odometer must be positive!'),
    ]
    
    # Compute Methods
    @api.depends('vehicle_id', 'departure_location', 'destination', 'date')
    def _compute_name(self):
        """Generate reference name"""
        for record in self:
            if record.vehicle_id:
                name = f"{record.vehicle_id.license_plate} - {record.departure_location or 'N/A'} to {record.destination or 'N/A'}"
                if record.date:
                    name += f" ({record.date})"
                record.name = name
            else:
                record.name = f"Trip {record.id or 'New'}"
    
    @api.depends('start_time', 'end_time')
    def _compute_duration_hours(self):
        """Calculate trip duration in hours"""
        for record in self:
            if record.start_time and record.end_time:
                delta = record.end_time - record.start_time
                record.duration_hours = delta.total_seconds() / 3600.0  # Convert to hours
            else:
                record.duration_hours = 0.0
    
    @api.depends('start_odometer', 'end_odometer')
    def _compute_distance(self):
        """Calculate distance from odometer readings"""
        for record in self:
            if record.end_odometer and record.start_odometer:
                record.distance = record.end_odometer - record.start_odometer
            else:
                record.distance = 0.0
    
    @api.depends('distance', 'duration_hours')
    def _compute_average_speed(self):
        """Calculate average speed"""
        for record in self:
            if record.duration_hours > 0 and record.distance > 0:
                record.average_speed = record.distance / record.duration_hours
            else:
                record.average_speed = 0.0
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Count attachments"""
        for record in self:
            record.attachment_count = len(record.attachment_ids)
    
    # Constraints
    @api.constrains('start_odometer', 'end_odometer')
    def _check_odometer(self):
        """Validate odometer readings"""
        for record in self:
            if record.start_odometer < 0:
                raise ValidationError(_('Start odometer cannot be negative!'))
            if record.end_odometer and record.end_odometer < record.start_odometer:
                raise ValidationError(_('End odometer cannot be less than start odometer!'))
    
    @api.constrains('start_time', 'end_time')
    def _check_times(self):
        """Validate trip times"""
        for record in self:
            if record.start_time and record.end_time and record.end_time < record.start_time:
                raise ValidationError(_('End time cannot be before start time!'))
    
    # Onchange Methods
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Set start odometer from vehicle"""
        if self.vehicle_id:
            self.start_odometer = self.vehicle_id.odometer
    
    @api.onchange('end_odometer')
    def _onchange_end_odometer(self):
        """Update vehicle odometer when trip ends"""
        if self.end_odometer and self.vehicle_id and self.end_odometer > self.vehicle_id.odometer:
            # Note: We don't actually update here, just inform the user
            # The actual update happens on save
            pass
    
    # Business Logic
    def write(self, vals):
        """Update vehicle odometer if end_odometer is set"""
        res = super().write(vals)
        for record in self:
            if record.end_odometer and record.vehicle_id and record.end_odometer > record.vehicle_id.odometer:
                record.vehicle_id.odometer = record.end_odometer
                record.vehicle_id.odometer_date = record.date
        return res
    
    @api.model_create_multi
    def create(self, vals_list):
        """Update vehicle odometer on creation"""
        records = super().create(vals_list)
        for record in records:
            if record.end_odometer and record.vehicle_id and record.end_odometer > record.vehicle_id.odometer:
                record.vehicle_id.odometer = record.end_odometer
                record.vehicle_id.odometer_date = record.date
        return records

