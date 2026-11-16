# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class RejectPurchaseRequestWizard(models.TransientModel):
    _name = 'reject.purchase.request.wizard'
    _description = 'Reject Purchase Request Wizard'

    reason = fields.Text(
        string='Rejection Reason',
        required=True,
        help='Please provide a reason for rejecting this purchase request'
    )
    purchase_request_id = fields.Many2one('purchase.request', string='Purchase Request', required=True)

    def action_confirm(self):
        """Confirm and proceed with rejection"""
        self.ensure_one()
        
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('Rejection reason is required. Please provide a reason for rejecting this purchase request.'))
        
        purchase_request = self.purchase_request_id
        
        # Check if state is draft
        if purchase_request.state != 'draft':
            raise ValidationError(_('This action can only be performed when the purchase request is in draft state.'))
        
        # Save rejection reason to purchase request
        purchase_request.rejection_reason = self.reason
        purchase_request.state = 'rejected'
        purchase_request._notify_rejected(self.reason)
        
        # Reject all related purchase quotations
        quotations = self.env['purchase.quotation'].search([
            ('purchase_request_id', '=', purchase_request.id)
        ])
        for quotation in quotations:
            quotation.rejection_reason = self.reason
            quotation.state = 'rejected'
        
        # Cancel all related supplier analysis
        supplier_analyses = self.env['supplier.analysis'].search([
            ('purchase_request_id', '=', purchase_request.id)
        ])
        for analysis in supplier_analyses:
            analysis.rejection_reason = self.reason
            analysis.state = 'cancelled'
            analysis._close_flow_activities()
        
        # Reject material request if linked
        if purchase_request.material_request_id:
            purchase_request.material_request_id.rejection_reason = self.reason
            purchase_request.material_request_id.state = 'rejected'
            purchase_request.material_request_id._close_flow_activities()
        
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Request'),
            'res_model': 'purchase.request',
            'view_mode': 'form',
            'res_id': purchase_request.id,
            'target': 'current',
        }

