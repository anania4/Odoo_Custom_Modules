# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class FleetMaintenanceSchedule(models.Model):
    _name = 'fleet.maintenance.schedule'
    _description = 'Fleet Maintenance Schedule'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Schedule Name',
        required=True,
        tracking=True,
        help='Name of the maintenance schedule'
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=False,
        ondelete='cascade',
        tracking=True,
        help='Vehicle for this maintenance schedule (not required if applying to all vehicles)'
    )
    
    maintenance_type_id = fields.Many2one(
        'fleet.maintenance.type',
        string='Maintenance Type',
        required=True,
        tracking=True,
        help='Type of maintenance to be performed'
    )
    
    description = fields.Text(
        string='Description',
        help='Description of the scheduled maintenance'
    )
    
    priority = fields.Selection([
        ('0', 'Low'),
        ('1', 'Medium'),
        ('2', 'High'),
        ('3', 'Very High')
    ], string='Priority', default='1', tracking=True,
       help='Priority of the maintenance task')
    
    # Scheduling based on time
    schedule_by_time = fields.Boolean(
        string='Schedule by Time',
        default=False,
        tracking=True,
        help='Enable time-based scheduling'
    )
    
    interval_number = fields.Integer(
        string='Interval',
        default=1,
        help='Interval number for time-based scheduling'
    )
    
    interval_type = fields.Selection(
        [
            ('days', 'Days'),
            ('weeks', 'Weeks'),
            ('months', 'Months'),
            ('years', 'Years'),
            ('mileage', 'Mileage'),
        ],
        string='Interval Unit',
        default='months',
        help='Unit of time for the interval'
    )
    
    last_maintenance_date = fields.Date(
        string='Last Maintenance Date',
        help='Date of last maintenance'
    )
    
    next_maintenance_date = fields.Date(
        string='Next Maintenance Date',
        compute='_compute_next_maintenance_date',
        store=True,
        help='Calculated next maintenance date'
    )
    
    # Scheduling based on odometer
    schedule_by_odometer = fields.Boolean(
        string='Schedule by Odometer',
        default=False,
        tracking=True,
        help='Enable odometer-based scheduling'
    )
    
    odometer_interval = fields.Integer(
        string='Odometer Interval (km)',
        default=5000,
        help='Kilometers between maintenance'
    )
    
    interval_value = fields.Integer(
        string='Interval Value',
        default=1,
        help='Value of the interval for the selected interval type'
    )
    
    assigned_mechanic = fields.Char(
        string='Assigned Mechanic',
        tracking=True,
        help='Name of the mechanic assigned to this maintenance'
    )
    
    last_maintenance_odometer = fields.Float(
        string='Last Maintenance Odometer',
        help='Odometer reading at last maintenance'
    )
    
    next_maintenance_odometer = fields.Float(
        string='Next Maintenance Odometer',
        compute='_compute_next_maintenance_odometer',
        store=True,
        help='Calculated next maintenance odometer'
    )
    
    current_vehicle_odometer = fields.Float(
        string='Current Odometer',
        related='vehicle_id.odometer',
        store=False,
        help='Current vehicle odometer reading'
    )
    
    # Status tracking
    is_overdue = fields.Boolean(
        string='Overdue',
        compute='_compute_overdue_status',
        store=False,
        help='Whether maintenance is overdue'
    )
    
    days_until_due = fields.Integer(
        string='Days Until Due',
        compute='_compute_days_until_due',
        store=False,
        help='Number of days until maintenance is due'
    )
    
    km_until_due = fields.Float(
        string='KM Until Due',
        compute='_compute_km_until_due',
        store=False,
        help='Kilometers until maintenance is due'
    )
    
    # Configuration
    auto_create_activity = fields.Boolean(
        string='Auto-create Activity',
        default=True,
        help='Automatically create activity reminder when due'
    )
    
    reminder_days_before = fields.Integer(
        string='Reminder Days Before',
        default=7,
        help='Days before due date to create reminder'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to disable this schedule'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Sequence for ordering'
    )
    
    # Related maintenance records
    maintenance_ids = fields.One2many(
        'fleet.maintenance',
        'schedule_id',
        string='Maintenance Records',
        help='All maintenance records from this schedule'
    )
    
    maintenance_count = fields.Integer(
        string='Maintenance Count',
        compute='_compute_maintenance_count',
        store=False,
        help='Number of maintenance records'
    )
    
    # Additional scheduling options
    apply_to_all_vehicles = fields.Boolean(
        string='Apply to All Vehicles',
        default=False,
        help='If checked, this schedule will apply to all vehicles in the fleet',
    )
    
    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company this schedule belongs to'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes'
    )
    
    _sql_constraints = [
        ('interval_number_positive', 'CHECK(interval_number > 0)', 'Interval number must be positive!'),
        ('odometer_interval_positive', 'CHECK(odometer_interval > 0)', 'Odometer interval must be positive!'),
        ('at_least_one_schedule_type', 'CHECK(schedule_by_time = true OR schedule_by_odometer = true)', 
         'At least one scheduling method must be enabled!'),
    ]
    
    @api.depends('last_maintenance_date', 'interval_number', 'interval_type', 'schedule_by_time')
    def _compute_next_maintenance_date(self):
        """Calculate next maintenance date based on time interval"""
        for schedule in self:
            if schedule.schedule_by_time and schedule.last_maintenance_date:
                if schedule.interval_type == 'days':
                    delta = timedelta(days=schedule.interval_number)
                elif schedule.interval_type == 'weeks':
                    delta = timedelta(weeks=schedule.interval_number)
                elif schedule.interval_type == 'months':
                    # Approximate months as 30 days
                    delta = timedelta(days=schedule.interval_number * 30)
                elif schedule.interval_type == 'years':
                    delta = timedelta(days=schedule.interval_number * 365)
                else:
                    delta = timedelta(days=30)
                
                schedule.next_maintenance_date = schedule.last_maintenance_date + delta
            else:
                schedule.next_maintenance_date = False
    
    @api.depends('last_maintenance_odometer', 'odometer_interval', 'schedule_by_odometer')
    def _compute_next_maintenance_odometer(self):
        """Calculate next maintenance odometer"""
        for schedule in self:
            if schedule.schedule_by_odometer and schedule.last_maintenance_odometer:
                schedule.next_maintenance_odometer = schedule.last_maintenance_odometer + schedule.odometer_interval
            else:
                schedule.next_maintenance_odometer = 0.0
    
    @api.depends('next_maintenance_date', 'next_maintenance_odometer', 'current_vehicle_odometer', 'schedule_by_time', 'schedule_by_odometer')
    def _compute_overdue_status(self):
        """Determine if maintenance is overdue"""
        today = fields.Date.today()
        for schedule in self:
            overdue = False
            
            # Check time-based overdue
            if schedule.schedule_by_time and schedule.next_maintenance_date:
                if schedule.next_maintenance_date < today:
                    overdue = True
            
            # Check odometer-based overdue
            if schedule.schedule_by_odometer and schedule.next_maintenance_odometer and schedule.vehicle_id:
                if schedule.current_vehicle_odometer and schedule.current_vehicle_odometer >= schedule.next_maintenance_odometer:
                    overdue = True
            
            schedule.is_overdue = overdue
    
    @api.depends('next_maintenance_date')
    def _compute_days_until_due(self):
        """Calculate days until maintenance is due"""
        today = fields.Date.today()
        for schedule in self:
            if schedule.next_maintenance_date:
                delta = (schedule.next_maintenance_date - today).days
                schedule.days_until_due = delta
            else:
                schedule.days_until_due = 0
    
    @api.depends('next_maintenance_odometer', 'current_vehicle_odometer')
    def _compute_km_until_due(self):
        """Calculate kilometers until maintenance is due"""
        for schedule in self:
            if schedule.next_maintenance_odometer and schedule.current_vehicle_odometer:
                schedule.km_until_due = schedule.next_maintenance_odometer - schedule.current_vehicle_odometer
            else:
                schedule.km_until_due = 0.0
    
    @api.depends('maintenance_ids')
    def _compute_maintenance_count(self):
        """Count maintenance records"""
        for schedule in self:
            schedule.maintenance_count = len(schedule.maintenance_ids)
    
    @api.constrains('schedule_by_time', 'schedule_by_odometer')
    def _check_schedule_type(self):
        """Ensure at least one scheduling method is enabled"""
        for schedule in self:
            if not schedule.schedule_by_time and not schedule.schedule_by_odometer:
                raise ValidationError(_('At least one scheduling method (time or odometer) must be enabled!'))
    
    @api.constrains('vehicle_id', 'apply_to_all_vehicles')
    def _check_vehicle_or_all(self):
        """Ensure either a vehicle is selected or apply_to_all_vehicles is checked"""
        for schedule in self:
            if not schedule.vehicle_id and not schedule.apply_to_all_vehicles:
                raise ValidationError(_('You must either select a vehicle or check "Apply to All Vehicles"!'))
    
    def action_create_maintenance(self):
        """Manually create maintenance record from schedule"""
        self.ensure_one()
        
        if self.apply_to_all_vehicles:
            raise ValidationError(_('Cannot create maintenance from a schedule that applies to all vehicles. Please create maintenance records individually for each vehicle.'))
        
        maintenance = self.env['fleet.maintenance'].create({
            'vehicle_id': self.vehicle_id.id,
            'maintenance_type_id': self.maintenance_type_id.id,
            'schedule_id': self.id,
            'description': self.description or f"Scheduled {self.maintenance_type_id.name}",
            'date': fields.Date.today(),
            'company_id': self.company_id.id,
        })
        
        # Update last maintenance tracking
        self.write({
            'last_maintenance_date': fields.Date.today(),
            'last_maintenance_odometer': self.vehicle_id.odometer if self.vehicle_id else 0,
        })
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Maintenance Record'),
            'res_model': 'fleet.maintenance',
            'res_id': maintenance.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def _cron_check_maintenance_schedules(self):
        """Scheduled action to check for due maintenance and create activities with priority levels"""
        today = fields.Date.today()
        
        schedules = self.search([('active', '=', True)])
        
        for schedule in schedules:
            should_create_activity = False
            activity_note = []
            priority = 'normal'
            
            # Check time-based schedule
            if schedule.schedule_by_time and schedule.next_maintenance_date:
                days_until_due = (schedule.next_maintenance_date - today).days
                
                if days_until_due < 0:
                    # Overdue
                    should_create_activity = True
                    priority = 'urgent'
                    activity_note.append(f"⚠️ OVERDUE by {abs(days_until_due)} days!")
                    activity_note.append(f"Due date: {schedule.next_maintenance_date}")
                elif days_until_due <= schedule.reminder_days_before:
                    # Due soon
                    should_create_activity = True
                    priority = 'high' if days_until_due <= 3 else 'normal'
                    activity_note.append(f"Due in {days_until_due} days")
                    activity_note.append(f"Due date: {schedule.next_maintenance_date}")
            
            # Check odometer-based schedule
            if schedule.schedule_by_odometer and schedule.next_maintenance_odometer and schedule.vehicle_id:
                if schedule.current_vehicle_odometer:
                    km_until_due = schedule.next_maintenance_odometer - schedule.current_vehicle_odometer
                    
                    if km_until_due <= 0:
                        # Overdue
                        should_create_activity = True
                        priority = 'urgent'
                        activity_note.append(f"⚠️ OVERDUE by {abs(km_until_due)} km!")
                        activity_note.append(f"Due at: {schedule.next_maintenance_odometer}km")
                    elif km_until_due <= 500:  # 500km warning threshold
                        should_create_activity = True
                        priority = 'high'
                        activity_note.append(f"Due in {km_until_due} km")
                        activity_note.append(f"Current: {schedule.current_vehicle_odometer}km")
            
            if should_create_activity and schedule.auto_create_activity:
                # Check if recent activity exists (within last 7 days)
                recent_activity = self.env['mail.activity'].search([
                    ('res_model', '=', 'fleet.maintenance.schedule'),
                    ('res_id', '=', schedule.id),
                    ('summary', 'ilike', schedule.name),
                    ('create_date', '>=', fields.Datetime.now() - timedelta(days=7)),
                ], limit=1)
                
                if not recent_activity:
                    activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
                    
                    vehicle_info = f"Vehicle: {schedule.vehicle_id.name} ({schedule.vehicle_id.license_plate})\n" if schedule.vehicle_id else "Applies to: All Vehicles\n"
                    
                    schedule.activity_schedule(
                        activity_type_id=activity_type.id if activity_type else False,
                        summary=f"🔧 Scheduled Maintenance Due: {schedule.name}",
                        note=vehicle_info + f"Maintenance Type: {schedule.maintenance_type_id.name}\n\n" + "\n".join(activity_note),
                        date_deadline=schedule.next_maintenance_date if schedule.schedule_by_time else today,
                    )
