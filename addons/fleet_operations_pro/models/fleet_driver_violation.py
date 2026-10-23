# -*- coding: utf-8 -*-

from odoo import models, fields, api, _


class FleetDriverViolation(models.Model):
    _name = 'fleet.driver.violation'
    _description = 'Driver Violation'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        help='Violation reference number'
    )
    
    driver_id = fields.Many2one(
        'fleet.driver',
        string='Driver',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Driver who committed the violation'
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        tracking=True,
        help='Vehicle involved in the violation'
    )
    
    violation_type = fields.Selection(
        [
            ('speeding', 'Speeding'),
            ('traffic_light', 'Traffic Light Violation'),
            ('parking', 'Parking Violation'),
            ('accident', 'Accident'),
            ('reckless_driving', 'Reckless Driving'),
            ('dui', 'DUI/DWI'),
            ('seat_belt', 'Seat Belt Violation'),
            ('phone_use', 'Phone Use While Driving'),
            ('lane_violation', 'Lane Violation'),
            ('other', 'Other'),
        ],
        string='Violation Type',
        required=True,
        tracking=True,
        help='Type of violation'
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date of violation'
    )
    
    location = fields.Char(
        string='Location',
        help='Location where violation occurred'
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of the violation'
    )
    
    severity = fields.Selection(
        [
            ('minor', 'Minor'),
            ('moderate', 'Moderate'),
            ('major', 'Major'),
            ('critical', 'Critical'),
        ],
        string='Severity',
        required=True,
        default='moderate',
        tracking=True,
        help='Severity of the violation'
    )
    
    fine_amount = fields.Monetary(
        string='Fine Amount',
        currency_field='currency_id',
        tracking=True,
        help='Fine amount for this violation'
    )
    
    points = fields.Integer(
        string='Points',
        help='Penalty points added to driver record'
    )
    
    ticket_number = fields.Char(
        string='Ticket Number',
        help='Official ticket or citation number'
    )
    
    issuing_authority = fields.Char(
        string='Issuing Authority',
        help='Authority that issued the violation'
    )
    
    # Cost tracking
    cost_record_id = fields.Many2one(
        'fleet.cost.record',
        string='Cost Record',
        readonly=True,
        help='Linked cost record for financial tracking'
    )
    
    # Documents
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_violation_attachment_rel',
        'violation_id',
        'attachment_id',
        string='Attachments',
        help='Violation-related documents (tickets, police reports, etc.)'
    )
    
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count',
        store=False,
        help='Number of attachments'
    )
    
    # Status
    status = fields.Selection(
        [
            ('pending', 'Pending'),
            ('resolved', 'Resolved'),
            ('appealed', 'Under Appeal'),
            ('dismissed', 'Dismissed'),
        ],
        string='Status',
        default='pending',
        required=True,
        tracking=True,
        help='Status of the violation'
    )
    
    resolution_date = fields.Date(
        string='Resolution Date',
        tracking=True,
        help='Date when violation was resolved'
    )
    
    resolution_notes = fields.Text(
        string='Resolution Notes',
        help='Notes about violation resolution'
    )
    
    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        help='Company this violation belongs to'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='company_id.currency_id',
        store=True,
        readonly=True,
        help='Company currency'
    )
    
    active = fields.Boolean(
        string='Active',
        default=True,
        help='Set to false to archive the violation'
    )
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Count attachments"""
        for record in self:
            record.attachment_count = len(record.attachment_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence for violation reference"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.driver.violation') or _('New')
        
        violations = super().create(vals_list)
        
        # Create cost record if fine amount is set
        for violation in violations:
            if violation.fine_amount and not violation.cost_record_id:
                violation._create_cost_record()
        
        return violations
    
    def write(self, vals):
        """Update cost record if fine amount changes"""
        res = super().write(vals)
        
        if 'fine_amount' in vals:
            for violation in self:
                if violation.fine_amount and not violation.cost_record_id:
                    violation._create_cost_record()
                elif violation.cost_record_id and violation.fine_amount:
                    violation.cost_record_id.write({'amount': violation.fine_amount})
        
        return res
    
    def _create_cost_record(self):
        """Create cost record for violation fine"""
        self.ensure_one()
        
        # Find or create Fine cost category
        cost_category = self.env['fleet.cost.category'].search([
            ('name', '=', 'Fine')
        ], limit=1)
        
        if not cost_category:
            cost_category = self.env['fleet.cost.category'].create({
                'name': 'Fine',
                'description': 'Traffic fines and violations',
                'code': 'FINE',
            })
        
        cost_record = self.env['fleet.cost.record'].create({
            'vehicle_id': self.vehicle_id.id if self.vehicle_id else False,
            'driver_id': self.driver_id.id,
            'date': self.date,
            'amount': self.fine_amount,
            'category_id': cost_category.id,
            'description': f"Violation Fine: {self.violation_type.replace('_', ' ').title()} - {self.name}",
            'company_id': self.company_id.id,
        })
        
        self.cost_record_id = cost_record.id
    
    def action_resolve(self):
        """Mark violation as resolved"""
        self.write({
            'status': 'resolved',
            'resolution_date': fields.Date.today(),
        })
    
    def action_appeal(self):
        """Mark violation as under appeal"""
        self.write({'status': 'appealed'})
    
    def action_dismiss(self):
        """Dismiss violation"""
        self.write({
            'status': 'dismissed',
            'resolution_date': fields.Date.today(),
        })

