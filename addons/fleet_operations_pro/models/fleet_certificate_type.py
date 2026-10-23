# -*- coding: utf-8 -*-

from odoo import models, fields, api


class FleetCertificateType(models.Model):
    """
    Model for different types of vehicle certificates.
    Examples: Registration, Insurance, Pollution, Fitness, Road Tax, Permits
    """
    _name = 'fleet.certificate.type'
    _description = 'Fleet Certificate Type'
    _order = 'sequence, name'
    
    name = fields.Char(
        string='Certificate Type',
        required=True,
        translate=True,
        help='Name of the certificate type (e.g., Registration, Insurance, PUC)'
    )
    
    code = fields.Char(
        string='Code',
        required=True,
        help='Short code for the certificate type'
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of this certificate type'
    )
    
    sequence = fields.Integer(
        string='Sequence',
        default=10,
        help='Order of display in lists'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to hide this certificate type'
    )
    
    reminder_days = fields.Integer(
        string='Reminder (Days Before Expiry)',
        default=30,
        help='Number of days before expiry to create reminder activities'
    )
    
    mandatory = fields.Boolean(
        string='Mandatory',
        default=True,
        help='Is this certificate mandatory for vehicle operation?'
    )
    
    requires_renewal = fields.Boolean(
        string='Requires Renewal',
        default=True,
        help='Does this certificate need periodic renewal?'
    )
    
    validity_period_months = fields.Integer(
        string='Validity Period (Months)',
        help='Standard validity period in months'
    )
    
    color = fields.Integer(
        string='Color Index',
        help='Color for display'
    )
    
    # Statistics
    certificate_count = fields.Integer(
        string='Certificates',
        compute='_compute_certificate_count'
    )
    
    @api.depends('name')
    def _compute_certificate_count(self):
        """Count certificates of this type"""
        for record in self:
            record.certificate_count = self.env['fleet.vehicle.certificate'].search_count([
                ('certificate_type_id', '=', record.id)
            ])
    
    _sql_constraints = [
        ('code_unique', 'UNIQUE(code)', 'Certificate type code must be unique!'),
    ]

