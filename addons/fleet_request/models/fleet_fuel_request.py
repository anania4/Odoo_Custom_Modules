# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import UserError


class FleetFuelRequest(models.Model):
    _name = 'fleet.fuel.request'
    _description = 'Fleet Fuel Request'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'request_date desc, id desc'

    name = fields.Char(
        string='Reference',
        default='/',
        copy=False,
        readonly=True,
        tracking=True
    )

    requested_by = fields.Many2one(
        'hr.employee',
        string='Requested By',
        required=True,
        tracking=True,
        default=lambda self: self.env.user.employee_id,
        help='Employee requesting fuel'
    )

    department_id = fields.Many2one(
        'hr.department',
        string='Department',
        related='requested_by.department_id',
        store=True,
        readonly=True
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        compute='_compute_vehicle_id',
        store=True,
        readonly=True,
        tracking=True,
        help='Vehicle currently assigned to the requested employee (automatic)'
    )

    fuel_type_id = fields.Many2one(
        'fleet.fuel.type',
        string='Fuel Type',
        related='vehicle_id.fuel_type_id',
        store=True,
        readonly=True
    )

    request_date = fields.Datetime(
        string='Request Date',
        default=fields.Datetime.now,
        required=True,
        readonly=True,
        tracking=True
    )

    receipt_no = fields.Char(
        string='Receipt No.',
        tracking=True,
        copy=False,
        help='Receipt number recorded by the Fuel Filler'
    )

    amount = fields.Monetary(
        string='Amount (ETB)',
        currency_field='currency_id',
        tracking=True,
        copy=False,
        help='Fuel payment amount recorded by the Fuel Filler'
    )

    filler_id = fields.Many2one(
        'res.users',
        string='Filled By',
        readonly=True,
        tracking=True,
        copy=False,
        help='Fuel Filler who marked the request as filled'
    )

    filled_date = fields.Datetime(
        string='Filled On',
        readonly=True,
        copy=False
    )

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

    line_ids = fields.One2many(
        'fleet.fuel.request.line',
        'request_id',
        string='Fuel Details',
        copy=True
    )

    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('submitted', 'Submitted'),
            ('approved', 'Approved'),
            ('filled', 'Filled'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False
    )

    can_edit_financials = fields.Boolean(
        string='Can Edit Financials',
        compute='_compute_can_edit_financials',
        help='Technical field used to restrict receipt and amount to the Fuel Filler'
    )

    notes = fields.Text(
        string='Notes'
    )

    @api.depends('requested_by')
    def _compute_vehicle_id(self):
        """Assign the vehicle of the employee's current active driver assignment"""
        for request in self:
            request.vehicle_id = request._get_current_vehicle(request.requested_by)

    def _get_current_vehicle(self, employee):
        if not employee:
            return self.env['fleet.vehicle']
        assignment = self.env['fleet.driver.assignment'].search([
            ('employee_id', '=', employee.id),
            ('date_start', '<=', fields.Date.today()),
            '|',
            ('date_end', '=', False),
            ('date_end', '>=', fields.Date.today()),
        ], limit=1, order='date_start desc')
        return assignment.vehicle_id

    @api.depends('state')
    @api.depends_context('uid')
    def _compute_can_edit_financials(self):
        is_filler = self.env.user.has_group('fleet_request.group_fuel_filler')
        for request in self:
            request.can_edit_financials = is_filler and request.state == 'approved'

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.fuel.request') or '/'
        return super().create(vals_list)

    def _check_fleet_manager(self):
        if not self.env.user.has_group('fleet_operations_pro.group_fleet_manager'):
            raise UserError(_('Only a Fleet Manager can perform this action.'))

    def _check_fuel_filler(self):
        if not self.env.user.has_group('fleet_request.group_fuel_filler'):
            raise UserError(_('Only a Fuel Filler can perform this action.'))

    def action_submit(self):
        """Employee submits the fuel request"""
        for request in self:
            if request.state != 'draft':
                raise UserError(_('Only draft fuel requests can be submitted.'))
            if not request.vehicle_id:
                raise UserError(_(
                    'No vehicle is assigned to %s. Assign a vehicle to the employee first.'
                ) % request.requested_by.name)
            if not request.line_ids:
                raise UserError(_('Please add at least one fuel detail line before submitting.'))
            for line in request.line_ids:
                if line.current_odometer <= 0:
                    raise UserError(_('Please enter the current odometer reading for every line.'))
                if line.current_odometer <= line.previous_odometer:
                    raise UserError(_(
                        'The current odometer (%(current)s km) must be greater than the previous '
                        'odometer (%(previous)s km) for vehicle %(vehicle)s.'
                    ) % {
                        'current': line.current_odometer,
                        'previous': line.previous_odometer,
                        'vehicle': request.vehicle_id.display_name,
                    })
            request.state = 'submitted'

    def action_approve(self):
        """Fleet Manager approves the request"""
        for request in self:
            request._check_fleet_manager()
            if request.state != 'submitted':
                raise UserError(_('Only submitted fuel requests can be approved.'))
            request.state = 'approved'

    def action_mark_filled(self):
        """Fuel Filler records quantity, amount and receipt and completes the request"""
        for request in self:
            request._check_fuel_filler()
            if request.state != 'approved':
                raise UserError(_('Only approved fuel requests can be marked as filled.'))
            if not request.receipt_no:
                raise UserError(_('Please enter the receipt number before marking the request as filled.'))
            if request.amount <= 0:
                raise UserError(_('Please enter the payment amount before marking the request as filled.'))
            if not request.line_ids:
                raise UserError(_('Please add at least one fuel detail line.'))

            total_filled = sum(request.line_ids.mapped('current_filled'))
            if total_filled <= 0:
                raise UserError(_('Please enter the current filled quantity for every line.'))
            for line in request.line_ids:
                if line.current_filled <= 0:
                    raise UserError(_('Please enter the current filled quantity for every line.'))
                if line.current_odometer <= 0:
                    raise UserError(_('Please enter the current odometer reading for every line.'))

            lines = request.line_ids.sorted('id')
            remaining_amount = request.amount
            for index, line in enumerate(lines):
                if index == len(lines) - 1:
                    line_amount = remaining_amount
                else:
                    line_amount = request.amount * line.current_filled / total_filled
                    remaining_amount -= line_amount

                # sudo: the filler may be restricted by driver record rules on fuel logs
                line.fuel_log_id = self.env['fleet.fuel.log'].sudo().create({
                    'vehicle_id': request.vehicle_id.id,
                    'driver_id': request.requested_by.id,
                    'date': fields.Date.today(),
                    'quantity': line.current_filled,
                    'total_cost': line_amount,
                    'odometer': line.current_odometer,
                    'invoice_reference': request.receipt_no,
                    'attachment': line.attachment,
                    'attachment_name': line.attachment_name,
                    'notes': request.notes or _('Created from fuel request %s') % request.name,
                    'fuel_request_line_id': line.id,
                })

            request.write({
                'state': 'filled',
                'filler_id': self.env.user.id,
                'filled_date': fields.Datetime.now(),
            })


class FleetFuelRequestLine(models.Model):
    _name = 'fleet.fuel.request.line'
    _description = 'Fleet Fuel Request Line'
    _order = 'id asc'

    request_id = fields.Many2one(
        'fleet.fuel.request',
        string='Fuel Request',
        required=True,
        ondelete='cascade'
    )

    request_state = fields.Selection(
        related='request_id.state',
        string='Request Status',
        readonly=True
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        related='request_id.vehicle_id',
        store=True,
        readonly=True
    )

    fuel_type_id = fields.Many2one(
        'fleet.fuel.type',
        string='Fuel Type',
        related='request_id.fuel_type_id',
        readonly=True
    )

    previous_filled = fields.Float(
        string='Previous Filled (L)',
        compute='_compute_previous_values',
        digits=(10, 2),
        help='Quantity filled in the previous fuel record'
    )

    previous_odometer = fields.Float(
        string='Previous Odometer (km)',
        compute='_compute_previous_values',
        digits=(10, 2),
        help='Odometer reading of the previous fuel record'
    )

    current_odometer = fields.Float(
        string='Current Odometer (km)',
        digits=(10, 2),
        help='Odometer reading entered by the driver'
    )

    km_difference = fields.Float(
        string='KM Difference (km)',
        compute='_compute_km_difference',
        digits=(10, 2),
        help='Current odometer minus previous odometer'
    )

    attachment = fields.Binary(
        string='Attachment',
        help='Odometer photo uploaded by the driver'
    )

    attachment_name = fields.Char(
        string='Attachment Name'
    )

    km_per_liter = fields.Float(
        string='KM/Liter',
        compute='_compute_km_per_liter',
        digits=(10, 2),
        help='KM difference divided by the previous filled quantity'
    )

    current_filled = fields.Float(
        string='Current Filled (L)',
        digits=(10, 2),
        help='Actual quantity filled, entered by the Fuel Filler'
    )

    can_edit_filled = fields.Boolean(
        string='Can Edit Filled Quantity',
        compute='_compute_can_edit_filled',
        help='Technical field used to restrict the filled quantity to the Fuel Filler'
    )

    fuel_log_id = fields.Many2one(
        'fleet.fuel.log',
        string='Fuel Log',
        readonly=True,
        copy=False
    )

    @api.depends(
        'request_id',
        'request_id.vehicle_id',
        'request_id.line_ids',
        'request_id.line_ids.current_odometer',
        'request_id.line_ids.current_filled',
    )
    def _compute_previous_values(self):
        for line in self:
            previous_line = line._get_previous_line()
            if previous_line:
                line.previous_odometer = previous_line.current_odometer or 0.0
                line.previous_filled = previous_line.current_filled or 0.0
                continue

            if line.fuel_log_id:
                previous_log = self.env['fleet.fuel.log'].search([
                    ('vehicle_id', '=', line.vehicle_id.id),
                    ('id', '<', line.fuel_log_id.id),
                ], limit=1, order='id desc')
            else:
                previous_log = self.env['fleet.fuel.log'].search([
                    ('vehicle_id', '=', line.vehicle_id.id),
                ], limit=1, order='date desc, id desc') if line.vehicle_id else self.env['fleet.fuel.log']

            if previous_log:
                line.previous_odometer = previous_log.odometer or 0.0
                line.previous_filled = previous_log.quantity or 0.0
            else:
                line.previous_odometer = line.vehicle_id.odometer or 0.0
                line.previous_filled = 0.0

    def _get_previous_line(self):
        self.ensure_one()
        if not self.request_id:
            return self.browse()
        lines = self.request_id.line_ids
        if not lines:
            return self.browse()
        if self.id in lines.ids:
            index = lines.ids.index(self.id)
            return lines[index - 1] if index > 0 else self.browse()
        return lines[-1]

    @api.depends('current_odometer', 'previous_odometer')
    def _compute_km_difference(self):
        for line in self:
            line.km_difference = (line.current_odometer or 0.0) - (line.previous_odometer or 0.0)

    @api.depends('km_difference', 'previous_filled')
    def _compute_km_per_liter(self):
        for line in self:
            if line.previous_filled:
                line.km_per_liter = line.km_difference / line.previous_filled
            else:
                line.km_per_liter = 0.0

    @api.depends('request_state')
    @api.depends_context('uid')
    def _compute_can_edit_filled(self):
        is_filler = self.env.user.has_group('fleet_request.group_fuel_filler')
        for line in self:
            line.can_edit_filled = is_filler and line.request_state == 'approved'


class FleetFuelLog(models.Model):
    _inherit = 'fleet.fuel.log'

    fuel_request_line_id = fields.Many2one(
        'fleet.fuel.request.line',
        string='Fuel Request Line',
        readonly=True,
        copy=False
    )
