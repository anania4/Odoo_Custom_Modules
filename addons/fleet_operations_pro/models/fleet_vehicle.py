# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class FleetVehicle(models.Model):
    _name = 'fleet.vehicle'
    _description = 'Fleet Vehicle'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'license_plate'
    # Vehicles are referred to by their plate number everywhere
    _rec_name = 'license_plate'
    _rec_names_search = ['license_plate', 'name', 'previous_plate_no', 'chassis_no']

    # Basic Information
    image = fields.Image(
        string='Vehicle Image',
        max_width=1024,
        max_height=1024,
        help='Vehicle photo'
    )
    name = fields.Char(
        string='Car Name',
        required=True,
        tracking=True,
        help='Vehicle reference name'
    )
    license_plate = fields.Char(
        string='License Plate',
        required=True,
        tracking=True,
        help='Vehicle registration plate number'
    )

    # Identification
    previous_plate_no = fields.Char(
        string='Previous Plate No',
        tracking=True,
        help='Plate number previously registered for this vehicle'
    )
    chassis_no = fields.Char(
        string='Chassis No',
        tracking=True,
        help='Vehicle Identification Number (VIN) / Chassis Number'
    )
    engine_no = fields.Char(
        string='Engine No',
        tracking=True
    )
    model_id = fields.Many2one(
        'fleet.vehicle.model',
        string='Model',
        tracking=True,
        help='Vehicle model (configured in Configuration > Vehicle Models)'
    )
    model_year = fields.Integer(
        string='Model Year',
        tracking=True,
        help='Year of manufacture'
    )
    color = fields.Char(
        string='Color',
        tracking=True
    )

    # Registration & Service
    permitted_work_service = fields.Char(
        string='Permitted Work Service',
        tracking=True,
        help='Work/service the vehicle is permitted (licensed) for'
    )
    body_type = fields.Char(
        string='Body Type',
        tracking=True
    )
    category_id = fields.Many2one(
        'fleet.vehicle.category',
        string='Category',
        required=True,
        tracking=True,
        help='Vehicle category (Car, Truck, Bus, etc.)'
    )
    tag_ids = fields.Many2many(
        'fleet.vehicle.tag',
        'fleet_vehicle_tag_rel',
        'vehicle_id',
        'tag_id',
        string='Tags'
    )

    # Assignment & Acquisition
    manager_id = fields.Many2one(
        'res.users',
        string='Manager',
        tracking=True,
        help='User responsible for this vehicle'
    )
    acquisition_cost = fields.Monetary(
        string='Acquisition Cost',
        currency_field='currency_id',
        tracking=True
    )

    # Engine & Fuel
    engine_capacity = fields.Integer(
        string='Engine Capacity (CC)',
        help='Motor power in cubic centimetres'
    )
    horsepower = fields.Integer(
        string='Horsepower',
        help='Motor horse power'
    )
    cylinders = fields.Integer(
        string='No. of Cylinders'
    )
    fuel_type_id = fields.Many2one(
        'fleet.fuel.type',
        string='Fuel Type',
        tracking=True,
        help='Type of fuel used'
    )
    fuel_tank_capacity = fields.Float(
        string='Fuel Tank Capacity (L)',
        help='Total fuel tank capacity in liters',
        tracking=True
    )
    current_fuel_level = fields.Float(
        string='Current Fuel Level (L)',
        compute='_compute_current_fuel_level',
        store=True,
        help='Current fuel level in liters'
    )
    fuel_percentage = fields.Float(
        string='Fuel Level (%)',
        compute='_compute_fuel_percentage',
        store=True,
        help='Current fuel level percentage'
    )
    
    # Status & Lifecycle
    status_id = fields.Many2one(
        'fleet.vehicle.status',
        string='Status',
        required=True,
        tracking=True,
        default=lambda self: self._default_status_id(),
        group_expand='_read_group_status_ids',
        help='Current vehicle status (configured in Configuration > Vehicle Statuses)'
    )
    status_code = fields.Char(
        related='status_id.code',
        store=True,
        index=True,
        string='Status Code',
        help='Technical code of the status (available, in_maintenance...) used by the dashboard and workflows'
    )
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Uncheck to archive the vehicle'
    )
    
    # Acquisition & Disposal
    acquisition_date = fields.Date(
        string='Acquisition Date',
        tracking=True,
        help='Date when vehicle was acquired'
    )
    disposal_date = fields.Date(
        string='Disposal Date',
        tracking=True,
        help='Date when vehicle was disposed/sold'
    )
    
    # Odometer
    odometer = fields.Float(
        string='Odometer (km)',
        tracking=True,
        help='Last recorded odometer reading in kilometers'
    )
    odometer_date = fields.Date(
        string='Odometer Date',
        help='Date of last odometer reading'
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
        default=lambda self: self.env.company,
        required=True
    )
    
    # Capacity & Weight
    seats = fields.Integer(
        string='Seats',
        help='Passenger capacity'
    )
    doors = fields.Integer(
        string='Doors'
    )
    axles_front = fields.Integer(
        string='Front Axles'
    )
    axles_back = fields.Integer(
        string='Back Axles'
    )
    general_weight_load = fields.Float(
        string='General Weight Load'
    )
    single_weight_load = fields.Float(
        string='Single Weight Load'
    )
    extra_carry_weight = fields.Float(
        string='Extra Carry Weight'
    )

    # Ownership
    ownership_type = fields.Selection(
        [
            ('owned', 'Owned'),
            ('rented', 'Rented'),
        ],
        string='Ownership Type',
        default='owned',
        required=True,
        tracking=True
    )
    rental_vendor_id = fields.Many2one(
        'res.partner',
        string='Rental Vendor / Owner',
        tracking=True,
        help='Company or person the vehicle is rented from'
    )
    vendor_contact_phone = fields.Char(
        string='Vendor Contact Phone',
        compute='_compute_vendor_contact_phone',
        store=True,
        readonly=False
    )

    # Rental Terms (only when rented)
    rental_start_date = fields.Date(
        string='Rental Start Date',
        tracking=True
    )
    rental_end_date = fields.Date(
        string='Rental End Date',
        tracking=True
    )
    rental_cost = fields.Monetary(
        string='Rental Cost',
        currency_field='currency_id',
        tracking=True
    )
    rental_frequency = fields.Selection(
        [
            ('daily', 'Daily'),
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        string='Rental Frequency',
        tracking=True
    )
    rental_contract_ref = fields.Char(
        string='Rental Contract Reference',
        tracking=True
    )

    notes = fields.Text(
        string='Notes',
        help='Additional information about the vehicle'
    )
    
    # Driver Assignment (Phase 1B)
    driver_assignment_ids = fields.One2many(
        'fleet.driver.assignment',
        'vehicle_id',
        string='Driver Assignments',
        help='History of driver assignments'
    )
    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver',
        compute='_compute_current_driver',
        inverse='_inverse_current_driver',
        search='_search_driver_id',
        store=False,
        help='Currently assigned driver (employee)'
    )
    
    # Fuel Logs (Phase 1C)
    fuel_log_ids = fields.One2many(
        'fleet.fuel.log',
        'vehicle_id',
        string='Fuel Logs',
        help='History of fuel entries'
    )
    fuel_log_count = fields.Integer(
        string='Fuel Entries',
        compute='_compute_fuel_log_count',
        store=False
    )
    average_fuel_efficiency = fields.Float(
        string='Avg Fuel Efficiency (km/L)',
        compute='_compute_average_fuel_efficiency',
        store=False,
        digits=(10, 2),
        help='Average fuel efficiency across all fuel logs'
    )
    
    # Maintenance (Phase 1D)
    maintenance_ids = fields.One2many(
        'fleet.maintenance',
        'vehicle_id',
        string='Maintenance Records',
        help='History of maintenance activities'
    )
    maintenance_count = fields.Integer(
        string='Maintenance Count',
        compute='_compute_maintenance_count',
        store=False
    )
    last_maintenance_date = fields.Date(
        string='Last Maintenance',
        compute='_compute_last_maintenance_date',
        store=False,
        help='Date of last maintenance'
    )
    # Toll Management (Phase 2C)
    toll_record_ids = fields.One2many(
        'fleet.toll.record',
        'vehicle_id',
        string='Toll Records',
        help='All toll records for this vehicle'
    )
    toll_count = fields.Integer(
        string='Toll Count',
        compute='_compute_toll_count',
        store=False,
        help='Number of toll records'
    )
    # Trip Management (Phase 2D)
    trip_ids = fields.One2many(
        'fleet.trip',
        'vehicle_id',
        string='Trips',
        help='All trips for this vehicle'
    )
    trip_count = fields.Integer(
        string='Trip Count',
        compute='_compute_trip_count',
        store=False,
        help='Number of trips'
    )
    total_distance = fields.Float(
        string='Total Distance',
        compute='_compute_total_distance',
        store=False,
        help='Total distance from all trips'
    )
    
    _sql_constraints = [
        ('license_plate_unique', 'unique(license_plate)', 'License plate must be unique!'),
        ('chassis_no_unique', 'unique(chassis_no)', 'Chassis number must be unique!'),
        ('fuel_tank_capacity_positive', 'CHECK(fuel_tank_capacity >= 0)', 'Fuel tank capacity must be positive!'),
        ('odometer_positive', 'CHECK(odometer >= 0)', 'Odometer reading must be positive!'),
    ]
    
    @api.depends('rental_vendor_id')
    def _compute_vendor_contact_phone(self):
        for vehicle in self:
            vehicle.vendor_contact_phone = vehicle.rental_vendor_id.phone or vehicle.rental_vendor_id.mobile or False

    @api.constrains('rental_start_date', 'rental_end_date')
    def _check_rental_dates(self):
        for vehicle in self:
            if vehicle.rental_start_date and vehicle.rental_end_date \
                    and vehicle.rental_end_date < vehicle.rental_start_date:
                raise ValidationError(_('Rental end date cannot be before rental start date'))

    @api.model
    def _default_status_id(self):
        """New vehicles start in the status with code 'available' (or the first status)"""
        Status = self.env['fleet.vehicle.status']
        return Status.search([('code', '=', 'available')], limit=1) or Status.search([], limit=1)

    def _set_status_code(self, code):
        """Move vehicles to the status with the given code, if such a status exists"""
        status = self.env['fleet.vehicle.status'].search([('code', '=', code)], limit=1)
        if status:
            self.filtered(lambda v: v.status_id != status).write({'status_id': status.id})

    @api.model
    def _read_group_status_ids(self, statuses, domain):
        """Show all active vehicle statuses as kanban columns, including empty ones."""
        return self.env['fleet.vehicle.status'].search([])

    @api.depends('fuel_log_ids', 'fuel_log_ids.quantity', 'fuel_tank_capacity')
    def _compute_current_fuel_level(self):
        """Compute current fuel level from fuel logs"""
        for vehicle in self:
            # Get the latest fuel log
            latest_fuel_log = self.env['fleet.fuel.log'].search([
                ('vehicle_id', '=', vehicle.id)
            ], limit=1, order='date desc, id desc')
            
            if latest_fuel_log:
                # Simple approach: last filled quantity
                # In real scenarios, you'd track consumption between fills
                vehicle.current_fuel_level = latest_fuel_log.quantity
                
                # Ensure it doesn't exceed tank capacity
                if vehicle.fuel_tank_capacity and vehicle.current_fuel_level > vehicle.fuel_tank_capacity:
                    vehicle.current_fuel_level = vehicle.fuel_tank_capacity
            else:
                vehicle.current_fuel_level = 0.0
    
    @api.depends('current_fuel_level', 'fuel_tank_capacity')
    def _compute_fuel_percentage(self):
        """Compute fuel level percentage"""
        for vehicle in self:
            if vehicle.fuel_tank_capacity > 0:
                vehicle.fuel_percentage = (vehicle.current_fuel_level / vehicle.fuel_tank_capacity) * 100
            else:
                vehicle.fuel_percentage = 0.0
    
    def _compute_current_driver(self):
        """Get currently assigned driver"""
        for vehicle in self:
            current_assignment = self.env['fleet.driver.assignment'].search([
                ('vehicle_id', '=', vehicle.id),
                ('date_start', '<=', fields.Date.today()),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', fields.Date.today()),
            ], limit=1, order='date_start desc')
            
            vehicle.driver_id = current_assignment.employee_id.id if current_assignment else False

    def _search_driver_id(self, operator, value):
        """Allow searching/filtering vehicles by their current driver"""
        today = fields.Date.today()
        current = self.env['fleet.driver.assignment'].search([
            ('date_start', '<=', today),
            '|', ('date_end', '=', False), ('date_end', '>=', today),
        ])
        if value is False or value is None:
            # "Driver is set" / "Driver is not set"
            return [('id', 'not in' if operator == '=' else 'in', current.vehicle_id.ids)]
        matching = current.filtered_domain([('employee_id', operator, value)])
        return [('id', 'in', matching.vehicle_id.ids)]

    def _inverse_current_driver(self):
        """Create/update driver assignment when current driver is set on vehicle"""
        for vehicle in self:
            if not vehicle.driver_id:
                # End current active assignment if exists
                current_assignment = self.env['fleet.driver.assignment'].search([
                    ('vehicle_id', '=', vehicle.id),
                    ('date_end', '=', False),
                ], limit=1)
                if current_assignment:
                    current_assignment.write({'date_end': fields.Date.today()})
                continue

            # Check if there's already an active assignment for this driver/vehicle
            current_assignment = self.env['fleet.driver.assignment'].search([
                ('vehicle_id', '=', vehicle.id),
                ('employee_id', '=', vehicle.driver_id.id),
                ('date_end', '=', False),
            ], limit=1)

            if current_assignment:
                continue

            # End any other active assignment on this vehicle
            other_active = self.env['fleet.driver.assignment'].search([
                ('vehicle_id', '=', vehicle.id),
                ('date_end', '=', False),
                ('employee_id', '!=', vehicle.driver_id.id),
            ])
            if other_active:
                other_active.write({'date_end': fields.Date.today()})

            # Create new assignment
            self.env['fleet.driver.assignment'].create({
                'vehicle_id': vehicle.id,
                'employee_id': vehicle.driver_id.id,
                'date_start': fields.Date.today(),
                'odometer_start': vehicle.odometer or 0.0,
            })
    
    def _compute_fuel_log_count(self):
        """Count fuel log entries"""
        for vehicle in self:
            vehicle.fuel_log_count = len(vehicle.fuel_log_ids)
    
    
    @api.depends('fuel_log_ids', 'fuel_log_ids.fuel_efficiency', 'fuel_log_ids.date')
    def _compute_average_fuel_efficiency(self):
        """Calculate average fuel efficiency from fuel logs with time weighting"""
        for vehicle in self:
            # Get recent fuel logs (last 6 months)
            six_months_ago = fields.Date.today() - timedelta(days=180)
            recent_logs = vehicle.fuel_log_ids.filtered(
                lambda l: l.fuel_efficiency > 0 and 
                         l.date and 
                         l.date >= six_months_ago
            )
            
            if recent_logs:
                # Weighted average (recent logs count more)
                total_weighted = 0.0
                total_weight = 0.0
                
                for log in recent_logs:
                    # Weight based on recency (more recent = higher weight)
                    days_old = (fields.Date.today() - log.date).days
                    weight = max(1.0, 180 - days_old) / 180  # Weight from 0 to 1
                    
                    total_weighted += log.fuel_efficiency * weight
                    total_weight += weight
                
                if total_weight > 0:
                    vehicle.average_fuel_efficiency = total_weighted / total_weight
                else:
                    vehicle.average_fuel_efficiency = 0.0
            else:
                # Fallback to all-time average
                all_logs = vehicle.fuel_log_ids.filtered(lambda l: l.fuel_efficiency > 0)
                if all_logs:
                    vehicle.average_fuel_efficiency = sum(all_logs.mapped('fuel_efficiency')) / len(all_logs)
                else:
                    vehicle.average_fuel_efficiency = 0.0
    
    def _compute_maintenance_count(self):
        """Count maintenance records"""
        for vehicle in self:
            vehicle.maintenance_count = len(vehicle.maintenance_ids)
    
    def _compute_last_maintenance_date(self):
        """Get last maintenance date"""
        for vehicle in self:
            last_maintenance = self.env['fleet.maintenance'].search([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'completed')
            ], limit=1, order='date desc')
            vehicle.last_maintenance_date = last_maintenance.date if last_maintenance else False
    
    # Toll Compute Methods (Phase 2C)
    @api.depends('toll_record_ids')
    def _compute_toll_count(self):
        """Count toll records"""
        for vehicle in self:
            vehicle.toll_count = len(vehicle.toll_record_ids)
    
    # Trip Compute Methods (Phase 2D)
    @api.depends('trip_ids')
    def _compute_trip_count(self):
        """Count trips"""
        for vehicle in self:
            vehicle.trip_count = len(vehicle.trip_ids)

    @api.depends('trip_ids', 'trip_ids.distance')
    def _compute_total_distance(self):
        """Calculate total distance from trips"""
        for vehicle in self:
            vehicle.total_distance = sum(vehicle.trip_ids.mapped('distance'))
    
    @api.constrains('model_year')
    def _check_model_year(self):
        """Validate model year"""
        for vehicle in self:
            if vehicle.model_year and (vehicle.model_year < 1900 or vehicle.model_year > 2100):
                raise ValidationError(_('Model year must be between 1900 and 2100'))
    
    @api.constrains('acquisition_date', 'disposal_date')
    def _check_dates(self):
        """Validate acquisition and disposal dates"""
        for vehicle in self:
            if vehicle.acquisition_date and vehicle.disposal_date:
                if vehicle.disposal_date < vehicle.acquisition_date:
                    raise ValidationError(_('Disposal date cannot be before acquisition date'))
    
    @api.constrains('license_plate')
    def _check_duplicate_license_plate(self):
        """Check for duplicate license plates with user-friendly message"""
        for vehicle in self:
            if vehicle.license_plate:
                duplicate = self.search([
                    ('license_plate', '=ilike', vehicle.license_plate),
                    ('id', '!=', vehicle.id),
                    ('active', 'in', [True, False]),  # Check archived too
                ], limit=1)
                
                if duplicate:
                    if not duplicate.active:
                        raise ValidationError(
                            _('License plate "%s" already exists for archived vehicle "%s" (ID: %s). '
                              'Please unarchive that vehicle or use a different license plate.') % 
                            (vehicle.license_plate, duplicate.name, duplicate.id)
                        )
                    else:
                        raise ValidationError(
                            _('License plate "%s" already exists for vehicle "%s". '
                              'License plates must be unique!') % 
                            (vehicle.license_plate, duplicate.name)
                        )
    
    def check_availability(self, start_date, end_date):
        """
        Check if vehicle is available for rental during specified period
        Returns: (is_available, blocking_record, blocking_type)
        """
        self.ensure_one()
        
        # Check if vehicle is in suitable status
        if self.status_code != 'available':
            return (False, None, 'status')
        
        # Check for scheduled maintenance
        scheduled_maintenance = self.env['fleet.maintenance'].search([
            ('vehicle_id', '=', self.id),
            ('state', 'in', ['scheduled', 'in_progress']),
            ('date', '>=', start_date),
            ('date', '<=', end_date),
        ], limit=1)
        
        if scheduled_maintenance:
            return (False, scheduled_maintenance, 'maintenance')
        
        return (True, None, None)
    
    @api.depends('license_plate')
    def _compute_display_name(self):
        """Refer to vehicles by their plate number across all fleet modules"""
        for vehicle in self:
            vehicle.display_name = vehicle.license_plate or vehicle.name or ''

