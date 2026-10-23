# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from datetime import timedelta


class FleetVehicleCertificate(models.Model):
    """
    Model for tracking vehicle certificates and their expiry dates.
    Includes automatic alerts and reminder activities.
    """
    _name = 'fleet.vehicle.certificate'
    _description = 'Fleet Vehicle Certificate'
    _order = 'expiry_date asc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string='Certificate Number',
        required=True,
        tracking=True,
        help='Certificate or document number'
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Vehicle for which this certificate is issued'
    )
    
    certificate_type_id = fields.Many2one(
        'fleet.certificate.type',
        string='Certificate Type',
        required=True,
        tracking=True,
        help='Type of certificate'
    )
    
    issue_date = fields.Date(
        string='Issue Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date when the certificate was issued'
    )
    
    expiry_date = fields.Date(
        string='Expiry Date',
        required=True,
        tracking=True,
        help='Date when the certificate expires'
    )
    
    issuing_authority = fields.Char(
        string='Issuing Authority',
        help='Authority or organization that issued the certificate'
    )
    
    issuing_location = fields.Char(
        string='Issuing Location',
        help='Location where the certificate was issued'
    )
    
    description = fields.Text(
        string='Description',
        help='Additional details about the certificate'
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_certificate_attachment_rel',
        'certificate_id',
        'attachment_id',
        string='Attachments',
        help='Attach scanned copies of certificates'
    )
    
    state = fields.Selection([
        ('valid', 'Valid'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('renewed', 'Renewed'),
    ], string='Status', compute='_compute_state', store=True, tracking=True)
    
    days_until_expiry = fields.Integer(
        string='Days Until Expiry',
        compute='_compute_days_until_expiry',
        store=True,
        help='Number of days until this certificate expires'
    )
    
    renewal_cost = fields.Monetary(
        string='Renewal Cost',
        currency_field='currency_id',
        help='Cost for renewing this certificate'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        default=lambda self: self.env.company.currency_id
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    renewal_certificate_id = fields.Many2one(
        'fleet.vehicle.certificate',
        string='Renewed By',
        readonly=True,
        help='The new certificate that renewed this one'
    )
    
    previous_certificate_id = fields.Many2one(
        'fleet.vehicle.certificate',
        string='Renews Certificate',
        help='The previous certificate that this one renews'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes or comments'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Uncheck to archive this certificate'
    )
    
    @api.depends('expiry_date')
    def _compute_days_until_expiry(self):
        """Calculate days until expiry"""
        today = fields.Date.today()
        for record in self:
            if record.expiry_date:
                delta = record.expiry_date - today
                record.days_until_expiry = delta.days
            else:
                record.days_until_expiry = 0
    
    @api.depends('expiry_date', 'days_until_expiry', 'renewal_certificate_id')
    def _compute_state(self):
        """Determine certificate status based on expiry date"""
        today = fields.Date.today()
        for record in self:
            if record.renewal_certificate_id:
                record.state = 'renewed'
            elif not record.expiry_date:
                record.state = 'valid'
            elif record.expiry_date < today:
                record.state = 'expired'
            elif record.days_until_expiry <= (record.certificate_type_id.reminder_days or 30):
                record.state = 'expiring_soon'
            else:
                record.state = 'valid'
    
    @api.constrains('issue_date', 'expiry_date')
    def _check_dates(self):
        """Validate issue and expiry dates"""
        for record in self:
            if record.issue_date and record.expiry_date:
                if record.expiry_date <= record.issue_date:
                    raise ValidationError(_('Expiry date must be after issue date!'))
    
    def action_renew_certificate(self):
        """Create a new certificate as renewal of this one"""
        self.ensure_one()
        
        # Calculate new dates
        validity_months = self.certificate_type_id.validity_period_months or 12
        new_issue_date = fields.Date.today()
        new_expiry_date = new_issue_date + timedelta(days=validity_months * 30)
        
        # Create new certificate
        new_cert = self.copy({
            'name': self.name + ' (Renewed)',
            'issue_date': new_issue_date,
            'expiry_date': new_expiry_date,
            'previous_certificate_id': self.id,
            'renewal_certificate_id': False,
        })
        
        # Link back to this certificate
        self.renewal_certificate_id = new_cert.id
        
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'fleet.vehicle.certificate',
            'res_id': new_cert.id,
            'view_mode': 'form',
            'target': 'current',
        }
    
    @api.model
    def _cron_check_certificate_expiry(self):
        """
        Cron job to check for expiring certificates and create activity reminders.
        Should be scheduled to run daily.
        """
        today = fields.Date.today()
        
        # Find certificates that are expiring soon and don't have activities
        certificates = self.search([
            ('state', 'in', ['valid', 'expiring_soon']),
            ('expiry_date', '!=', False),
            ('active', '=', True),
        ])
        
        for cert in certificates:
            reminder_days = cert.certificate_type_id.reminder_days or 30
            reminder_date = cert.expiry_date - timedelta(days=reminder_days)
            
            if today >= reminder_date and today < cert.expiry_date:
                # Check if activity already exists
                existing_activity = self.env['mail.activity'].search([
                    ('res_model', '=', 'fleet.vehicle.certificate'),
                    ('res_id', '=', cert.id),
                    ('summary', 'like', 'Certificate Expiry')
                ], limit=1)
                
                if not existing_activity:
                    # Create activity reminder
                    self.env['mail.activity'].create({
                        'res_model_id': self.env['ir.model']._get_id('fleet.vehicle.certificate'),
                        'res_id': cert.id,
                        'activity_type_id': self.env.ref('mail.mail_activity_data_todo').id,
                        'summary': f'Certificate Expiry Reminder: {cert.certificate_type_id.name}',
                        'note': f'Certificate {cert.name} for vehicle {cert.vehicle_id.name} will expire on {cert.expiry_date}. Please arrange for renewal.',
                        'date_deadline': cert.expiry_date - timedelta(days=7),
                    })

