# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetService(models.Model):
    _name = 'fleet.service'
    _description = 'Fleet Service'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        default='New',
        readonly=True,
        copy=False
    )
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True
    )
    service_type_id = fields.Many2one(
        'fleet.maintenance.type',
        string='Service Type',
        required=True,
        tracking=True
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain=lambda self: self.env['res.partner']._fleet_vendor_domain(),
        tracking=True,
        help='Garage, vendor or workshop performing the service'
    )
    inspection_center_id = fields.Many2one(
        'res.partner',
        string='Inspection Center',
        tracking=True,
        domain=lambda self: self.env['res.partner']._fleet_vendor_domain(),
        help='Inspection center where the vehicle is inspected, chosen from your vendors'
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True
    )
    contract_id = fields.Many2one(
        'fleet.contract',
        string='Vehicle Agreement',
        ondelete='set null',
        index=True,
        tracking=True,
        help='Vehicle Agreement covering this service (if billed under a vehicle agreement)'
    )

    # Dates
    date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    end_date = fields.Date(
        string='End Date',
        tracking=True,
        copy=False,
        help='Date the service was completed'
    )

    # Cost
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency'
    )
    cost = fields.Monetary(
        string='Cost',
        currency_field='currency_id',
        tracking=True
    )

    state = fields.Selection(
        [
            ('new', 'New'),
            ('running', 'Running'),
            ('done', 'Done'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='new',
        required=True,
        tracking=True,
        copy=False
    )

    # Service details
    odometer = fields.Float(
        string='Odometer at Service (km)',
        tracking=True
    )
    interval_type = fields.Selection(
        [
            ('one_time', 'One-time'),
            ('recurring', 'Recurring'),
        ],
        string='Service Interval Type',
        default='one_time',
        required=True,
        tracking=True,
        help='One-time: the interval only sets the next due km of this service.\n'
             'Recurring: every next service of this type on this vehicle takes the same '
             'interval automatically, so it is due again every interval, until set back to One-time.'
    )
    service_interval = fields.Float(
        string='Service Interval (km)',
        tracking=True,
        help='Distance until this service is due again'
    )
    next_service_odometer = fields.Float(
        string='Next Service Due (km)',
        compute='_compute_next_service_odometer',
        store=True,
        help='Odometer at service + service interval'
    )
    description = fields.Text(string='Description of Work')
    notes = fields.Text(string='Notes')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_service_attachment_rel',
        'service_id',
        'attachment_id',
        string='Attachments'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    active = fields.Boolean(
        string='Active',
        default=True
    )

    _sql_constraints = [
        ('service_odometer_positive', 'CHECK(odometer >= 0)', 'Odometer reading must be positive!'),
        ('service_interval_positive', 'CHECK(service_interval >= 0)', 'Service interval must be positive!'),
        ('service_dates', 'CHECK(end_date IS NULL OR end_date >= date)', 'End date cannot be before the start date!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.service') or 'New'
            # Recurring interval carried forward even when the form onchange did not run (imports, code)
            if 'interval_type' not in vals and not vals.get('service_interval'):
                previous = self._last_recurring_service(vals.get('vehicle_id'), vals.get('service_type_id'))
                if previous:
                    vals.update(interval_type='recurring', service_interval=previous.service_interval)
        services = super().create(vals_list)
        services.filtered(lambda s: s.state == 'done')._update_vehicle_odometer()
        return services

    def write(self, vals):
        result = super().write(vals)
        if {'state', 'odometer', 'end_date'} & set(vals):
            self.filtered(lambda s: s.state == 'done')._update_vehicle_odometer()
        return result

    @api.depends('odometer', 'service_interval')
    def _compute_next_service_odometer(self):
        for service in self:
            service.next_service_odometer = (
                service.odometer + service.service_interval if service.service_interval else 0.0
            )

    @api.onchange('vehicle_id')
    def _onchange_vehicle_id(self):
        if self.vehicle_id and not self.odometer:
            self.odometer = self.vehicle_id.odometer

    @api.onchange('vehicle_id', 'service_type_id')
    def _onchange_recurring_interval(self):
        """Take the interval of the last recurring service of this type on this vehicle"""
        if self.state != 'new' or self.service_interval:
            return
        previous = self._last_recurring_service(self.vehicle_id.id, self.service_type_id.id)
        if previous:
            self.interval_type = 'recurring'
            self.service_interval = previous.service_interval

    @api.model
    def _last_recurring_service(self, vehicle_id, service_type_id):
        """Latest done service of this vehicle and type, if it is recurring"""
        if not (vehicle_id and service_type_id):
            return self.browse()
        last = self.search([
            ('vehicle_id', '=', vehicle_id),
            ('service_type_id', '=', service_type_id),
            ('state', '=', 'done'),
        ], order='end_date desc, odometer desc, id desc', limit=1)
        if last.interval_type == 'recurring' and last.service_interval:
            return last
        return self.browse()

    @api.constrains('interval_type', 'service_interval')
    def _check_recurring_interval(self):
        for service in self:
            if service.interval_type == 'recurring' and service.service_interval <= 0:
                raise ValidationError(_(
                    'Service %s is recurring: please set its Service Interval (km).') % service.name)

    @api.constrains('contract_id', 'vehicle_id')
    def _check_contract_vehicle(self):
        """A service under a contract must be for the contract's vehicle"""
        for service in self:
            if service.contract_id and service.vehicle_id and \
                    service.contract_id.vehicle_id != service.vehicle_id:
                raise ValidationError(_(
                    'The vehicle agreement %s is for vehicle %s, not for vehicle %s.'
                ) % (service.contract_id.name,
                     service.contract_id.vehicle_id.display_name,
                     service.vehicle_id.display_name))

    @api.constrains('state', 'end_date')
    def _check_end_date_done(self):
        for service in self:
            if service.state == 'done' and not service.end_date:
                raise ValidationError(_('Please set the End Date before marking service %s as done.') % service.name)

    def _update_vehicle_odometer(self):
        """A completed service gives the latest odometer reading of the vehicle"""
        for service in self:
            vehicle = service.vehicle_id
            if vehicle and service.odometer > (vehicle.odometer or 0.0):
                vehicle.write({
                    'odometer': service.odometer,
                    'odometer_date': service.end_date or service.date,
                })

    # Actions
    def action_start(self):
        for service in self:
            if service.state != 'new':
                raise ValidationError(_('Only new services can be started.'))
        self.write({'state': 'running'})

    def action_done(self):
        for service in self:
            if service.state not in ('new', 'running'):
                raise ValidationError(_('Only new or running services can be marked as done.'))
            service.write({
                'state': 'done',
                'end_date': service.end_date or fields.Date.today(),
            })

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def action_reset_new(self):
        self.write({'state': 'new'})
