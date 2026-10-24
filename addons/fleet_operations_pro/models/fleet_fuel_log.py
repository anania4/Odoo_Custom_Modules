# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetFuelLog(models.Model):
    _name = 'fleet.fuel.log'
    _description = 'Fleet Fuel Log'
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
        help='Vehicle for which fuel was filled'
    )
    
    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver',
        tracking=True,
        help='Driver (employee) who filled the fuel'
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date of fueling'
    )
    
    # Fuel Details
    quantity = fields.Float(
        string='Quantity (L)',
        required=True,
        digits=(10, 2),
        tracking=True,
        help='Quantity of fuel in liters'
    )
    
    price_per_unit = fields.Monetary(
        string='Price per Liter',
        currency_field='currency_id',
        help='Price per liter of fuel'
    )
    
    total_cost = fields.Monetary(
        string='Total Cost',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help='Total cost of fuel'
    )
    
    # Odometer
    odometer = fields.Float(
        string='Odometer (km)',
        required=True,
        tracking=True,
        help='Vehicle odometer reading at time of fueling'
    )
    
    odometer_difference = fields.Float(
        string='Distance Since Last Fill (km)',
        compute='_compute_odometer_difference',
        store=True,
        help='Distance traveled since last fuel entry'
    )
    
    # Fuel Efficiency
    fuel_efficiency = fields.Float(
        string='Fuel Efficiency (km/L)',
        compute='_compute_fuel_efficiency',
        store=True,
        digits=(10, 2),
        help='Kilometers per liter'
    )
    
    # Fuel Station
    fuel_station = fields.Char(
        string='Fuel Station',
        help='Name or location of fuel station'
    )
    
    fuel_station_location = fields.Char(
        string='Station Location',
        help='Address of fuel station'
    )
    
    # Invoice/Receipt
    invoice_reference = fields.Char(
        string='Invoice Reference',
        help='Invoice or receipt number'
    )
    
    attachment = fields.Binary(
        string='Receipt',
        help='Fuel receipt attachment'
    )
    
    attachment_name = fields.Char(
        string='Attachment Name'
    )
    
    # Vehicle Related Fields
    fuel_type_id = fields.Many2one(
        'fleet.fuel.type',
        string='Fuel Type',
        related='vehicle_id.fuel_type_id',
        store=True,
        readonly=True
    )
    
    # Financial
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id,
        required=True
    )
    
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
        help='Additional notes about this fuel entry'
    )
    
    _sql_constraints = [
        ('quantity_positive', 'CHECK(quantity > 0)', 'Fuel quantity must be positive!'),
        ('total_cost_positive', 'CHECK(total_cost >= 0)', 'Total cost must be positive!'),
        ('odometer_positive', 'CHECK(odometer >= 0)', 'Odometer must be positive!'),
    ]
    
    @api.depends('vehicle_id', 'date', 'quantity')
    def _compute_name(self):
        """Generate fuel log reference"""
        for log in self:
            if log.vehicle_id and log.date:
                log.name = f"{log.vehicle_id.license_plate} - {log.date} - {log.quantity}L"
            else:
                log.name = 'New Fuel Log'
    
    @api.depends('odometer')
    def _compute_odometer_difference(self):
        """Calculate distance since last fuel entry"""
        for log in self:
            previous_log = self.search([
                ('vehicle_id', '=', log.vehicle_id.id),
                ('date', '<', log.date),
                ('id', '!=', log.id),
            ], limit=1, order='date desc')
            
            if previous_log:
                log.odometer_difference = log.odometer - previous_log.odometer
            else:
                log.odometer_difference = 0.0
    
    @api.depends('odometer_difference', 'quantity')
    def _compute_fuel_efficiency(self):
        """Calculate fuel efficiency in km/L"""
        for log in self:
            if log.quantity > 0 and log.odometer_difference > 0:
                log.fuel_efficiency = log.odometer_difference / log.quantity
            else:
                log.fuel_efficiency = 0.0
    
    @api.onchange('quantity', 'price_per_unit')
    def _onchange_quantity_price(self):
        """Auto-calculate total cost when quantity or price changes"""
        if self.quantity and self.price_per_unit:
            self.total_cost = self.quantity * self.price_per_unit
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Set odometer from vehicle when vehicle is selected"""
        if self.vehicle_id:
            self.odometer = self.vehicle_id.odometer
            # Set current driver if available
            if self.vehicle_id.current_driver_id:
                self.driver_id = self.vehicle_id.current_driver_id
    
    @api.constrains('odometer', 'vehicle_id')
    def _check_odometer(self):
        """Validate odometer reading"""
        for log in self:
            if log.vehicle_id and log.odometer:
                # Check if odometer is less than vehicle's last known odometer
                if log.vehicle_id.odometer and log.odometer < log.vehicle_id.odometer:
                    # Allow if this is a historical entry
                    if log.date >= fields.Date.today():
                        raise ValidationError(_(
                            'Odometer reading (%s km) cannot be less than vehicle\'s current odometer (%s km)'
                        ) % (log.odometer, log.vehicle_id.odometer))
    
    @api.model_create_multi
    def create(self, vals_list):
        """Update vehicle odometer and fuel level after creating fuel log"""
        logs = super().create(vals_list)
        for log in logs:
            if log.vehicle_id:
                # Update vehicle's odometer if this log has a later date
                if not log.vehicle_id.odometer_date or log.date >= log.vehicle_id.odometer_date:
                    log.vehicle_id.write({
                        'odometer': log.odometer,
                        'odometer_date': log.date,
                    })
                # Trigger recomputation of vehicle's current fuel level
                log.vehicle_id._compute_current_fuel_level()
        return logs
    
    def write(self, vals):
        """Update vehicle odometer and fuel level after updating fuel log"""
        result = super().write(vals)
        if 'odometer' in vals or 'date' in vals or 'quantity' in vals:
            for log in self:
                if log.vehicle_id:
                    # Update vehicle's odometer if this log has the latest date
                    if not log.vehicle_id.odometer_date or log.date >= log.vehicle_id.odometer_date:
                        log.vehicle_id.write({
                            'odometer': log.odometer,
                            'odometer_date': log.date,
                        })
                    # Trigger recomputation of vehicle's current fuel level
                    log.vehicle_id._compute_current_fuel_level()
        return result
    
    def unlink(self):
        """Recompute vehicle fuel level after deleting fuel log"""
        vehicles = self.mapped('vehicle_id')
        result = super().unlink()
        for vehicle in vehicles:
            vehicle._compute_current_fuel_level()
        return result

