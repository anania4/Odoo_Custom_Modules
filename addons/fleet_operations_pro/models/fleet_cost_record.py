# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetCostRecord(models.Model):
    """
    Model for tracking all fleet-related costs.
    Can be manually created or auto-generated from fuel/maintenance records.
    """
    _name = 'fleet.cost.record'
    _description = 'Fleet Cost Record'
    _order = 'date desc, id desc'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    
    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        default='New',
        help='Cost record reference number'
    )
    
    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        tracking=True,
        help='Vehicle for which this cost was incurred'
    )
    
    category_id = fields.Many2one(
        'fleet.cost.category',
        string='Cost Category',
        required=True,
        tracking=True,
        help='Category of this cost'
    )
    
    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.today,
        tracking=True,
        help='Date when the cost was incurred'
    )
    
    amount = fields.Monetary(
        string='Amount',
        required=True,
        currency_field='currency_id',
        tracking=True,
        help='Cost amount'
    )
    
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        required=True,
        default=lambda self: self.env.company.currency_id
    )
    
    odometer = fields.Float(
        string='Odometer',
        help='Vehicle odometer reading at the time of this cost'
    )
    
    description = fields.Text(
        string='Description',
        required=True,
        help='Detailed description of the cost'
    )
    
    vendor = fields.Char(
        string='Vendor/Supplier',
        help='Name of the vendor or service provider'
    )
    
    invoice_reference = fields.Char(
        string='Invoice Reference',
        help='Invoice or receipt number'
    )
    
    attachment_ids = fields.Many2many(
        'ir.attachment',
        'fleet_cost_record_attachment_rel',
        'cost_id',
        'attachment_id',
        string='Attachments',
        help='Attach invoices, receipts, or other supporting documents'
    )
    
    auto_generated = fields.Boolean(
        string='Auto Generated',
        default=False,
        help='True if this cost was automatically generated from another record'
    )
    
    source_model = fields.Char(
        string='Source Model',
        help='Model name that generated this cost (e.g., fleet.fuel.log, fleet.maintenance)'
    )
    
    source_record_id = fields.Integer(
        string='Source Record ID',
        help='ID of the record that generated this cost'
    )
    
    driver_id = fields.Many2one(
        'fleet.driver',
        string='Driver',
        help='Driver associated with this cost (if applicable)'
    )
    
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        required=True,
        default=lambda self: self.env.company
    )
    
    notes = fields.Text(
        string='Notes',
        help='Additional notes or comments'
    )
    
    # Computed fields for analysis
    cost_per_km = fields.Float(
        string='Cost per KM',
        compute='_compute_cost_per_km',
        store=True,
        help='Cost per kilometer (if odometer is available)'
    )
    
    @api.depends('amount', 'odometer', 'vehicle_id.odometer')
    def _compute_cost_per_km(self):
        """Calculate cost per kilometer"""
        for record in self:
            if record.odometer and record.vehicle_id.odometer:
                # Calculate based on distance since last cost entry
                previous_costs = self.search([
                    ('vehicle_id', '=', record.vehicle_id.id),
                    ('date', '<', record.date),
                    ('odometer', '>', 0)
                ], order='date desc', limit=1)
                
                if previous_costs:
                    distance = record.odometer - previous_costs[0].odometer
                    if distance > 0:
                        record.cost_per_km = record.amount / distance
                    else:
                        record.cost_per_km = 0.0
                else:
                    # First record, calculate from total odometer
                    if record.odometer > 0:
                        record.cost_per_km = record.amount / record.odometer
                    else:
                        record.cost_per_km = 0.0
            else:
                record.cost_per_km = 0.0
    
    @api.model_create_multi
    def create(self, vals_list):
        """Generate sequence number for cost record - batch optimized"""
        for vals in vals_list:
            if vals.get('name', 'New') == 'New':
                vals['name'] = self.env['ir.sequence'].next_by_code('fleet.cost.record') or 'New'
        return super(FleetCostRecord, self).create(vals_list)
    
    @api.constrains('amount')
    def _check_amount(self):
        """Validate that amount is positive"""
        for record in self:
            if record.amount <= 0:
                raise ValidationError(_('Cost amount must be greater than zero!'))
    
    @api.constrains('odometer')
    def _check_odometer(self):
        """Validate odometer reading"""
        for record in self:
            if record.odometer and record.odometer < 0:
                raise ValidationError(_('Odometer reading cannot be negative!'))
    
    def action_view_source_record(self):
        """Open the source record that generated this cost"""
        self.ensure_one()
        if self.source_model and self.source_record_id:
            return {
                'type': 'ir.actions.act_window',
                'res_model': self.source_model,
                'res_id': self.source_record_id,
                'view_mode': 'form',
                'target': 'current',
            }

