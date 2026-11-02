# -*- coding: utf-8 -*-

from datetime import timedelta

from odoo import api, fields, models

LICENSE_DUE_SOON_DAYS = 30


class FleetDriver(models.Model):
    _name = 'fleet.driver'
    _description = 'Fleet Driver'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'name'

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        ondelete='restrict',
        index=True,
        tracking=True,
        help='Employee working as a driver, from the Employees app',
    )
    name = fields.Char(related='employee_id.name', store=True, string='Name')
    image_128 = fields.Image(related='employee_id.image_128')
    work_phone = fields.Char(related='employee_id.work_phone', string='Phone')
    mobile_phone = fields.Char(related='employee_id.mobile_phone', string='Mobile')
    company_id = fields.Many2one(
        related='employee_id.company_id', store=True, string='Company'
    )
    active = fields.Boolean(default=True)

    # License
    license_number = fields.Char(string='License Number', tracking=True)
    license_category = fields.Char(
        string='License Category',
        tracking=True,
        help='Driving license category / class',
    )
    license_expiry_date = fields.Date(string='License Expiry Date', tracking=True)
    license_state = fields.Selection(
        [
            ('valid', 'Valid'),
            ('due_soon', 'Expires Soon'),
            ('expired', 'Expired'),
            ('missing', 'No Expiry Date'),
        ],
        string='License Status',
        compute='_compute_license_state',
    )

    # Assignments
    assignment_ids = fields.Many2many(
        'fleet.driver.assignment',
        string='Assignment History',
        compute='_compute_assignments',
    )
    current_assignment_id = fields.Many2one(
        'fleet.driver.assignment', compute='_compute_assignments'
    )
    current_vehicle_id = fields.Many2one(
        'fleet.vehicle', string='Current Vehicle', compute='_compute_assignments'
    )
    current_vehicle_plate = fields.Char(
        string='Plate', compute='_compute_assignments'
    )
    current_vehicle_model = fields.Char(
        string='Model', compute='_compute_assignments'
    )
    assigned_since = fields.Date(string='Assigned Since', compute='_compute_assignments')

    # Summary
    vehicle_count = fields.Integer(
        string='Vehicles Driven', compute='_compute_summary'
    )
    total_km = fields.Float(string='Total km Driven', compute='_compute_summary')
    service_count = fields.Integer(
        string='Services on Their Vehicles', compute='_compute_summary'
    )

    _sql_constraints = [
        ('employee_unique', 'unique(employee_id)',
         'This employee is already registered as a driver.'),
    ]

    @api.depends('license_expiry_date')
    def _compute_license_state(self):
        today = fields.Date.context_today(self)
        soon = today + timedelta(days=LICENSE_DUE_SOON_DAYS)
        for driver in self:
            expiry = driver.license_expiry_date
            if not expiry:
                driver.license_state = 'missing'
            elif expiry < today:
                driver.license_state = 'expired'
            elif expiry <= soon:
                driver.license_state = 'due_soon'
            else:
                driver.license_state = 'valid'

    def _get_assignments(self):
        self.ensure_one()
        if not self.employee_id:
            return self.env['fleet.driver.assignment']
        return self.env['fleet.driver.assignment'].search(
            [('employee_id', '=', self.employee_id.id)],
            order='date_start desc, id desc',
        )

    @api.depends('employee_id')
    def _compute_assignments(self):
        today = fields.Date.context_today(self)
        for driver in self:
            assignments = driver._get_assignments()
            current = assignments.filtered(
                lambda a: a.date_start <= today
                and (not a.date_end or a.date_end >= today)
            )[:1]
            vehicle = current.vehicle_id
            driver.assignment_ids = assignments
            driver.current_assignment_id = current
            driver.current_vehicle_id = vehicle
            driver.current_vehicle_plate = vehicle.license_plate or False
            driver.current_vehicle_model = vehicle.sudo().model_id.name or False
            driver.assigned_since = current.date_start or False

    @api.depends('employee_id')
    def _compute_summary(self):
        today = fields.Date.context_today(self)
        Service = self.env['fleet.service'].sudo()
        for driver in self:
            assignments = driver._get_assignments().sudo()
            driver.vehicle_count = len(assignments.vehicle_id)

            km = 0.0
            service_domain = []
            for assignment in assignments:
                if assignment.odometer_end:
                    km += assignment.distance_driven
                elif assignment.is_active and assignment.odometer_start:
                    # Ongoing assignment: count up to the vehicle's current reading
                    km += max(assignment.vehicle_id.odometer - assignment.odometer_start, 0.0)
                # Services done on the vehicle while this driver had it
                service_domain.append([
                    ('vehicle_id', '=', assignment.vehicle_id.id),
                    ('date', '>=', assignment.date_start),
                    ('date', '<=', assignment.date_end or today),
                ])
            driver.total_km = km

            if service_domain:
                domain = ['|'] * (len(service_domain) - 1)
                for clause in service_domain:
                    domain += ['&', '&'] + clause
                domain = [('state', '!=', 'cancelled')] + domain
                driver.service_count = Service.search_count(domain)
            else:
                driver.service_count = 0
