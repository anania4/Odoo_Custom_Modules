# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetDriverTraining(models.Model):
    _name = 'fleet.driver.training'
    _description = 'Driver Training'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'
    
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        help='Training reference number'
    )
    
    driver_id = fields.Many2one(
        'fleet.driver',
        string='Driver',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Driver receiving training'
    )
    
    training_type = fields.Selection(
        [
            ('defensive_driving', 'Defensive Driving'),
            ('hazmat', 'Hazardous Materials'),
            ('first_aid', 'First Aid'),
            ('vehicle_maintenance', 'Vehicle Maintenance'),
            ('customer_service', 'Customer Service'),
            ('safety', 'Safety Training'),
            ('winter_driving', 'Winter Driving'),
            ('eco_driving', 'Eco-Driving'),
            ('certification_renewal', 'Certification Renewal'),
            ('other', 'Other'),
        ],
        string='Training Type',
        required=True,
        tracking=True,
        help='Type of training'
    )
    
    training_name = fields.Char(
        string='Training Name',
        required=True,
        help='Name of the training program'
    )
    
    date = fields.Date(
        string='Training Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date of training'
    )
    
    duration_hours = fields.Float(
        string='Duration (Hours)',
        digits=(10, 2),
        help='Training duration in hours'
    )
    
    trainer = fields.Char(
        string='Trainer',
        help='Name of the trainer or training organization'
    )
    
    location = fields.Char(
        string='Location',
        help='Location where training was conducted'
    )
    
    description = fields.Text(
        string='Description',
        help='Detailed description of training content'
    )
    
    # Completion & Certification
    completion_status = fields.Selection(
        [
            ('scheduled', 'Scheduled'),
            ('in_progress', 'In Progress'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('cancelled', 'Cancelled'),
        ],
        string='Status',
        default='scheduled',
        required=True,
        tracking=True,
        help='Training completion status'
    )
    
    completion_date = fields.Date(
        string='Completion Date',
        tracking=True,
        help='Date when training was completed'
    )
    
    score = fields.Float(
        string='Score (%)',
        digits=(5, 2),
        help='Training score or grade'
    )
    
    passed = fields.Boolean(
        string='Passed',
        compute='_compute_passed',
        store=True,
        help='Whether driver passed the training'
    )
    
    certificate_number = fields.Char(
        string='Certificate Number',
        help='Certificate number if applicable'
    )
    
    certificate_expiry_date = fields.Date(
        string='Certificate Expiry',
        tracking=True,
        help='Date when certificate expires'
    )
    
    is_certification_expired = fields.Boolean(
        string='Certification Expired',
        compute='_compute_certification_expired',
        store=False,
        help='Whether certification has expired'
    )
    
    # Cost tracking
    cost = fields.Monetary(
        string='Training Cost',
        currency_field='currency_id',
        help='Cost of the training'
    )
    
    cost_record_id = fields.Many2one(
        'fleet.cost.record',
        string='Cost Record',
        readonly=True,
        help='Linked cost record for financial tracking'
    )
    
    # Documents
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_training_attachment_rel',
        'training_id',
        'attachment_id',
        string='Attachments',
        help='Training-related documents (certificates, materials, etc.)'
    )
    
    attachment_count = fields.Integer(
        string='Attachments',
        compute='_compute_attachment_count',
        store=False,
        help='Number of attachments'
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes about the training'
    )
    
    # Multi-company
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company,
        tracking=True,
        help='Company this training belongs to',
        index=True
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
        help='Set to false to archive the training'
    )
    
    _sql_constraints = [
        ('score_check', 'CHECK(score >= 0 AND score <= 100)', 'Score must be between 0 and 100!'),
        ('company_consistency_check', 'CHECK(1=1)', 'Company consistency check'),
    ]
    
    def _check_company(self):
        for record in self:
            if record.driver_id.company_id and record.company_id != record.driver_id.company_id:
                raise ValidationError(_("The company of the training must match the company of the driver."))
    
    @api.constrains('company_id', 'driver_id')
    def _check_company_consistency(self):
        self._check_company()
    
    @api.depends('score')
    def _compute_passed(self):
        """Determine if training was passed (score >= 70%)"""
        for record in self:
            record.passed = record.score >= 70.0 if record.score else False
    
    @api.depends('certificate_expiry_date')
    def _compute_certification_expired(self):
        """Check if certification has expired"""
        today = fields.Date.today()
        for record in self:
            record.is_certification_expired = record.certificate_expiry_date and record.certificate_expiry_date < today
    
    @api.depends('attachment_ids')
    def _compute_attachment_count(self):
        """Count attachments"""
        for record in self:
            record.attachment_count = len(record.attachment_ids)
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence for training reference"""
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.driver.training') or _('New')
        
        trainings = super().create(vals_list)
        
        # Create cost record if cost is set
        for training in trainings:
            if training.cost and not training.cost_record_id:
                training._create_cost_record()
        
        return trainings
    
    def write(self, vals):
        """Update cost record if cost changes"""
        res = super().write(vals)
        
        if 'cost' in vals:
            for training in self:
                if training.cost and not training.cost_record_id:
                    training._create_cost_record()
                elif training.cost_record_id and training.cost:
                    training.cost_record_id.write({'amount': training.cost})
        
        return res
    
    def _create_cost_record(self):
        """Create cost record for training cost"""
        self.ensure_one()
        
        # Find or create Training cost category
        cost_category = self.env['fleet.cost.category'].search([
            ('name', '=', 'Training'),
        ], limit=1)
        
        if not cost_category:
            cost_category = self.env['fleet.cost.category'].create({
                'name': 'Training',
                'description': 'Driver training and certification costs',
            })
        
        cost_record = self.env['fleet.cost.record'].create({
            'driver_id': self.driver_id.id,
            'date': self.date,
            'amount': self.cost,
            'category_id': cost_category.id,
            'description': f"Training: {self.training_name} - {self.name}",
            'company_id': self.company_id.id,
        })
        
        self.cost_record_id = cost_record.id
    
    def action_mark_completed(self):
        """Mark training as completed"""
        self.write({
            'completion_status': 'completed',
            'completion_date': fields.Date.today(),
        })
    
    def action_mark_failed(self):
        """Mark training as failed"""
        self.write({
            'completion_status': 'failed',
            'completion_date': fields.Date.today(),
        })
    
    def action_cancel(self):
        """Cancel training"""
        self.write({'completion_status': 'cancelled'})
    
    @api.constrains('date', 'completion_date')
    def _check_dates(self):
        """Validate dates"""
        for record in self:
            if record.completion_date and record.date and record.completion_date < record.date:
                raise ValidationError(_('Completion date cannot be before training date!'))
    
    @api.constrains('score')
    def _check_score(self):
        """Validate score"""
        for record in self:
            if record.score and (record.score < 0 or record.score > 100):
                raise ValidationError(_('Score must be between 0 and 100!'))

