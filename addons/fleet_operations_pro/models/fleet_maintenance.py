# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetMaintenance(models.Model):
    _name = 'fleet.maintenance'
    _description = 'Fleet Maintenance'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        compute='_compute_name',
        store=True
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Vehicle being maintained'
    )
    
    maintenance_type_id = fields.Many2one(
        'fleet.maintenance.type',
        string='Maintenance Type',
        required=True,
        tracking=True,
        help='Type of maintenance performed'
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date of maintenance'
    )
    
    # Service Details
    description = fields.Text(
        string='Description',
        required=True,
        help='Detailed description of the maintenance work'
    )
    
    odometer = fields.Float(
        string='Odometer (km)',
        required=True,
        tracking=True,
        help='Vehicle odometer reading at time of maintenance'
    )
    
    # Service Provider
    service_provider = fields.Char(
        string='Service Provider',
        help='Name of the service provider/vendor'
    )
    
    service_provider_partner_id = fields.Many2one(
        'res.partner',
        string='Service Provider Contact',
        help='Link to partner/vendor record'
    )
    
    service_location = fields.Char(
        string='Service Location',
        help='Address where service was performed'
    )
    
    invoice_reference = fields.Char(
        string='Invoice Reference',
        help='Invoice or receipt number'
    )
    
    # Status
    state = fields.Selection(
        [
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='scheduled',
        required=True,
        tracking=True,
        readonly=True,
        help='Status of the maintenance'
    )
    
    # Completion
    completion_date = fields.Date(
        string='Completion Date',
        help='Date when maintenance was completed'
    )
    
    # Warranty
    under_warranty = fields.Boolean(
        string='Under Warranty',
        default=False,
        help='Whether this maintenance was covered under warranty'
    )
    
    warranty_details = fields.Text(
        string='Warranty Details',
        help='Details about warranty coverage'
    )
    
    # Parts Used (simple text for Phase 1, will be enhanced with inventory in Phase 4)
    parts_used = fields.Text(
        string='Parts Used',
        help='List of parts used during maintenance'
    )
    
    # Company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='vehicle_id.company_id',
        store=True,
        readonly=True
    )
    
    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional notes about the maintenance'
    )
    
    _sql_constraints = [
        ('odometer_positive', 'CHECK(odometer >= 0)', 'Odometer must be positive!'),
    ]
    
    @api.depends('vehicle_id', 'maintenance_type_id', 'date')
    def _compute_name(self):
        """Generate maintenance reference"""
        for maintenance in self:
            if maintenance.vehicle_id and maintenance.maintenance_type_id and maintenance.date:
                maintenance.name = f"{maintenance.vehicle_id.license_plate} - {maintenance.maintenance_type_id.name} - {maintenance.date}"
            else:
                maintenance.name = 'New Maintenance'
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Set odometer from vehicle when vehicle is selected"""
        if self.vehicle_id:
            self.odometer = self.vehicle_id.odometer
    
    @api.onchange('service_provider_partner_id')
    def _onchange_service_provider_partner(self):
        """Auto-fill service provider name from partner"""
        if self.service_provider_partner_id:
            self.service_provider = self.service_provider_partner_id.name
            if self.service_provider_partner_id.street:
                self.service_location = self.service_provider_partner_id.contact_address
    
    @api.constrains('odometer', 'vehicle_id')
    def _check_odometer(self):
        """Validate odometer reading"""
        for maintenance in self:
            if maintenance.vehicle_id and maintenance.odometer:
                # Allow historical entries
                if maintenance.vehicle_id.odometer and maintenance.odometer < maintenance.vehicle_id.odometer:
                    if maintenance.date >= fields.Date.today():
                        raise ValidationError(_(
                            'Odometer reading (%s km) cannot be less than vehicle\'s current odometer (%s km)'
                        ) % (maintenance.odometer, maintenance.vehicle_id.odometer))
    
    @api.constrains('date', 'completion_date')
    def _check_dates(self):
        """Validate dates"""
        for maintenance in self:
            if maintenance.completion_date and maintenance.date:
                if maintenance.completion_date < maintenance.date:
                    raise ValidationError(_('Completion date cannot be before maintenance date'))
    
    @api.constrains('state')
    def _constrains_state(self):
        """Allow normal state transitions via business methods"""
        return
    
    @api.model_create_multi
    def create(self, vals_list):
        """Update vehicle odometer and status after creating maintenance"""
        maintenances = super().create(vals_list)
        for maintenance in maintenances:
            if maintenance.vehicle_id:
                # Update vehicle's odometer if this maintenance has a later date
                if not maintenance.vehicle_id.odometer_date or maintenance.date >= maintenance.vehicle_id.odometer_date:
                    maintenance.vehicle_id.write({
                        'odometer': maintenance.odometer,
                        'odometer_date': maintenance.date,
                    })
                
                # Update vehicle status to "In Maintenance" if maintenance is in progress
                if maintenance.state == 'in_progress':
                    maintenance.vehicle_id._set_status_code('in_maintenance')
        return maintenances
    
    def write(self, vals):
        """Update vehicle status based on maintenance status"""
        result = super().write(vals)
        
        if 'state' in vals:
            for maintenance in self:
                if vals['state'] == 'in_progress':
                    # Set vehicle to "In Maintenance"
                    maintenance.vehicle_id._set_status_code('in_maintenance')
                elif vals['state'] == 'completed':
                    # Set vehicle back to "Available" if it was in maintenance
                    if maintenance.vehicle_id.status_code == 'in_maintenance':
                        maintenance.vehicle_id._set_status_code('available')
                    # Set completion date if not set
                    if not maintenance.completion_date:
                        maintenance.write({'completion_date': fields.Date.today()})
        
        # Update odometer if changed
        if 'odometer' in vals or 'date' in vals:
            for maintenance in self:
                if not maintenance.vehicle_id.odometer_date or maintenance.date >= maintenance.vehicle_id.odometer_date:
                    maintenance.vehicle_id.write({
                        'odometer': maintenance.odometer,
                        'odometer_date': maintenance.date,
                    })
        
        return result
    
    def action_start_maintenance(self):
        """Action to start maintenance"""
        self.ensure_one()
        if self.state != 'scheduled':
            raise ValidationError(_('Only scheduled maintenance can be started!'))
        self.write({'state': 'in_progress'})
        return True
    
    def action_complete_maintenance(self):
        """Action to complete maintenance"""
        self.ensure_one()
        if self.state not in ['scheduled', 'in_progress']:
            raise ValidationError(_('Only scheduled or in-progress maintenance can be completed!'))
        
        self.write({
            'state': 'completed',
            'completion_date': fields.Date.today(),
        })
        return True
    
    def action_cancel_maintenance(self):
        """Action to cancel maintenance"""
        self.ensure_one()
        if self.state == 'completed':
            raise ValidationError(_('Cannot cancel completed maintenance!'))
        
        self.write({'state': 'cancelled'})
        # Set vehicle back to available if it was in maintenance
        if self.vehicle_id.status_code == 'in_maintenance':
            self.vehicle_id._set_status_code('available')
        return True

