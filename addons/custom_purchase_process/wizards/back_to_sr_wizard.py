# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class BackToSRWizard(models.TransientModel):
    _name = 'back.to.sr.wizard'
    _description = 'Back to SR Wizard'

    reason = fields.Text(
        string='Reason for Back to SR',
        required=True,
        help='Please provide a reason for returning to Material Request'
    )
    purchase_request_id = fields.Many2one('purchase.request', string='Purchase Request', required=True)

    def action_confirm(self):
        """Confirm and proceed with back to SR action"""
        self.ensure_one()
        
        if not self.reason or not self.reason.strip():
            raise ValidationError(_('Reason is required. Please provide a reason for returning to Material Request.'))
        
        purchase_request = self.purchase_request_id
        
        # Check if state is draft
        if purchase_request.state != 'draft':
            raise ValidationError(_('This action can only be performed when the purchase request is in draft state.'))
        
        # Check if there are related RFQs or Supplier Analysis
        if purchase_request.qo_ids:
            raise ValidationError(_('Cannot delete purchase request. There are created RFQs for this record. Please delete the RFQs first.'))
        
        if purchase_request.supplier_analysis_ids:
            raise ValidationError(_('Cannot delete purchase request. There are created Supplier Analysis records for this record. Please delete them first.'))
        
        # Store material request ID BEFORE any operations
        material_request_id = purchase_request.material_request_id.id if purchase_request.material_request_id else None
        
        # Reset material request to draft and save reason if it exists
        if purchase_request.material_request_id:
            material_request = purchase_request.material_request_id
            material_request.state = 'draft'
            material_request.reason_for_back_to_sr = self.reason
            material_request_id = material_request.id  # Ensure we have the ID
        
        # Tell the requester before the purchase request is deleted
        if purchase_request.material_request_id:
            purchase_request._notify_back_to_sr(purchase_request.material_request_id, self.reason)

        # Delete the purchase request
        purchase_request.unlink()
        
        # Always return to purchase request tree view
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Requests'),
            'res_model': 'purchase.request',
            'view_mode': 'list,form',
            'target': 'current',
        }

