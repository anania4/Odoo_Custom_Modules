# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetFuelLogWizard(models.TransientModel):
    _name = 'fleet.fuel.log.wizard'
    _description = 'Add Fuel Log Wizard'
    
    # Source context
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        help='Vehicle for which fuel is being added'
    )
    
    rental_contract_id = fields.Many2one(
        'fleet.rental.contract',
        string='Rental Contract',
        help='Rental contract this fuel log belongs to (filled automatically when opened from a contract)'
    )
    
    driver_id = fields.Many2one(
        'fleet.driver',
        string='Driver',
        help='Driver who filled the fuel'
    )
    
    # Fuel Details
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        help='Date of fueling'
    )
    
    quantity = fields.Float(
        string='Quantity (L)',
        required=True,
        digits=(10, 2),
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
        compute='_compute_total_cost',
        store=True,
        readonly=False,
        help='Total cost of fuel'
    )
    
    # Odometer
    odometer = fields.Float(
        string='Odometer (km)',
        required=True,
        help='Vehicle odometer reading at time of fueling'
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
    
    # Additional Info
    notes = fields.Text(
        string='Notes',
        help='Additional notes about this fueling'
    )
    
    attachment = fields.Binary(
        string='Receipt',
        help='Fuel receipt attachment'
    )
    
    attachment_name = fields.Char(
        string='Attachment Name'
    )
    
    # Currency
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        compute='_compute_currency',
        store=True,
        help='Company currency'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company
    )
    
    # Display Fields
    current_fuel_level = fields.Float(
        string='Current Fuel Level',
        related='vehicle_id.current_fuel_level',
        readonly=True,
        help='Current fuel level in vehicle'
    )
    
    fuel_tank_capacity = fields.Float(
        string='Tank Capacity',
        related='vehicle_id.fuel_tank_capacity',
        readonly=True,
        help='Vehicle fuel tank capacity'
    )
    
    fuel_percentage = fields.Float(
        string='Current Fuel %',
        related='vehicle_id.fuel_percentage',
        readonly=True,
        help='Current fuel level percentage'
    )
    
    new_fuel_level = fields.Float(
        string='New Fuel Level (L)',
        compute='_compute_new_fuel_level',
        help='Fuel level after adding fuel'
    )
    
    new_fuel_percentage = fields.Float(
        string='New Fuel %',
        compute='_compute_new_fuel_percentage',
        help='Fuel percentage after adding fuel'
    )
    
    # Compute Methods
    @api.depends('company_id')
    def _compute_currency(self):
        for wizard in self:
            wizard.currency_id = wizard.company_id.currency_id
    
    @api.depends('quantity', 'price_per_unit')
    def _compute_total_cost(self):
        for wizard in self:
            if wizard.quantity and wizard.price_per_unit:
                wizard.total_cost = wizard.quantity * wizard.price_per_unit
            elif not wizard.total_cost:
                wizard.total_cost = 0.0
    
    @api.depends('current_fuel_level', 'quantity')
    def _compute_new_fuel_level(self):
        for wizard in self:
            wizard.new_fuel_level = wizard.current_fuel_level + wizard.quantity
    
    @api.depends('new_fuel_level', 'fuel_tank_capacity')
    def _compute_new_fuel_percentage(self):
        for wizard in self:
            if wizard.fuel_tank_capacity > 0:
                wizard.new_fuel_percentage = (wizard.new_fuel_level / wizard.fuel_tank_capacity) * 100
            else:
                wizard.new_fuel_percentage = 0.0
    
    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        """Set odometer from vehicle"""
        if self.vehicle_id:
            self.odometer = self.vehicle_id.odometer
    
    @api.onchange('quantity', 'current_fuel_level', 'fuel_tank_capacity')
    def _onchange_quantity(self):
        """Warn if fuel exceeds tank capacity"""
        if self.quantity and self.current_fuel_level and self.fuel_tank_capacity:
            new_level = self.current_fuel_level + self.quantity
            if new_level > self.fuel_tank_capacity:
                return {
                    'warning': {
                        'title': _('Warning'),
                        'message': _('The fuel quantity will exceed the tank capacity! New level: %.2f L, Capacity: %.2f L') % (new_level, self.fuel_tank_capacity)
                    }
                }
    
    def action_add_fuel(self):
        """Create fuel log entry"""
        self.ensure_one()
        
        # Validation
        if self.quantity <= 0:
            raise ValidationError(_('Fuel quantity must be positive!'))
        
        if self.total_cost < 0:
            raise ValidationError(_('Total cost cannot be negative!'))
        
        # Create fuel log
        fuel_log = self.env['fleet.fuel.log'].create({
            'vehicle_id': self.vehicle_id.id,
            'driver_id': self.driver_id.id if self.driver_id else False,
            'date': self.date,
            'quantity': self.quantity,
            'price_per_unit': self.price_per_unit if self.price_per_unit else 0.0,
            'total_cost': self.total_cost,
            'odometer': self.odometer,
            'fuel_station': self.fuel_station,
            'fuel_station_location': self.fuel_station_location,
            'rental_contract_id': self.rental_contract_id.id if self.rental_contract_id else False,
            'notes': self.notes,
            'attachment': self.attachment,
            'attachment_name': self.attachment_name,
        })
        
        # Update vehicle odometer
        if self.odometer > self.vehicle_id.odometer:
            self.vehicle_id.odometer = self.odometer
            self.vehicle_id.odometer_date = self.date
        
        # Return action to view the created fuel log
        return {
            'type': 'ir.actions.act_window',
            'name': _('Fuel Log'),
            'res_model': 'fleet.fuel.log',
            'res_id': fuel_log.id,
            'view_mode': 'form',
            'target': 'current',
        }

