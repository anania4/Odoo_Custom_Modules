# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


class FleetRequest(models.Model):
    _name = 'fleet.request'
    _description = 'Fleet Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    # =========================================
    # Basic Information
    # =========================================

    name = fields.Char(
        string='Request Reference',
        compute='_compute_name',
        store=True,
        help='Reference of the request'
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Employee',
        required=True,
        tracking=True,
        default=lambda self: self.env.user.employee_id,
        help='Employee requesting the vehicle'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='employee_id.department_id',
        store=True,
        readonly=True,
        help='Department of the requesting employee (automatic)'
    )

    manager_id = fields.Many2one(
        'hr.employee',
        string='Department Manager',
        related='employee_id.parent_id',
        store=True,
        readonly=True,
        help='Manager of the requesting employee (automatic)'
    )

    request_date = fields.Datetime(
        string='Date of Request',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        tracking=True,
        help='Date and time the request was created (automatic)'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='employee_id.company_id',
        store=True,
        readonly=True
    )

    # =========================================
    # Trip Schedule
    # =========================================

    scheduled_start = fields.Datetime(
        string='Scheduled Date & Time of Trip',
        tracking=True,
        help='Requested start date and time of the trip'
    )

    scheduled_end = fields.Datetime(
        string='Scheduled End Date & Time of Trip',
        tracking=True,
        help='Requested end date and time of the trip'
    )

    duration = fields.Float(
        string='Duration (Hours)',
        compute='_compute_duration',
        store=True,
        help='Trip duration computed from scheduled start and end'
    )

    purpose = fields.Text(
        string='Purpose',
        help='Purpose of the trip'
    )

    pickup_location = fields.Char(
        string='Pickup Location',
        help='Trip pickup location'
    )

    destination = fields.Char(
        string='Destination',
        help='Trip destination'
    )

    # =========================================
    # Approval Fields
    # =========================================

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('dept_approved', 'Department Manager Approved'),
            ('fleet_approved', 'Fleet Manager Approved'),
            ('assigned', 'Assigned'),
            ('rejected', 'Rejected'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
        help='Current stage of the request'
    )

    rejection_reason = fields.Text(
        string='Reason of Rejection',
        tracking=True,
        copy=False,
        help='Reason given by the approver when rejecting this request'
    )

    # =========================================
    # Assignment Fields (Fleet Manager Only)
    # =========================================

    driver_id = fields.Many2one(
        'hr.employee',
        string='Driver',
        domain="[('company_id', '=', company_id)]",
        tracking=True,
        copy=False,
        help='Driver assigned by the Fleet Manager, fetched from the Employees app'
    )

    delegated_employee_id = fields.Many2one(
        'hr.employee',
        string='Driver Delegation',
        tracking=True,
        copy=False,
        help='Employee delegated to drive, fetched from the Employees app '
             '(chosen by the Fleet Manager when assigning a driver)'
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        readonly=True,
        tracking=True,
        copy=False,
        help='Vehicle currently driven by the assigned driver (automatic)'
    )

    # =========================================
    # Computes
    # =========================================

    @api.depends('employee_id', 'employee_id.name')
    def _compute_name(self):
        """Generate request reference"""
        for request in self:
            employee_name = request.employee_id.name or 'New'
            request.name = 'FR/%05d/%s' % (request.id or 0, employee_name)

    @api.depends('scheduled_start', 'scheduled_end')
    def _compute_duration(self):
        """Compute trip duration in hours"""
        for request in self:
            if request.scheduled_start and request.scheduled_end:
                delta = request.scheduled_end - request.scheduled_start
                request.duration = delta.total_seconds() / 3600.0
            else:
                request.duration = 0.0

    # =========================================
    # Constraints
    # =========================================

    @api.constrains('scheduled_start', 'scheduled_end')
    def _check_scheduled_dates(self):
        """Validate scheduled dates"""
        for request in self:
            if request.scheduled_start and request.scheduled_end:
                if request.scheduled_end < request.scheduled_start:
                    raise ValidationError(_('Scheduled end date/time cannot be before the scheduled start date/time'))

    @api.constrains('state', 'rejection_reason')
    def _check_rejection_state(self):
        """Rejection reason is mandatory when the request is rejected"""
        for request in self:
            if request.state == 'rejected' and not (request.rejection_reason or '').strip():
                raise ValidationError(_('Reason of rejection is mandatory when the request is rejected.'))

    @api.constrains('state', 'driver_id', 'vehicle_id')
    def _check_assigned_state(self):
        """A request can only be in the Assigned stage with a driver and vehicle"""
        for request in self:
            if request.state == 'assigned' and (not request.driver_id or not request.vehicle_id):
                raise ValidationError(_('A driver must be assigned to move the request to the Assigned stage.'))

    # =========================================
    # Helpers
    # =========================================

    def _is_department_manager(self):
        """Check if the current user is the manager of the requesting employee"""
        self.ensure_one()
        user_employee = self.env.user.employee_id
        department_manager = self.employee_id.department_id.manager_id
        return user_employee and user_employee in (self.employee_id.parent_id, department_manager)

    def _check_department_manager(self):
        if not self._is_department_manager() and not self.env.user.has_group('fleet_operations_pro.group_fleet_manager'):
            raise UserError(_('Only the department manager of the requesting employee can perform this action.'))

    def _check_fleet_manager(self):
        if not self.env.user.has_group('fleet_operations_pro.group_fleet_manager'):
            raise UserError(_('Only a Fleet Manager can perform this action.'))

    # =========================================
    # Workflow Actions
    # =========================================

    def action_submit(self):
        """Submit the request for approval"""
        for request in self:
            if request.state != 'draft':
                raise UserError(_('Only draft requests can be submitted.'))
            if not (request.scheduled_start and request.scheduled_end):
                raise UserError(_('Please set the scheduled date and time of the trip before submitting.'))
            if not request.purpose:
                raise UserError(_('Please fill in the purpose of the trip before submitting.'))
            if not request.pickup_location or not request.destination:
                raise UserError(_('Please fill in the pickup and destination before submitting.'))
            request.state = 'submitted'

    def action_dept_approve(self):
        """Department Manager approval"""
        for request in self:
            if request.state != 'submitted':
                raise UserError(_('Only submitted requests can be approved by the department manager.'))
            request._check_department_manager()
            request.state = 'dept_approved'

    def action_dept_reject(self):
        """Department Manager rejection (reason of rejection is mandatory)"""
        for request in self:
            if request.state != 'submitted':
                raise UserError(_('Only submitted requests can be rejected by the department manager.'))
            request._check_department_manager()
            if not (request.rejection_reason or '').strip():
                raise UserError(_('Reason of rejection is mandatory. Please fill in the reason of rejection.'))
            request.state = 'rejected'

    def action_fleet_approve(self):
        """Fleet Manager approval"""
        for request in self:
            if request.state != 'dept_approved':
                raise UserError(_('Only requests approved by the department manager can be approved by the fleet manager.'))
            request._check_fleet_manager()
            request.state = 'fleet_approved'

    def action_fleet_reject(self):
        """Fleet Manager rejection (reason of rejection is mandatory)"""
        for request in self:
            if request.state != 'dept_approved':
                raise UserError(_('Only requests approved by the department manager can be rejected by the fleet manager.'))
            request._check_fleet_manager()
            if not (request.rejection_reason or '').strip():
                raise UserError(_('Reason of rejection is mandatory. Please fill in the reason of rejection.'))
            request.state = 'rejected'

    def action_reset_draft(self):
        """Fleet Manager sends the request back to draft"""
        for request in self:
            if request.state not in ('submitted', 'dept_approved'):
                raise UserError(_('Only submitted or approved requests can be sent back to draft.'))
            request._check_fleet_manager()
            request.state = 'draft'

    @api.onchange('driver_id')
    def _onchange_driver_id(self):
        """When a driver is assigned, target the vehicle of the driver's current active assignment"""
        self.vehicle_id = self.driver_id and self._get_current_vehicle(self.driver_id.id) or False
        if self.driver_id and not self.vehicle_id:
            return {
                'warning': {
                    'title': _('No Vehicle Assigned'),
                    'message': _('This driver has no current active vehicle assignment. '
                                 'Assign a vehicle to the driver first.'),
                }
            }

    def _get_current_vehicle(self, employee_id):
        """Return the vehicle of the employee's current active assignment, if any"""
        assignment = self.env['fleet.driver.assignment'].search([
            ('employee_id', '=', employee_id),
            ('date_start', '<=', fields.Date.today()),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', fields.Date.today()),
        ], limit=1, order='date_start desc')
        return assignment.vehicle_id if assignment else self.env['fleet.vehicle']

    def action_assign(self):
        """Fleet Manager assigns a driver; the vehicle comes from the driver's current assignment"""
        for request in self:
            if request.state != 'fleet_approved':
                raise UserError(_('Only fleet-manager-approved requests can be assigned a driver.'))
            request._check_fleet_manager()
            if not request.driver_id:
                raise UserError(_('Please select a driver before assigning.'))
            vehicle = request._get_current_vehicle(request.driver_id.id)
            if not vehicle:
                raise UserError(_(
                    'The driver %s has no current active vehicle assignment. '
                    'Assign a vehicle to the driver first.') % request.driver_id.name)
            request.vehicle_id = vehicle
            request.state = 'assigned'
