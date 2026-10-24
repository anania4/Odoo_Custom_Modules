# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class FleetContract(models.Model):
    _name = 'fleet.contract'
    _description = 'Fleet Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc, id desc'

    name = fields.Char(
        string='Contract Reference',
        default='New',
        readonly=True,
        copy=False,
        help='Contract reference'
    )

    # Vehicle & Type
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        index=True,
        tracking=True,
        help='Vehicle covered by this contract'
    )

    contract_type = fields.Selection(
        [
            ('insurance', 'Insurance'),
            ('lease', 'Lease'),
            ('rental_agreement', 'Rental Agreement'),
            ('service_contract', 'Service Contract'),
            ('other', 'Other'),
        ],
        string='Contract Type',
        required=True,
        default='other',
        tracking=True,
        help='Type of contract (insurance policy, lease, rental agreement...)'
    )

    partner_id = fields.Many2one(
        'res.partner',
        string='Provider',
        tracking=True,
        help='Insurance company, lessor or service provider of this contract'
    )

    reference = fields.Char(
        string='External Reference',
        help='External reference given by the provider (policy number, lease number...)'
    )

    # Dates
    start_date = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date from which the contract is valid'
    )

    end_date = fields.Date(
        string='End Date',
        required=True,
        tracking=True,
        help='Date until which the contract is valid'
    )

    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_expiry',
        help='Days remaining before the contract end date (negative if past)'
    )

    expiring_alert = fields.Boolean(
        string='Expiring Soon',
        compute='_compute_expiry',
        help='True if the contract expires within 30 days'
    )

    # Cost
    cost = fields.Monetary(
        string='Contract Cost',
        currency_field='currency_id',
        tracking=True,
        help='Total cost of the contract'
    )

    recurring_cost = fields.Monetary(
        string='Recurring Cost',
        currency_field='currency_id',
        help='Cost to renew/be paid at each recurring interval'
    )

    cost_frequency = fields.Selection(
        [
            ('none', 'One-time'),
            ('monthly', 'Monthly'),
            ('quarterly', 'Quarterly'),
            ('yearly', 'Yearly'),
        ],
        string='Billing Frequency',
        default='none',
        help='How often the recurring cost is billed or renewed'
    )

    # State
    state = fields.Selection(
        [
            ('draft', 'Draft'),
            ('running', 'Running'),
            ('expired', 'Expired'),
            ('cancelled', 'Cancelled'),
        ],
        string='State',
        default='draft',
        required=True,
        tracking=True,
        copy=False,
        help='Current stage of the contract'
    )

    # Related
    service_ids = fields.One2many(
        'fleet.service',
        'contract_id',
        string='Services',
        help='Services billed under this contract'
    )

    service_count = fields.Integer(
        string='Services',
        compute='_compute_service_count',
        help='Number of services under this contract'
    )

    # Notes
    notes = fields.Text(
        string='Notes',
        help='Additional terms or notes about this contract'
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
        required=True,
        default=lambda self: self.env.company.currency_id
    )

    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the contract'
    )

    _type_prefixes = {
        'insurance': 'INS',
        'lease': 'LSE',
        'rental_agreement': 'RNT',
        'service_contract': 'SVT',
        'other': 'CTR',
    }

    _sql_constraints = [
        ('contract_dates', 'CHECK(end_date >= start_date)', 'End date cannot be before the start date!'),
        ('cost_positive', 'CHECK(cost >= 0)', 'Contract cost must be positive!'),
    ]

    @api.model_create_multi
    def create(self, vals_list):
        """Assign the contract reference from the sequence, prefixed by contract type"""
        for vals in vals_list:
            if not vals.get('name') or vals['name'] == 'New':
                prefix = self._type_prefixes.get(vals.get('contract_type', 'other'), 'CTR')
                seq = self.env['ir.sequence'].next_by_code('fleet.contract') or '00000'
                vals['name'] = f"{prefix}/{seq}"
        return super().create(vals_list)

    @api.depends('end_date')
    def _compute_expiry(self):
        """Compute days until expiry and expiring flag"""
        today = fields.Date.today()
        for contract in self:
            if contract.end_date:
                contract.days_until_expiry = (contract.end_date - today).days
                contract.expiring_alert = 0 <= contract.days_until_expiry <= 30
            else:
                contract.days_until_expiry = 0
                contract.expiring_alert = False

    @api.depends('service_ids')
    def _compute_service_count(self):
        """Count services under this contract"""
        for contract in self:
            contract.service_count = len(contract.service_ids)

    # Constraints
    @api.constrains('cost')
    def _check_cost(self):
        for contract in self:
            if contract.cost < 0 or contract.recurring_cost < 0:
                raise ValidationError(_('Contract costs cannot be negative!'))

    # Actions
    def action_run(self):
        """Move the contract to running"""
        for contract in self:
            if contract.state != 'draft':
                raise ValidationError(_('Only draft contracts can be set to running.'))
            contract.state = 'running'

    def action_cancel(self):
        """Cancel the contract"""
        for contract in self:
            if contract.state == 'cancelled':
                raise ValidationError(_('This contract is already cancelled.'))
            contract.state = 'cancelled'

    def action_set_expired(self):
        """Mark the contract as expired"""
        for contract in self:
            if contract.state not in ('draft', 'running'):
                raise ValidationError(_('Only draft or running contracts can be expired.'))
            contract.state = 'expired'

    def action_view_services(self):
        """Open the services linked to this contract"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Services'),
            'res_model': 'fleet.service',
            'view_mode': 'list,form',
            'domain': [('contract_id', '=', self.id)],
            'context': {'default_contract_id': self.id, 'default_vehicle_id': self.vehicle_id.id},
        }
