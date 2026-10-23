# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class FleetNotificationConfig(models.Model):
    _name = 'fleet.notification.config'
    _description = 'Fleet Notification Configuration'
    _order = 'notification_type, sequence'
    
    name = fields.Char(
        string='Name',
        compute='_compute_name',
        store=True,
        help='Configuration name'
    )
    
    notification_type = fields.Selection(
        [
            ('certificate_expiry', 'Certificate Expiry'),
            ('license_expiry', 'Driver License Expiry'),
            ('rental_start', 'Rental Contract Start'),
            ('rental_end', 'Rental Contract End'),
        ],
        string='Notification Type',
        required=True,
        help='Type of notification'
    )
    
    lead_days = fields.Integer(
        string='Lead Days',
        required=True,
        default=30,
        help='Number of days before event to create reminder'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to disable this notification'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Sequence for ordering'
    )
    
    activity_type_id = fields.Many2one(
        'mail.activity.type',
        string='Activity Type',
        help='Type of activity to create for this notification'
    )
    
    user_id = fields.Many2one(
        'res.users',
        string='Assigned To',
        help='User to assign activity to (if not specified, will assign to responsible user)'
    )
    
    summary_template = fields.Char(
        string='Summary Template',
        help='Template for activity summary (use {field_name} for variables)'
    )
    
    note_template = fields.Text(
        string='Note Template',
        help='Template for activity note (use {field_name} for variables)'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company this configuration belongs to'
    )
    
    _sql_constraints = [
        ('lead_days_positive', 'CHECK(lead_days > 0)', 'Lead days must be positive!'),
    ]
    
    @api.depends('notification_type', 'lead_days')
    def _compute_name(self):
        """Generate configuration name"""
        type_names = dict(self._fields['notification_type'].selection)
        for record in self:
            if record.notification_type:
                record.name = f"{type_names.get(record.notification_type)} - {record.lead_days} days before"
            else:
                record.name = 'New Configuration'

