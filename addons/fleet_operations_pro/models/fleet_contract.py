# -*- coding: utf-8 -*-

from dateutil.relativedelta import relativedelta

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetContractType(models.Model):
    _name = 'fleet.contract.type'
    _description = 'Vehicle Agreement Type'
    _order = 'sequence, name'

    name = fields.Char(string='Agreement Type', required=True, translate=True)
    prefix = fields.Char(
        string='Reference Prefix',
        required=True,
        help='Start of the vehicle agreement reference, e.g. INS gives INS/2026/00001'
    )
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('name_unique', 'unique(name)', 'This vehicle agreement type already exists!'),
    ]

    @api.onchange('name')
    def _onchange_name(self):
        if self.name and not self.prefix:
            self.prefix = self.name[:3].upper()


class FleetContract(models.Model):
    _name = 'fleet.contract'
    _description = 'Vehicle Agreement'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Reference',
        default='New',
        readonly=True,
        copy=False,
        help='Vehicle Agreement reference'
    )

    # Vehicle & Type
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help='Vehicle covered by this vehicle agreement'
    )
    contract_type_id = fields.Many2one(
        'fleet.contract.type',
        string='Agreement Type',
        required=True,
        ondelete='restrict',
        tracking=True,
        help='Configured in Configuration > Agreement Types. '
             'Vehicle rentals are recorded on the vehicle (Ownership > Rental Terms).'
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain=lambda self: self.env['res.partner']._fleet_vendor_domain(),
        tracking=True,
        help='Insurance company, lessor or service provider of this vehicle agreement'
    )
    reference = fields.Char(
        string='Vendor Reference / Policy No',
        tracking=True,
        help='Reference given by the vendor (policy number, lease number...)'
    )
    user_id = fields.Many2one(
        'res.users',
        string='Responsible',
        default=lambda self: self.env.user,
        tracking=True,
        help='Person responsible for this vehicle agreement; receives the expiry reminder'
    )

    # Dates
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        tracking=True
    )
    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True
    )
    reminder_days = fields.Integer(
        string='Reminder Days Before Expiry',
        default=30,
        help='An activity is created for the responsible person this many days before the end date'
    )
    reminder_sent = fields.Boolean(
        string='Reminder Sent',
        copy=False
    )
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_expiry',
        help='Days remaining before the vehicle agreement end date (negative if past)'
    )
    expiring_alert = fields.Boolean(
        string='Expiring Soon',
        compute='_compute_expiry',
        help='True if the vehicle agreement ends within its reminder period'
    )

    # Cost & Payment
    currency_id = fields.Many2one(
        'res.currency',
        related='company_id.currency_id',
        string='Currency'
    )
    cost = fields.Monetary(
        string='Recurring Cost',
        currency_field='currency_id',
        tracking=True,
        help='Amount due each period (or the full amount when there is no recurring frequency)'
    )
    cost_frequency = fields.Selection(
        [
            ('monthly', 'Monthly'),
            ('yearly', 'Yearly'),
        ],
        string='Recurring Cost Frequency',
        tracking=True,
        help='Leave empty for a one-time payment'
    )
    total_cost = fields.Monetary(
        string='Estimated Total Cost',
        currency_field='currency_id',
        compute='_compute_total_cost',
        help='Recurring cost multiplied by the number of periods between start and end date'
    )
    deposit = fields.Monetary(
        string='Deposit',
        currency_field='currency_id',
        tracking=True
    )
    next_due_date = fields.Date(
        string='Next Due Date',
        compute='_compute_next_due_date',
        help='Next recurring payment date: the start date repeated every month/year, '
             'from today until the end date'
    )
    days_until_due = fields.Integer(
        string='Days Until Next Payment',
        compute='_compute_next_due_date',
    )

    # State
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('running', 'Running'),
            ('expired', 'Expired'),
            ('closed', 'Closed'),
        ],
        string='Status',
        default='draft',
        required=True,
        tracking=True,
        copy=False
    )

    # Related
    service_ids = fields.One2many(
        'fleet.service',
        'contract_id',
        string='Services',
        help='Services billed under this vehicle agreement'
    )
    service_count = fields.Integer(
        string='Service Count',
        compute='_compute_service_count'
    )

    notes = fields.Text(string='Notes')
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_contract_attachment_rel',
        'contract_id',
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
        ('contract_dates', 'CHECK(end_date >= start_date)', 'End date cannot be before the start date!'),
        ('reminder_days_positive', 'CHECK(reminder_days >= 0)', 'Reminder days cannot be negative!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Reference = contract type prefix + sequence, e.g. INS/2026/00001"""
        ContractType = self.env['fleet.contract.type']
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                prefix = ContractType.browse(vals.get('contract_type_id')).prefix or 'CTR'
                seq = self.env['ir.sequence'].next_by_code('fleet.contract') or '00000'
                vals['name'] = f"{prefix}/{seq}"
        return super().create(vals_list)

    def write(self, vals):
        # A new end date or reminder period means the reminder must be sent again
        if 'end_date' in vals or 'reminder_days' in vals:
            vals = dict(vals, reminder_sent=False)
        return super().write(vals)

    @api.depends('end_date', 'reminder_days')
    def _compute_expiry(self):
        today = fields.Date.today()
        for contract in self:
            if contract.end_date:
                contract.days_until_expiry = (contract.end_date - today).days
                contract.expiring_alert = 0 <= contract.days_until_expiry <= contract.reminder_days
            else:
                contract.days_until_expiry = 0
                contract.expiring_alert = False

    @api.depends('cost', 'cost_frequency', 'start_date', 'end_date')
    def _compute_total_cost(self):
        for contract in self:
            if not contract.cost_frequency or not (contract.start_date and contract.end_date):
                contract.total_cost = contract.cost
                continue
            # Count the periods started between start and end date (inclusive)
            delta = relativedelta(contract.end_date + relativedelta(days=1), contract.start_date)
            months = delta.years * 12 + delta.months + (1 if delta.days else 0)
            if contract.cost_frequency == 'yearly':
                periods = -(-months // 12)
            else:
                periods = months
            contract.total_cost = contract.cost * max(periods, 1)

    @api.depends('service_ids')
    def _compute_service_count(self):
        for contract in self:
            contract.service_count = len(contract.service_ids)

    def _period_delta(self):
        self.ensure_one()
        return relativedelta(years=1) if self.cost_frequency == 'yearly' else relativedelta(months=1)

    @api.depends('cost_frequency', 'start_date', 'end_date', 'state')
    def _compute_next_due_date(self):
        today = fields.Date.context_today(self)
        for contract in self:
            due = False
            if contract.cost_frequency and contract.start_date and contract.state in ('draft', 'running'):
                step, n = contract._period_delta(), 0
                candidate = contract.start_date
                while candidate < today:
                    n += 1
                    candidate = contract.start_date + step * n
                if not contract.end_date or candidate <= contract.end_date:
                    due = candidate
            contract.next_due_date = due
            contract.days_until_due = (due - today).days if due else 0

    # Actions
    def action_run(self):
        for contract in self:
            if contract.state != 'draft':
                raise ValidationError(_('Only draft vehicle agreements can be set to running.'))
            contract.state = 'running'

    def action_close(self):
        for contract in self:
            if contract.state == 'closed':
                raise ValidationError(_('This vehicle agreement is already closed.'))
            contract.state = 'closed'

    def action_set_expired(self):
        for contract in self:
            if contract.state not in ('draft', 'running'):
                raise ValidationError(_('Only draft or running vehicle agreements can be expired.'))
            contract.state = 'expired'

    def action_reset_draft(self):
        self.write({'state': 'draft'})

    def action_view_services(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Services'),
            'res_model': 'fleet.service',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id, 'default_vehicle_id': self.vehicle_id.id},
        }

    @api.model
    def _cron_check_contracts(self):
        """Daily: expire running contracts past their end date and send expiry reminders."""
        today = fields.Date.today()
        self.search([
            ('state', '=', 'running'),
            ('end_date', '<', today),
        ]).write({'state': 'expired'})

        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        to_remind = self.search([
            ('state', '=', 'running'),
            ('reminder_sent', '=', False),
            ('end_date', '>=', today),
        ]).filtered(lambda c: (c.end_date - today).days <= c.reminder_days)
        for contract in to_remind:
            contract.activity_schedule(
                activity_type_id=activity_type.id if activity_type else False,
                date_deadline=contract.end_date,
                summary=_('Vehicle Agreement %s expires on %s') % (contract.name, contract.end_date),
                note=_('Vehicle Agreement %(name)s for vehicle %(vehicle)s ends on %(date)s. Renew or close it.',
                       name=contract.name, vehicle=contract.vehicle_id.display_name, date=contract.end_date),
                user_id=(contract.user_id or self.env.user).id,
            )
            contract.reminder_sent = True
