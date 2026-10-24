# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class FleetRentalContract(models.Model):
    _name = 'fleet.rental.contract'
    _description = 'Fleet Rental Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'
    _rec_name = 'name'

    # Basic Information
    name = fields.Char(
        string='Contract Number',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        help='Unique contract reference number'
    )
    
    # Customer Information
    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        required=True,
        tracking=True,
        domain=[('type', 'in', ['contact', 'invoice'])],
        help='Customer renting the vehicle(s)'
    )
    customer_phone = fields.Char(
        string='Phone',
        related='customer_id.phone',
        readonly=True,
        help='Customer phone number'
    )
    customer_email = fields.Char(
        string='Email',
        related='customer_id.email',
        readonly=True,
        help='Customer email address'
    )
    
    # Vehicle Information (Multi-vehicle support)
    vehicle_ids = fields.Many2many(
        'fleet.vehicle',
        'fleet_rental_vehicle_rel',
        'rental_id',
        'vehicle_id',
        string='Vehicles',
        required=True,
        tracking=True,
        help='Vehicles included in this rental contract'
    )
    vehicle_count = fields.Integer(
        string='Vehicle Count',
        compute='_compute_vehicle_count',
        store=True,
        help='Number of vehicles in this contract'
    )
    
    # Driver Information (optional)
    driver_id = fields.Many2one(
        'fleet.driver',
        string='Driver',
        tracking=True,
        help='Driver assigned to this rental (if applicable)'
    )
    
    # Date & Duration
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        help='Rental start date'
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        help='Rental end date'
    )
    duration_days = fields.Integer(
        string='Duration (Days)',
        compute='_compute_duration',
        store=True,
        help='Rental duration in days'
    )
    actual_return_date = fields.Date(
        string='Actual Return Date',
        tracking=True,
        help='Actual date when vehicles were returned'
    )
    
    # Pricing
    rental_rate_type = fields.Selection(
        [
            ('daily', 'Daily'),
            ('weekly', 'Weekly'),
            ('monthly', 'Monthly'),
        ],
        string='Rate Type',
        default='daily',
        required=True,
        help='Pricing model for this rental'
    )
    rental_rate = fields.Monetary(
        string='Rental Rate',
        required=True,
        currency_field='currency_id',
        help='Rental price per rate type (daily/weekly/monthly)'
    )
    total_rental_amount = fields.Monetary(
        string='Total Rental Amount',
        compute='_compute_total_rental_amount',
        store=True,
        currency_field='currency_id',
        help='Total rental cost calculated'
    )
    
    # Distance Charges
    allowed_kilometers = fields.Float(
        string='Allowed Kilometers',
        help='Maximum kilometers allowed without extra charge'
    )
    extra_km_rate = fields.Monetary(
        string='Extra KM Rate',
        currency_field='currency_id',
        help='Charge per kilometer over the allowed limit'
    )
    distance_charges = fields.Monetary(
        string='Distance Charges',
        compute='_compute_distance_charges',
        store=True,
        currency_field='currency_id',
        help='Extra charges for exceeding allowed kilometers'
    )
    
    # Additional Charges
    additional_charges = fields.Monetary(
        string='Additional Charges',
        currency_field='currency_id',
        tracking=True,
        help='Any additional charges (cleaning, damage, etc.)'
    )
    discount = fields.Monetary(
        string='Discount',
        currency_field='currency_id',
        tracking=True,
        help='Discount amount'
    )
    
    # Total Amount
    total_amount = fields.Monetary(
        string='Total Amount',
        compute='_compute_total_amount',
        store=True,
        currency_field='currency_id',
        help='Total amount including rental, fuel, tolls, distance charges, and additional charges'
    )
    
    # Deposit
    deposit_amount = fields.Monetary(
        string='Deposit Amount',
        currency_field='currency_id',
        tracking=True,
        help='Security deposit collected from customer'
    )
    deposit_returned = fields.Boolean(
        string='Deposit Returned',
        default=False,
        tracking=True,
        help='Check if deposit has been returned to customer'
    )
    deposit_return_date = fields.Date(
        string='Deposit Return Date',
        tracking=True,
        help='Date when deposit was returned'
    )
    deposit_return_amount = fields.Monetary(
        string='Deposit Return Amount',
        currency_field='currency_id',
        help='Amount of deposit returned (may differ due to deductions)'
    )
    
    # Locations
    pickup_location = fields.Char(
        string='Pickup Location',
        help='Where vehicles will be picked up'
    )
    return_location = fields.Char(
        string='Return Location',
        help='Where vehicles should be returned'
    )
    
    # Odometer Readings
    initial_odometer = fields.Float(
        string='Initial Odometer',
        help='Odometer reading at rental start'
    )
    final_odometer = fields.Float(
        string='Final Odometer',
        help='Odometer reading at rental end'
    )
    distance_traveled = fields.Float(
        string='Distance Traveled',
        compute='_compute_distance_traveled',
        store=True,
        help='Total distance traveled during rental'
    )
    
    # Fuel Management (Phase 2B)
    fuel_log_ids = fields.One2many(
        'fleet.fuel.log',
        'rental_contract_id',
        string='Fuel Logs',
        help='All fuel logs for this rental contract'
    )
    fuel_log_count = fields.Integer(
        string='Fuel Logs',
        compute='_compute_fuel_log_count',
        store=False,
        help='Number of fuel logs'
    )
    initial_fuel_level = fields.Float(
        string='Initial Fuel Level (L)',
        help='Fuel level at rental start'
    )
    final_fuel_level = fields.Float(
        string='Final Fuel Level (L)',
        help='Fuel level at rental end'
    )
    initial_fuel_percentage = fields.Float(
        string='Initial Fuel %',
        compute='_compute_initial_fuel_percentage',
        store=False,
        help='Initial fuel level as percentage'
    )
    final_fuel_percentage = fields.Float(
        string='Final Fuel %',
        compute='_compute_final_fuel_percentage',
        store=False,
        help='Final fuel level as percentage'
    )
    fuel_recharge_policy = fields.Selection(
        [
            ('none', 'No Recharge Required'),
            ('full', 'Full Tank'),
            ('percentage', 'Same Percentage as Start'),
        ],
        string='Fuel Recharge Policy',
        default='full',
        required=True,
        help='Fuel recharge policy for this rental'
    )
    fuel_consumed = fields.Float(
        string='Fuel Consumed (L)',
        compute='_compute_fuel_consumed',
        store=False,
        help='Total fuel consumed during rental'
    )
    fuel_cost_to_charge = fields.Monetary(
        string='Fuel Cost to Charge',
        compute='_compute_fuel_cost_to_charge',
        store=False,
        currency_field='currency_id',
        help='Fuel cost to be charged to customer based on policy'
    )
    
    # Toll Management (Phase 2C)
    toll_record_ids = fields.One2many(
        'fleet.toll.record',
        'rental_contract_id',
        string='Toll Records',
        help='All toll records for this rental contract'
    )
    toll_count = fields.Integer(
        string='Tolls',
        compute='_compute_toll_count',
        store=False,
        help='Number of toll records'
    )
    total_toll_cost = fields.Monetary(
        string='Total Toll Cost',
        compute='_compute_total_toll_cost',
        store=False,
        currency_field='currency_id',
        help='Total toll expenses during rental'
    )
    
    # Trip Management (Phase 2D)
    trip_ids = fields.One2many(
        'fleet.trip',
        'rental_contract_id',
        string='Trips',
        help='All trips during this rental'
    )
    trip_count = fields.Integer(
        string='Trips',
        compute='_compute_trip_count',
        store=False,
        help='Number of trips'
    )
    total_trip_distance = fields.Float(
        string='Total Trip Distance',
        compute='_compute_total_trip_distance',
        store=False,
        help='Total distance from all trips'
    )
    
    # Status & State
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('confirmed', 'Confirmed'),
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        readonly=True,
        help='Contract status'
    )
    
    # Additional Information
    notes = fields.Text(
        string='Notes',
        help='Additional notes or special instructions'
    )
    terms_conditions = fields.Text(
        string='Terms & Conditions',
        help='Rental terms and conditions'
    )
    
    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company this contract belongs to'
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        readonly=True,
        help='Company currency'
    )
    
    # Active flag
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the contract'
    )
    
    # SQL Constraints
    _sql_constraints = [
        ('check_dates', 'CHECK(end_date >= start_date)', 'End date must be after start date!'),
        ('check_deposit', 'CHECK(deposit_amount >= 0)', 'Deposit amount must be positive!'),
        ('check_rental_rate', 'CHECK(rental_rate >= 0)', 'Rental rate must be positive!'),
    ]
    
    # Compute Methods
    @api.depends('vehicle_ids')
    def _compute_vehicle_count(self):
        for record in self:
            record.vehicle_count = len(record.vehicle_ids)
    
    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for record in self:
            if record.start_date and record.end_date:
                delta = record.end_date - record.start_date
                record.duration_days = delta.days + 1  # Include both start and end days
            else:
                record.duration_days = 0
    
    @api.depends('rental_rate', 'rental_rate_type', 'duration_days', 'vehicle_count')
    def _compute_total_rental_amount(self):
        for record in self:
            if record.rental_rate_type == 'daily':
                record.total_rental_amount = record.rental_rate * record.duration_days * record.vehicle_count
            elif record.rental_rate_type == 'weekly':
                weeks = record.duration_days / 7.0
                record.total_rental_amount = record.rental_rate * weeks * record.vehicle_count
            elif record.rental_rate_type == 'monthly':
                months = record.duration_days / 30.0
                record.total_rental_amount = record.rental_rate * months * record.vehicle_count
            else:
                record.total_rental_amount = 0.0
    
    @api.depends('initial_odometer', 'final_odometer')
    def _compute_distance_traveled(self):
        for record in self:
            if record.final_odometer and record.initial_odometer:
                record.distance_traveled = record.final_odometer - record.initial_odometer
            else:
                record.distance_traveled = 0.0
    
    # Fuel Compute Methods (Phase 2B)
    @api.depends('fuel_log_ids')
    def _compute_fuel_log_count(self):
        """Count fuel logs"""
        for record in self:
            record.fuel_log_count = len(record.fuel_log_ids)
    
    @api.depends('initial_fuel_level', 'vehicle_ids', 'vehicle_ids.fuel_tank_capacity')
    def _compute_initial_fuel_percentage(self):
        """Calculate initial fuel percentage"""
        for record in self:
            if record.initial_fuel_level and record.vehicle_ids:
                # Use first vehicle's tank capacity for calculation
                vehicle = record.vehicle_ids[0] if record.vehicle_ids else False
                if vehicle and vehicle.fuel_tank_capacity > 0:
                    record.initial_fuel_percentage = (record.initial_fuel_level / vehicle.fuel_tank_capacity) * 100
                else:
                    record.initial_fuel_percentage = 0.0
            else:
                record.initial_fuel_percentage = 0.0
    
    @api.depends('final_fuel_level', 'vehicle_ids', 'vehicle_ids.fuel_tank_capacity')
    def _compute_final_fuel_percentage(self):
        """Calculate final fuel percentage"""
        for record in self:
            if record.final_fuel_level and record.vehicle_ids:
                # Use first vehicle's tank capacity for calculation
                vehicle = record.vehicle_ids[0] if record.vehicle_ids else False
                if vehicle and vehicle.fuel_tank_capacity > 0:
                    record.final_fuel_percentage = (record.final_fuel_level / vehicle.fuel_tank_capacity) * 100
                else:
                    record.final_fuel_percentage = 0.0
            else:
                record.final_fuel_percentage = 0.0
    
    @api.depends('fuel_log_ids', 'fuel_log_ids.quantity')
    def _compute_fuel_consumed(self):
        """Calculate total fuel consumed during rental"""
        for record in self:
            record.fuel_consumed = sum(record.fuel_log_ids.mapped('quantity'))
    
    @api.depends('initial_fuel_level', 'final_fuel_level', 'fuel_recharge_policy', 'fuel_log_ids', 'fuel_log_ids.total_cost', 'vehicle_ids', 'vehicle_ids.fuel_tank_capacity')
    def _compute_fuel_cost_to_charge(self):
        """Calculate fuel cost to charge customer based on recharge policy with fallback pricing"""
        for record in self:
            cost = 0.0
            
            if not record.vehicle_ids:
                record.fuel_cost_to_charge = 0.0
                continue
            
            vehicle = record.vehicle_ids[0]  # Use first vehicle for calculation
            
            if record.fuel_recharge_policy == 'none':
                # No fuel recharge required
                cost = 0.0
            
            elif record.fuel_recharge_policy == 'full':
                # Customer must return with full tank
                if record.final_fuel_level and vehicle.fuel_tank_capacity > 0:
                    fuel_shortage = vehicle.fuel_tank_capacity - record.final_fuel_level
                    
                    if fuel_shortage > 0:
                        # Get average fuel price from logs
                        avg_price = record._get_average_fuel_price()
                        if avg_price > 0:
                            cost = fuel_shortage * avg_price
                        else:
                            # Fallback: use default rate when no fuel logs
                            cost = fuel_shortage * 1.5  # Default $1.50 per liter
            
            elif record.fuel_recharge_policy == 'percentage':
                # Customer must return with same percentage as start
                if record.initial_fuel_level and record.final_fuel_level:
                    fuel_difference = record.initial_fuel_level - record.final_fuel_level
                    
                    if fuel_difference > 0:
                        # Get average fuel price from logs
                        avg_price = record._get_average_fuel_price()
                        if avg_price > 0:
                            cost = fuel_difference * avg_price
                        else:
                            # Fallback: use default rate when no fuel logs
                            cost = fuel_difference * 1.5  # Default $1.50 per liter
            
            record.fuel_cost_to_charge = cost
    
    # Toll Compute Methods (Phase 2C)
    @api.depends('toll_record_ids')
    def _compute_toll_count(self):
        """Count toll records"""
        for record in self:
            record.toll_count = len(record.toll_record_ids)
    
    @api.depends('toll_record_ids', 'toll_record_ids.amount')
    def _compute_total_toll_cost(self):
        """Calculate total toll cost"""
        for record in self:
            record.total_toll_cost = sum(record.toll_record_ids.mapped('amount'))
    
    # Trip Compute Methods (Phase 2D)
    @api.depends('trip_ids')
    def _compute_trip_count(self):
        """Count trips"""
        for record in self:
            record.trip_count = len(record.trip_ids)
    
    @api.depends('trip_ids', 'trip_ids.distance')
    def _compute_total_trip_distance(self):
        """Calculate total trip distance"""
        for record in self:
            record.total_trip_distance = sum(record.trip_ids.mapped('distance'))
    
    @api.depends('distance_traveled', 'allowed_kilometers', 'extra_km_rate')
    def _compute_distance_charges(self):
        """Calculate extra charges for exceeding allowed kilometers"""
        for record in self:
            if record.distance_traveled and record.allowed_kilometers and record.extra_km_rate:
                excess_km = record.distance_traveled - record.allowed_kilometers
                if excess_km > 0:
                    record.distance_charges = excess_km * record.extra_km_rate
                else:
                    record.distance_charges = 0.0
            else:
                record.distance_charges = 0.0
    
    @api.depends('total_rental_amount', 'distance_charges', 'fuel_cost_to_charge',
                 'total_toll_cost', 'additional_charges', 'discount')
    def _compute_total_amount(self):
        """Calculate total amount for the rental"""
        for record in self:
            total = (
                record.total_rental_amount +
                record.distance_charges +
                record.fuel_cost_to_charge +
                record.total_toll_cost +
                record.additional_charges -
                record.discount
            )
            record.total_amount = max(0.0, total)  # Ensure non-negative
    
    def _get_average_fuel_price(self):
        """Helper method to calculate average fuel price from logs"""
        self.ensure_one()
        
        if not self.fuel_log_ids:
            return 0.0
        
        total_cost = sum(self.fuel_log_ids.mapped('total_cost'))
        total_quantity = sum(self.fuel_log_ids.mapped('quantity'))
        
        if total_quantity > 0:
            return total_cost / total_quantity
        return 0.0
    
    # CRUD Methods
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.rental.contract') or _('New')
        return super().create(vals_list)
    
    # Constraints
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.end_date < record.start_date:
                raise ValidationError(_('End date cannot be before start date!'))
    
    @api.constrains('initial_odometer', 'final_odometer')
    def _check_odometer(self):
        for record in self:
            if record.final_odometer and record.initial_odometer:
                if record.final_odometer < record.initial_odometer:
                    raise ValidationError(_('Final odometer cannot be less than initial odometer!'))
    
    @api.constrains('deposit_return_amount', 'deposit_amount')
    def _check_deposit_return(self):
        for record in self:
            if record.deposit_return_amount and record.deposit_amount:
                if record.deposit_return_amount > record.deposit_amount:
                    raise ValidationError(_('Deposit return amount cannot exceed deposit amount!'))
    
    def _validate_rental_start_requirements(self):
        """Validate all requirements before starting rental"""
        self.ensure_one()
        errors = []
        
        # Check vehicle availability
        for vehicle in self.vehicle_ids:
            is_available, blocker, blocker_type = vehicle.check_availability(self.start_date, self.end_date)
            if not is_available:
                if blocker_type == 'rental':
                    errors.append(
                        _('Vehicle %s is already rented (Contract: %s from %s to %s)') % 
                        (vehicle.name, blocker.name, blocker.start_date, blocker.end_date)
                    )
                elif blocker_type == 'maintenance':
                    errors.append(
                        _('Vehicle %s has scheduled maintenance on %s') % 
                        (vehicle.name, blocker.date)
                    )
                else:
                    errors.append(
                        _('Vehicle %s is not available (Status: %s)') % 
                        (vehicle.name, vehicle.state)
                    )
        
        # Check driver license
        if self.driver_id:
            if self.driver_id.license_status == 'expired':
                errors.append(
                    _('Driver %s has an expired license (Expired: %s)!') % 
                    (self.driver_id.name, self.driver_id.license_expiry_date)
                )
            elif self.driver_id.license_status == 'suspended':
                errors.append(
                    _('Driver %s has a suspended license!') % self.driver_id.name
                )
        
        # Check required fields
        if not self.initial_odometer:
            errors.append(_('Initial odometer reading is required'))
        if not self.initial_fuel_level:
            errors.append(_('Initial fuel level is required'))
        
        if errors:
            raise ValidationError('\n'.join(errors))
        
        return True
    
    # Business Logic
    def action_confirm(self):
        """Confirm the rental contract"""
        for record in self:
            if record.state != 'draft':
                raise ValidationError(_('Only draft contracts can be confirmed!'))
            
            # Validate required fields
            if not record.vehicle_ids:
                raise ValidationError(_('Please select at least one vehicle!'))
            if not record.customer_id:
                raise ValidationError(_('Customer is required!'))
            if not record.rental_rate or record.rental_rate <= 0:
                raise ValidationError(_('Rental rate must be greater than zero!'))
            
            record.write({'state': 'confirmed'})
            record.message_post(body=_('Rental contract confirmed.'))
    
    def action_start_rental(self):
        """Start the rental and update vehicle status"""
        for record in self:
            if record.state != 'confirmed':
                raise ValidationError(_('Only confirmed contracts can be started!'))
            
            # Validate initial readings
            if not record.initial_odometer:
                raise ValidationError(_('Please record initial odometer reading!'))
            if not record.initial_fuel_level:
                raise ValidationError(_('Please record initial fuel level!'))
            
            # Check vehicle availability
            for vehicle in record.vehicle_ids:
                if vehicle.state == 'rented':
                    raise ValidationError(_('Vehicle %s is already rented!') % vehicle.name)
            
            record.write({'state': 'active'})
            # Update vehicle status to 'rented'
            rented_status = self.env['fleet.vehicle.status'].search([('code', '=', 'rented')], limit=1)
            if rented_status:
                record.vehicle_ids.write({'status_id': rented_status.id})
            record.message_post(body=_('Rental started. Vehicle(s) marked as rented.'))
    
    def action_complete_rental(self):
        """Complete the rental"""
        for record in self:
            if record.state != 'active':
                raise ValidationError(_('Only active rentals can be completed!'))
            
            # Validate final readings
            if not record.final_odometer:
                raise ValidationError(_('Please record final odometer reading!'))
            if not record.final_fuel_level:
                raise ValidationError(_('Please record final fuel level!'))
            
            record.write({
                'state': 'completed',
                'actual_return_date': fields.Date.context_today(self)
            })
            # Update vehicle status back to 'available'
            available_status = self.env['fleet.vehicle.status'].search([('code', '=', 'available')], limit=1)
            if available_status:
                record.vehicle_ids.write({'status_id': available_status.id})
            record.message_post(body=_('Rental completed. Vehicle(s) marked as available.'))
    
    def action_cancel(self):
        """Cancel the rental contract"""
        for record in self:
            if record.state not in ['draft', 'confirmed', 'active']:
                raise ValidationError(_('Cannot cancel a %s contract!') % record.state)
            
            if record.state == 'active':
                # Return vehicles to available
                available_status = self.env['fleet.vehicle.status'].search([('code', '=', 'available')], limit=1)
                if available_status:
                    record.vehicle_ids.write({'status_id': available_status.id})
            
            record.write({'state': 'cancelled'})
            record.message_post(body=_('Rental contract cancelled.'))
    
    def action_return_deposit(self):
        """Mark deposit as returned"""
        for record in self:
            if not record.deposit_returned:
                record.deposit_returned = True
                record.deposit_return_date = fields.Date.context_today(self)
                if not record.deposit_return_amount:
                    record.deposit_return_amount = record.deposit_amount
                record.message_post(body=_('Deposit returned: %s') % record.deposit_return_amount)

