# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class FleetInsurance(models.Model):
    _name = 'fleet.insurance'
    _description = 'Fleet Insurance Policy'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'start_date desc'
    
    name = fields.Char(
        string='Policy Reference',
        required=True,
        copy=False,
        default='/',
        help='Insurance policy reference number'
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Vehicle covered by this policy'
    )
    
    policy_number = fields.Char(
        string='Policy Number',
        required=True,
        tracking=True,
        help='Insurance policy number from provider'
    )
    
    insurance_company = fields.Char(
        string='Insurance Company',
        required=True,
        tracking=True,
        help='Name of insurance provider'
    )
    
    policy_type = fields.Selection([
        ('comprehensive', 'Comprehensive'),
        ('third_party', 'Third Party'),
        ('collision', 'Collision'),
        ('liability', 'Liability Only'),
    ], string='Policy Type', required=True, default='comprehensive', tracking=True)
    
    # Dates
    start_date = fields.Date(
        string='Policy Start Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True
    )
    
    end_date = fields.Date(
        string='Policy End Date',
        required=True,
        tracking=True
    )
    
    is_expired = fields.Boolean(
        string='Expired',
        compute='_compute_is_expired',
        store=False
    )
    
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_days_until_expiry',
        store=False
    )
    
    # Financial Details
    premium_amount = fields.Monetary(
        string='Premium Amount',
        required=True,
        tracking=True,
        currency_field='currency_id',
        help='Insurance premium cost'
    )
    
    coverage_amount = fields.Monetary(
        string='Coverage Amount',
        tracking=True,
        currency_field='currency_id',
        help='Maximum coverage provided'
    )
    
    deductible = fields.Monetary(
        string='Deductible',
        tracking=True,
        currency_field='currency_id',
        help='Amount to be paid before insurance covers'
    )
    
    # Documents
    policy_document = fields.Binary(
        string='Policy Document',
        help='Upload insurance policy document'
    )
    
    policy_document_filename = fields.Char(string='Filename')
    
    # Additional Details
    agent_name = fields.Char(string='Insurance Agent')
    agent_phone = fields.Char(string='Agent Phone')
    agent_email = fields.Char(string='Agent Email')
    
    notes = fields.Text(string='Notes')
    
    # Status
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive this policy'
    )
    
    is_current = fields.Boolean(
        string='Current Policy',
        compute='_compute_is_current',
        store=False,
        help='Whether this is the currently active policy'
    )
    
    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True
    )
    
    _sql_constraints = [
        ('policy_number_unique', 'UNIQUE(policy_number, insurance_company)',
         'Policy number must be unique per insurance company!'),
    ]
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence number for insurance policy - batch optimized"""
        for vals in vals_list:
            if vals.get('name', '/') == '/':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.insurance') or '/'
        return super().create(vals_list)
    
    @api.depends('end_date')
    def _compute_is_expired(self):
        """Check if policy is expired"""
        today = fields.Date.today()
        for policy in self:
            policy.is_expired = policy.end_date < today if policy.end_date else False
    
    @api.depends('end_date')
    def _compute_days_until_expiry(self):
        """Calculate days until policy expires"""
        today = fields.Date.today()
        for policy in self:
            if policy.end_date:
                delta = (policy.end_date - today).days
                policy.days_until_expiry = delta
            else:
                policy.days_until_expiry = 0
    
    @api.depends('start_date', 'end_date', 'vehicle_id')
    def _compute_is_current(self):
        """Check if this is the current active policy"""
        today = fields.Date.today()
        for policy in self:
            policy.is_current = (
                policy.start_date <= today <= policy.end_date
                if policy.start_date and policy.end_date else False
            )
    
    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        """Validate date range"""
        for policy in self:
            if policy.start_date and policy.end_date:
                if policy.start_date > policy.end_date:
                    raise ValidationError(_('End date must be after start date!'))
    
    @api.model
    def _cron_check_insurance_expiry(self):
        """
        Scheduled action to check for expiring insurance policies
        Creates activities for policies expiring in 30, 60, 90 days
        """
        today = fields.Date.today()
        reminder_periods = [30, 60, 90]
        
        for days in reminder_periods:
            reminder_date = today + timedelta(days=days)
            
            # Find policies expiring on this date
            expiring_policies = self.search([
                ('end_date', '=', reminder_date),
                ('active', '=', True),
            ])
            
            for policy in expiring_policies:
                # Check if activity already exists
                existing_activity = self.env['mail.activity'].search([
                    ('res_model', '=', 'fleet.insurance'),
                    ('res_id', '=', policy.id),
                    ('summary', 'ilike', 'Insurance Policy Expiry'),
                ], limit=1)
                
                if not existing_activity:
                    activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
                    
                    policy.activity_schedule(
                        activity_type_id=activity_type.id if activity_type else False,
                        summary=f"Insurance Policy Expiry: {policy.name}",
                        note=f"Vehicle: {policy.vehicle_id.name}\n"
                             f"Policy: {policy.policy_number}\n"
                             f"Provider: {policy.insurance_company}\n"
                             f"Expiry Date: {policy.end_date}\n"
                             f"Days until expiry: {days}",
                        date_deadline=policy.end_date - timedelta(days=7),
                    )
    
    def action_renew_policy(self):
        """Create a new policy based on current one"""
        self.ensure_one()
        
        return {
            'name': _('Renew Insurance Policy'),
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.insurance',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_vehicle_id': self.vehicle_id.id,
                'default_insurance_company': self.insurance_company,
                'default_policy_type': self.policy_type,
                'default_start_date': self.end_date + timedelta(days=1),
                'default_premium_amount': self.premium_amount,
                'default_coverage_amount': self.coverage_amount,
                'default_deductible': self.deductible,
                'default_agent_name': self.agent_name,
                'default_agent_phone': self.agent_phone,
                'default_agent_email': self.agent_email,
            }
        }

