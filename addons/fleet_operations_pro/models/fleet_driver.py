# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class FleetDriver(models.Model):
    _name = 'fleet.driver'
    _description = 'Fleet Driver'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    # Basic Information
    image = fields.Image(
        string='Driver Photo',
        max_width=1024,
        max_height=1024,
        help='Driver photo'
    )
    name = fields.Char(
        string='Driver Name',
        required=True,
        tracking=True,
        help='Full name of the driver'
    )
    code = fields.Char(
        string='Driver Code',
        help='Internal reference code for the driver'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Uncheck to archive the driver'
    )
    
    # Contact Information
    email = fields.Char(
        string='Email',
        tracking=True
    )
    phone = fields.Char(
        string='Phone',
        tracking=True
    )
    mobile = fields.Char(
        string='Mobile',
        tracking=True
    )
    address = fields.Text(
        string='Address',
        help='Residential address'
    )
    
    # Partner Link (for standalone module, we don't link to HR employee)
    partner_id = fields.Many2one(
        'res.partner',
        string='Related Contact',
        help='Link to contact/partner record if needed'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Related User',
        help='Link driver to Odoo user for portal/app access and security rules'
    )
    
    # License Information
    license_number = fields.Char(
        string='License Number',
        tracking=True,
        help='Driver\'s license number'
    )
    license_type = fields.Selection(
        [
            ('light', 'Light Vehicle'),
            ('heavy', 'Heavy Vehicle'),
            ('commercial', 'Commercial'),
            ('motorcycle', 'Motorcycle'),
            ('special', 'Special Equipment'),
        ],
        string='License Type',
        tracking=True,
        help='Type of driving license'
    )
    license_issue_date = fields.Date(
        string='License Issue Date',
        tracking=True
    )
    license_expiry_date = fields.Date(
        string='License Expiry Date',
        tracking=True,
        help='Date when the license expires'
    )
    license_status = fields.Selection(
        [
            ('valid', 'Valid'),
            ('expiring_soon', 'Expiring Soon'),
            ('expired', 'Expired'),
            ('suspended', 'Suspended'),
        ],
        string='License Status',
        compute='_compute_license_status',
        store=True,
        help='Current status of the driver\'s license'
    )
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_license_status',
        store=True,
        help='Number of days until license expires'
    )
    
    # Employment Information
    date_hired = fields.Date(
        string='Hire Date',
        tracking=True
    )
    date_terminated = fields.Date(
        string='Termination Date',
        tracking=True
    )
    employment_status = fields.Selection(
        [
            ('active', 'Active'),
            ('on_leave', 'On Leave'),
            ('terminated', 'Terminated'),
        ],
        string='Employment Status',
        default='active',
        tracking=True
    )
    
    # Driver Statistics & Performance
    total_trips = fields.Integer(
        string='Total Trips',
        compute='_compute_driver_stats',
        store=False,
        help='Total number of trips'
    )
    total_distance = fields.Float(
        string='Total Distance (km)',
        compute='_compute_driver_stats',
        store=False,
        help='Total distance driven in kilometers'
    )
    
    # Relational Fields
    assignment_ids = fields.One2many(
        'fleet.driver.assignment',
        'driver_id',
        string='Vehicle Assignments',
        help='History of vehicle assignments'
    )
    current_assignment_id = fields.Many2one(
        'fleet.driver.assignment',
        string='Current Assignment',
        compute='_compute_current_assignment',
        store=False,
        help='Current active vehicle assignment'
    )
    current_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Current Vehicle',
        compute='_compute_current_assignment',
        store=False,
        help='Currently assigned vehicle'
    )
    
    # Assignments (Phase 1B)
    assignment_ids = fields.One2many(
        'fleet.driver.assignment',
        'driver_id',
        string='Vehicle Assignments',
        help='History of vehicle assignments for this driver'
    )
    assignment_count = fields.Integer(
        string='Assignments',
        compute='_compute_assignment_count',
        store=False,
        help='Number of vehicle assignments'
    )
    current_vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Current Vehicle',
        compute='_compute_current_vehicle',
        store=False,
        help='Currently assigned vehicle (if any)'
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional information about the driver'
    )
    
    _sql_constraints = [
        ('license_number_unique', 'unique(license_number, company_id)', 
         'License number must be unique per company!'),
    ]
    
    @api.depends('license_expiry_date')
    def _compute_license_status(self):
        """Compute license status based on expiry date"""
        today = fields.Date.today()
        for driver in self:
            if not driver.license_expiry_date:
                driver.license_status = 'valid'
                driver.days_until_expiry = 0
            else:
                days_diff = (driver.license_expiry_date - today).days
                driver.days_until_expiry = days_diff
                
                if days_diff < 0:
                    driver.license_status = 'expired'
                elif days_diff <= 30:
                    driver.license_status = 'expiring_soon'
                else:
                    driver.license_status = 'valid'
    
    def _compute_current_assignment(self):
        """Get current active vehicle assignment"""
        for driver in self:
            current = self.env['fleet.driver.assignment'].search([
                ('driver_id', '=', driver.id),
                ('date_start', '<=', fields.Date.today()),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', fields.Date.today()),
            ], limit=1, order='date_start desc')
            
            driver.current_assignment_id = current.id if current else False
            driver.current_vehicle_id = current.vehicle_id.id if current else False
    
    def _compute_driver_stats(self):
        """Compute driver statistics - will be implemented with trip logs in Phase 2D"""
        for driver in self:
            driver.total_trips = 0
            driver.total_distance = 0.0
    
    @api.depends('assignment_ids')
    def _compute_assignment_count(self):
        """Count vehicle assignments"""
        for driver in self:
            driver.assignment_count = len(driver.assignment_ids)
    
    @api.depends('assignment_ids.is_active', 'assignment_ids.vehicle_id')
    def _compute_current_vehicle(self):
        """Get currently assigned vehicle"""
        for driver in self:
            active_assignment = driver.assignment_ids.filtered(lambda a: a.is_active)
            driver.current_vehicle_id = active_assignment[0].vehicle_id if active_assignment else False
    
    @api.constrains('license_expiry_date', 'license_issue_date')
    def _check_license_dates(self):
        """Validate license dates"""
        for driver in self:
            if driver.license_issue_date and driver.license_expiry_date:
                if driver.license_expiry_date < driver.license_issue_date:
                    raise ValidationError(_('License expiry date cannot be before issue date'))
    
    @api.constrains('date_hired', 'date_terminated')
    def _check_employment_dates(self):
        """Validate employment dates"""
        for driver in self:
            if driver.date_hired and driver.date_terminated:
                if driver.date_terminated < driver.date_hired:
                    raise ValidationError(_('Termination date cannot be before hire date'))
    
    @api.model
    def _cron_check_license_expiry(self):
        """Scheduled action to check license expiry and create activities"""
        today = fields.Date.today()
        reminder_days = [30, 60, 90]  # Days before expiry to create reminders
        
        for days in reminder_days:
            expiry_date = today + timedelta(days=days)
            drivers = self.search([
                ('active', '=', True),
                ('license_expiry_date', '=', expiry_date),
                ('license_status', '!=', 'expired'),
            ])
            
            for driver in drivers:
                # Check if activity already exists
                existing_activity = self.env['mail.activity'].search([
                    ('res_id', '=', driver.id),
                    ('res_model_id', '=', self.env.ref('fleet_operations_pro.model_fleet_driver').id),
                    ('summary', 'ilike', 'License Expiry'),
                ], limit=1)
                
                if not existing_activity:
                    driver.activity_schedule(
                        'mail.mail_activity_data_todo',
                        summary=_('Driver License Expiring Soon'),
                        note=_(f'Driver {driver.name}\'s license will expire in {days} days on {driver.license_expiry_date}'),
                        date_deadline=expiry_date,
                    )
    
    def action_assign_vehicle(self):
        """Action to assign a vehicle to driver"""
        self.ensure_one()
        return {
            'name': _('Assign Vehicle'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.driver.assignment',
            'view_mode': 'form',
            'target': 'new',
            'context': {'default_driver_id': self.id},
        }
    
    def name_get(self):
        """Custom name display"""
        result = []
        for driver in self:
            if driver.code:
                name = f"[{driver.code}] {driver.name}"
            else:
                name = driver.name
            result.append((driver.id, name))
        return result

