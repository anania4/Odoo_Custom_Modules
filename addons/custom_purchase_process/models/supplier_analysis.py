from odoo import _, api, fields, models
from odoo.exceptions import ValidationError, UserError
from datetime import datetime
import logging

_logger = logging.getLogger(__name__)

class SupplierAnalysis(models.Model):
    _name = 'supplier.analysis'
    _description = 'Supplier Analysis'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin", "custom.purchase.notify.mixin"]
    _bell_only_notifications = True

    name = fields.Char(
        string="Analysis Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )
    state = fields.Selection([
        ('draft', 'On Draft'),
        ('analyzed', 'Analysed'),
        ('approved_by_proc', 'Approved by Procurement Manager'),
        ('approved_by_finance', 'Approved by Finance Manager'),
        ('approved_by_ceo', 'Approved by CEO'),
        ('done', 'Done'),
        ('cancelled', 'Cancelled'),
    ], string="Status", default='draft', required=True, tracking=True)

    purchase_request_id = fields.Many2one('purchase.request', string="Purchase Request", required=True)
    remark = fields.Char("Remark")
    committee_approval = fields.Boolean("Committee Approval")
    procurement_officer_id = fields.Many2one(
        'res.users',
        string="Procurement Officer",
        related='purchase_request_id.user_id',
        readonly=True,
        help="Procurement Officer assigned on the source Purchase Request (Store Requisition)"
    )
    reason_for_cancel = fields.Char("Reason for Cancellation")
    reason_for_set_draft = fields.Char("Reason for Reset to Draft")
    rejection_reason = fields.Text(string="Rejection Reason", readonly=True)
    supplier_analysis_lines = fields.One2many('supplier.analysis.line', 'analysis_id', string="Product Lines")
    qa_required = fields.Selection([
        ('yes', 'Yes'),
        ('no', 'No')
    ], string="QA Required", default='')
    procurement_type = fields.Selection([
        ('pay_to_procure', 'Pay to Procure'),
        ('procure_to_pay', 'Procure to Pay')
    ], string="Procurement Type", default='pay_to_procure')

    date_requested = fields.Date(string="Date Requested", default=fields.Datetime.now, required=True)
    requested_by = fields.Many2one('res.users', string="Procurrement Officer", default=lambda self: self.env.user)
    approved_by = fields.Many2one('res.users', string="Approved By")
    company_id = fields.Many2one(
        'res.company', string="Company", readonly=True, force_save=True,
        required=True, default=lambda self: self.env.company
    )
    user_id = fields.Many2one(
        'res.users', string="Purchaser",
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref('purchase.group_purchase_user').id),
            ('company_ids', 'in', self.env.context.get('allowed_company_ids', []))
        ],
    )
    ceo_approved_by = fields.Many2one('res.users', string="Approved CEO")
    finance_approved_by = fields.Many2one('res.users', string="Approved By (Finance)")

    purchase_order_count = fields.Integer(string="Purchase Order Count", compute="_compute_purchase_order_count")
    po_ids = fields.One2many('purchase.order', 'purchase_request_supplier_id', string='POs')
    supplier_analysis_po_count = fields.Integer(string="Supplier Analysis PO Count", compute="_compute_supplier_analysis_po_count")

    reason_for_selecting_vendor = fields.Html(string="Reason for Selecting/Updating Vendor")
    threshold_id = fields.Many2one(
            'supplier_analysis.threshold',
            string="Approval Threshold",
            tracking=True
        )


    total_amount = fields.Float(
        string="Total Amount",
        compute="_compute_total_amount",
        store=True,
        help="Sum of all line subtotals"
    )

    @api.depends('supplier_analysis_lines.subtotal', 'supplier_analysis_lines.selected')
    def _compute_total_amount(self):
        for analysis in self:
            selected_lines = analysis.supplier_analysis_lines.filtered(lambda l: l.selected)
            analysis.total_amount = sum(selected_lines.mapped('subtotal')) if selected_lines else 0.0

    # Create sequence
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('supplier.analysis') or _('New')
        return super(SupplierAnalysis, self).create(vals)

    @api.depends('po_ids')
    def _compute_purchase_order_count(self):
        for record in self:
            record.purchase_order_count = len(record.po_ids)
    
    @api.depends('po_ids')
    def _compute_supplier_analysis_po_count(self):
        for record in self:
            # Count purchase orders directly related to this supplier analysis
            record.supplier_analysis_po_count = self.env['purchase.order'].search_count([
                ('purchase_request_supplier_id', '=', record.id)
            ])

    

    def action_view_po_supplier(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Purchase Orders',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('purchase_request_id', '=', self.purchase_request_id.id)],
            'context': dict(self.env.context, create=False),
        }
    
    def action_view_supplier_analysis_pos(self):
        """View purchase orders directly linked to this supplier analysis"""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': f'Purchase Orders - {self.name}',
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('purchase_request_supplier_id', '=', self.id)],
            'context': {
                'default_purchase_request_supplier_id': self.id,
                'create': False
            },
            'target': 'current',
        }

    def action_view_sa(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': 'Quality Inspection',
            'res_model': 'quality.inspection',
            'view_mode': 'list,form',
            'domain': [('supplier_analysis_id', '=', self.id)],
            'context': dict(self.env.context, create=False),
        }
    @api.onchange('qa_required', 'supplier_analysis_lines.selected')
    def _onchange_qa_required(self):
        if self.qa_required and self.qa_required == 'yes':
            self.supplier_analysis_lines.filtered(lambda l: l.selected).chosen_for_inspection = True
        else:
            self.supplier_analysis_lines.filtered(lambda l: l.selected).chosen_for_inspection = False
            self.supplier_analysis_lines.filtered(lambda l: l.selected).passed_inspection = False

    def action_generate_quality_inspection(self):
        """Generate quality inspection records for products that need inspection - enhanced version"""
        quality_inspection_model = self.env['quality.inspection']
        created_inspections = []
        
        for record in self:
            # Only allow from analyzed or approved_by_proc states if QA is required
            if record.state not in ['analyzed', 'approved_by_proc']:
                raise UserError(_("Quality inspection can only be generated from In Progress or Committee Approved state."))
                
            if record.qa_required != 'yes':
                raise UserError(_("Quality inspection is not required for this analysis."))
            
            # Check for existing quality inspections (excluding 'failed' state)
            existing_inspections = quality_inspection_model.search([
                ('supplier_analysis_id', '=', record.id),
                ('state', 'in', ['draft', 'requested_docs', 'approved'])
            ])
            
            # If there are existing inspections, check their status
            if existing_inspections:
                # First, check ALL inspections for failed items (regardless of state)
                failed_inspections = existing_inspections.filtered(lambda inv: inv.has_failed_items())
                
                if failed_inspections:
                    # If any inspection has failed items, change those to 'failed' state and allow creating new one
                    failed_inspections.write({'state': 'failed'})
                else:
                    # No failed items - check if there are approved inspections with all passed items
                    approved_inspections = existing_inspections.filtered(lambda inv: inv.state == 'approved')
                    approved_with_all_passed = approved_inspections.filtered(lambda inv: inv.has_passed_items())
                    
                    if approved_with_all_passed:
                        # If approved inspection with all passed items exists, don't create another
                        raise UserError(_("Quality inspection are already created with all passed items. Cannot create another inspection. Only create new inspection if the existing one has failed items."))
                    else:
                        # There are draft/requested_docs inspections (not approved yet) or approved without all passed
                        # Don't create another one
                        raise UserError(_("Quality inspection are already created. Cannot create another inspection. Only create new inspection if the existing one has failed items."))
            
            # If there are any other active inspections (draft/requested_docs without failed items), 
            # we should also handle them - but based on requirements, we only care about approved with passed
            # So we'll allow creating new ones if previous ones are not approved with all passed
            
            # Get lines that are selected
            selected_lines = record.supplier_analysis_lines.filtered(lambda l: l.selected)
            if not selected_lines:
                raise UserError(_("No lines selected for inspection."))

            # If there are existing quality inspections, filter to only include lines with failed items OR new vendors
            lines_to_inspect = selected_lines
            if existing_inspections:
                # Find all quality inspection lines for this supplier analysis (to identify previously inspected vendors)
                all_qi_lines = self.env['quality.inspection.line'].search([
                    ('quality_inspection_id.supplier_analysis_id', '=', record.id)
                ])
                
                # Get all previously inspected combinations (supplier_analysis_line_id, partner_id)
                previously_inspected = set()
                for qi_line in all_qi_lines:
                    if qi_line.supplier_analysis_line_id and qi_line.partner_id:
                        previously_inspected.add((
                            qi_line.supplier_analysis_line_id.id,
                            qi_line.partner_id.id
                        ))
                
                # Get combinations that failed
                failed_qi_lines = all_qi_lines.filtered(lambda l: l.failed_inspection)
                failed_combinations = set()
                for qi_line in failed_qi_lines:
                    if qi_line.supplier_analysis_line_id and qi_line.partner_id:
                        failed_combinations.add((
                            qi_line.supplier_analysis_line_id.id,
                            qi_line.partner_id.id
                        ))
                
                # Filter selected_lines to include:
                # 1. Lines that have failed items (from previous inspection)
                # 2. Lines for NEW vendors (not previously inspected)
                lines_to_inspect = selected_lines.filtered(
                    lambda l: l.partner_id and (
                        (l.id, l.partner_id.id) in failed_combinations or  # Has failed items
                        (l.id, l.partner_id.id) not in previously_inspected  # New vendor, not inspected before
                    )
                )
                
                if not lines_to_inspect:
                    raise UserError(_("No lines with failed items or new vendors found. Cannot create quality inspection. Only create inspection for lines that have failed items from previous inspection or for new vendors."))

            # Auto-mark lines for inspection (batch update)
            lines_to_inspect.filtered(lambda l: not l.chosen_for_inspection).write({'chosen_for_inspection': True})

            # Group by vendor for efficient processing
            selected_lines_by_vendor = {}
            for line in lines_to_inspect:
                if not line.partner_id:
                    raise UserError(_("Each selected line must have a vendor assigned."))
                selected_lines_by_vendor.setdefault(line.partner_id.id, []).append(line)

            # Create quality inspections per vendor
            for vendor_id, lines in selected_lines_by_vendor.items():
                inspection = quality_inspection_model.create({
                    'name': self.env['ir.sequence'].next_by_code('quality.inspection') or _('New'),
                    'supplier_analysis_id': record.id,
                    'requested_date': record.date_requested,
                    'partner_id': vendor_id,
                    'quality_inspections_line_ids': [(0, 0, {
                        'supplier_analysis_line_id': line.id,
                        'partner_id': vendor_id,  # Set vendor directly for better performance
                        'product_id': line.product_id.id,
                        'name': line.name,
                        'passed_inspection': False,
                        'inspection_remark': '',
                    }) for line in lines],
                })
                created_inspections.append(inspection)
                inspection._notify_generated()
                
        return {
            'type': 'ir.actions.act_window',
            'name': 'Generated Quality Inspections',
            'res_model': 'quality.inspection',
            'view_mode': 'list,form',
            'domain': [('id', 'in', [i.id for i in created_inspections])],
            'target': 'current',
        }

    
    
    def action_analyze(self):
        for record in self:
            if not record.qa_required:
                raise UserError(_("Please select quality inspection choice"))
            if record.state != 'draft':
                raise UserError(_("Only records in Draft state can be moved to Analyzed."))
            if not record.remark:
                raise UserError(_("Please provide a remark before moving to Analyzed."))
            
            record.supplier_analysis_lines.filtered(lambda l: l.is_newly_added).write({'is_newly_added': False})
            record.state = 'analyzed'
            record._notify_analyzed()




    
    def action_procurement_approve(self):
        for record in self:
            if record.state != 'analyzed':
                raise UserError(_("Only records in Analyzed state can be approved by Procurement Manager."))

            selected_lines = record.supplier_analysis_lines.filtered(lambda l: l.selected)
            if not selected_lines:
                raise UserError(_("At least one product must be selected for approval."))

            if record.qa_required == 'yes':
                selected_lines.write({'chosen_for_inspection': True})

            for line in selected_lines:
                if record.purchase_request_id.material_request_id:
                    matching_request_lines = record.purchase_request_id.material_request_id.material_request_line_ids.filtered(
                        lambda x: x.product_id == line.product_id
                    )
                    if matching_request_lines and hasattr(matching_request_lines, 'supplier_id') and hasattr(matching_request_lines, 'cost_price'):
                        matching_request_lines.write({
                            'supplier_id': line.partner_id.id,
                            'cost_price': line.unit_price
                        })

            record.approved_by = self.env.user.id
            record.state = 'approved_by_proc'
            record._notify_procurement_approved()

    def action_ceo_approve(self):
        purchase_orders = self.env['purchase.order']
        for record in self:
            if record.state not in ('approved_by_finance', 'approved_by_ceo'):
                raise UserError(
                    _("CEO can only approve from Approved by Finance Manager state.")
                )

            if record.qa_required == 'yes':
                qa_lines = record.supplier_analysis_lines.filtered(lambda l: l.selected and l.chosen_for_inspection)
                if qa_lines:
                    uninspected_lines = qa_lines.filtered(lambda l: not l.passed_inspection)
                    if uninspected_lines:
                        raise UserError(_("Quality inspection is required but some items have not passed inspection or are still pending."))

            selected_lines = record.supplier_analysis_lines.filtered(lambda l: l.selected)
            if not selected_lines:
                raise UserError(_("No supplier analysis lines have been marked as selected."))

            lines_without_partners = selected_lines.filtered(lambda l: not l.partner_id)
            if lines_without_partners:
                raise UserError(_("The following lines are selected but have no vendor assigned: %s") %
                              ', '.join(lines_without_partners.mapped('name')))

            grouped_lines = {}
            for line in selected_lines:
                grouped_lines.setdefault(line.partner_id.id, []).append(line)

            record_purchase_orders = self.env['purchase.order']
            for partner_id, lines in grouped_lines.items():
                if not partner_id:
                    raise UserError(_("Invalid partner_id found in grouped lines. Please check vendor assignments."))

                po_vals = {
                    'partner_id': partner_id,
                    'origin': record.purchase_request_id.name,
                    'date_order': fields.Datetime.now(),
                    'purchase_request_id': record.purchase_request_id.id,
                    'project_id': record.purchase_request_id.project_id.id,
                    'remark': record.remark,
                    'purchase_request_supplier_id': record.id,
                    'procurement_type': record.procurement_type,
                    'quality_evaluation': record.qa_required == 'yes',
                    'passed_evaluation': record.qa_required != 'yes' or all(
                        not l.chosen_for_inspection or l.passed_inspection for l in lines
                    ),
                }

                purchase_order = self.env['purchase.order'].create(po_vals)
                record_purchase_orders |= purchase_order

                for line in lines:
                    self.env['purchase.order.line'].create({
                        'order_id': purchase_order.id,
                        'product_id': line.product_id.id,
                        'name': line.name or line.product_id.name,
                        'product_uom': line.product_uom_id.id or line.product_id.uom_po_id.id,
                        'price_unit': line.unit_price,
                        'product_qty': line.quantity,
                        'date_planned': fields.Datetime.now(),
                        'taxes_id': [(6, 0, line.taxes_id.ids)],
                    })

                try:
                    purchase_order.button_confirm()
                except Exception as e:
                    _logger.warning("Failed to confirm purchase order %s: %s", purchase_order.name, str(e))

            record.write({
                'state': 'done',
                'ceo_approved_by': self.env.user.id,
            })
            record.purchase_request_id.state = 'purchase_order'
            purchase_orders |= record_purchase_orders
            record._notify_ceo_approved(record_purchase_orders)

        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('id', 'in', purchase_orders.ids)],
            'target': 'current',
        }

    def action_cancel(self):
        """Cancel the supplier analysis with a required reason."""
        for record in self:
            if not record.reason_for_cancel:
                raise UserError(_("Please provide a reason for cancellation before cancelling this supplier analysis."))
            
            if record.state not in ['draft', 'analyzed', 'approved_by_proc', 'approved_by_finance', 'approved_by_ceo']:
                raise UserError(_("Only certain states can be cancelled."))
            
            record.state = 'cancelled'
            record._notify_cancelled()

    def _get_analyst_users(self):
        """Users who must be told when an analysis is sent back for re-analysis."""
        self.ensure_one()
        return (self.requested_by | self.procurement_officer_id).sudo()

    def action_reset_to_draft(self):
        """Reset the supplier analysis to draft with a required reason."""
        for record in self:
            if not record.reason_for_set_draft:
                raise UserError(_("Please provide a reason for resetting to draft before proceeding."))

            reason = record.reason_for_set_draft
            # the approvers are cleared by the reset, so remember who to tell
            earlier_handlers = record._get_analyst_users() | record.approved_by | record.finance_approved_by

            record.write({
                'state': 'draft',
                'reason_for_set_draft': False,
                'approved_by': False,
                'finance_approved_by': False,
                'finance_officer_id': False,
            })

            record.supplier_analysis_lines.write({
                'chosen_for_inspection': False,
                'passed_inspection': False,
            })

            record._notify_sent_back(reason, earlier_handlers)

    def action_update_supplier_analysis(self):
        """Update supplier analysis with new vendors from RFQs - Enhanced to maintain product grouping"""
        self.ensure_one()
        
        if self.state != 'draft':
            raise UserError(_("Supplier analysis can only be updated when in draft state."))
        
        # Get all quotations for this purchase request
        # Rejected RFQs are left out; RFQs that are not received yet have no prices to compare.
        quotations = self.env['purchase.quotation'].search([
            ('purchase_request_id', '=', self.purchase_request_id.id),
            ('state', '=', 'received'),
        ])
        
        if not quotations:
            raise UserError(_("No received quotations found for this purchase request."))
        
        # Get existing vendor-product combinations in this analysis
        existing_combinations = set()
        for line in self.supplier_analysis_lines:
            if line.product_id and line.partner_id:
                existing_combinations.add((line.product_id.id, line.partner_id.id))
        
        # Group new vendors by product
        new_vendors_by_product = {}
        for quotation in quotations:
            for quotation_line in quotation.quotation_line_ids:
                if quotation_line.product_id and quotation.partner_id:
                    combination = (quotation_line.product_id.id, quotation.partner_id.id)
                    if combination not in existing_combinations:
                        product_id = quotation_line.product_id.id
                        if product_id not in new_vendors_by_product:
                            new_vendors_by_product[product_id] = []
                        
                        new_vendors_by_product[product_id].append({
                            'analysis_id': self.id,
                            'product_id': quotation_line.product_id.id,
                            'partner_id': quotation.partner_id.id,
                            'name': quotation_line.description or quotation_line.product_id.name,
                            'product_uom_id': quotation_line.product_uom_id.id,
                            'quantity': quotation_line.quantity,
                            'unit_price': quotation_line.unit_price,
                            'selected': False,
                            'is_merge_line': False,
                            'is_newly_added': False,  # Don't highlight - treat as normal
                        })
                        existing_combinations.add(combination)
        
        if new_vendors_by_product:
            total_added = 0
            # Get all existing lines sorted by sequence/id
            all_lines = self.supplier_analysis_lines.sorted('id')
            
            # For each product that has new vendors
            for product_id, new_lines_data in new_vendors_by_product.items():
                # Find the last line for this product (skip merge lines)
                last_product_line = None
                last_product_line_index = -1
                
                for idx, line in enumerate(all_lines):
                    if line.product_id.id == product_id and not line.is_merge_line:
                        last_product_line = line
                        last_product_line_index = idx
                
                if last_product_line:
                    # Get the sequence/position after the last line of this product
                    # Find the next line after the last product line
                    if last_product_line_index + 1 < len(all_lines):
                        next_line = all_lines[last_product_line_index + 1]
                        # Insert new lines before the next line (which could be a merge line for next product)
                        for new_line_data in new_lines_data:
                            # Create the line - Odoo will append it to the end by default
                            created_line = self.env['supplier.analysis.line'].with_context(allow_create_supplier_analysis_line=True).create(new_line_data)
                            total_added += 1
                    else:
                        # Last product in the list, just create at the end
                        for new_line_data in new_lines_data:
                            self.env['supplier.analysis.line'].with_context(allow_create_supplier_analysis_line=True).create(new_line_data)
                            total_added += 1
                else:
                    # Product not found in existing lines (shouldn't happen, but handle it)
                    for new_line_data in new_lines_data:
                        self.env['supplier.analysis.line'].create(new_line_data)
                        total_added += 1
            
            # Reorder lines to ensure proper grouping: merge line -> product lines -> merge line -> product lines
            self._reorder_analysis_lines()
            
            return True
        raise UserError(_('No new vendors found to add to the supplier analysis.'))
    
    # ------------------------------------------------------------------
    # Bell notifications
    # ------------------------------------------------------------------
    def _get_pr_requester_users(self):
        """People who started the request: SR requester and PR requester."""
        self.ensure_one()
        return self.purchase_request_id._get_requester_users()

    def _notify_created(self):
        self.ensure_one()
        officers = self._get_group_users(
            'custom_purchase_process.group_supplier_analysis_user',
            ['custom_purchase_process.group_supplier_analysis_supervisor'])
        self._notify_flow(
            forward=officers,
            forward_title=_("Supplier Analysis awaits you"),
            forward_message=_("%s was created for %s. Analyse the quotations and start the analysis.",
                              self.name, self.purchase_request_id.name),
            icon='fa-balance-scale',
        )

    def _notify_analyzed(self):
        self.ensure_one()
        managers = self._get_group_users(
            'custom_purchase_process.group_supplier_analysis_procurement_manager',
            ['custom_purchase_process.group_supplier_analysis_finance_manager'])
        self._notify_flow(
            forward=managers,
            forward_title=_("Supplier Analysis awaits your approval"),
            forward_message=_("%s for %s was analysed by %s and awaits your approval.",
                              self.name, self.purchase_request_id.name, self.env.user.name),
            icon='fa-balance-scale',
        )

    def _notify_procurement_approved(self):
        self.ensure_one()
        finance = self._get_group_users(
            'custom_purchase_process.group_supplier_analysis_finance_manager',
            ['custom_purchase_process.group_supplier_analysis_ceo'])
        self._notify_flow(
            forward=finance,
            forward_title=_("Supplier Analysis awaits your approval"),
            forward_message=_("%s for %s was approved by the Procurement Manager (%s). "
                              "Assign a finance officer and approve it.",
                              self.name, self.purchase_request_id.name, self.env.user.name),
            backward=self._get_analyst_users(),
            backward_title=_("Your Supplier Analysis was approved"),
            backward_message=_("%s was approved by the Procurement Manager (%s) and moved to Finance.",
                               self.name, self.env.user.name),
            icon='fa-balance-scale',
        )

    def _notify_finance_approved(self):
        self.ensure_one()
        ceos = self._get_group_users('custom_purchase_process.group_supplier_analysis_ceo')
        previous = self._get_analyst_users() | self.approved_by
        self._notify_flow(
            forward=ceos,
            forward_title=_("Supplier Analysis awaits your approval"),
            forward_message=_("%s for %s was approved by the Finance Manager (%s) and awaits your approval.",
                              self.name, self.purchase_request_id.name, self.env.user.name),
            backward=previous,
            backward_title=_("Supplier Analysis approved by Finance"),
            backward_message=_("%s was approved by the Finance Manager (%s). Finance officer: %s.",
                               self.name, self.env.user.name, self.finance_officer_id.name),
            icon='fa-balance-scale',
        )
        self._bell_notify(
            self.finance_officer_id.user_id,
            _("Supplier Analysis assigned to you"),
            _("%s for %s was approved by %s and is assigned to you as finance officer.",
              self.name, self.purchase_request_id.name, self.env.user.name),
            'info', 'fa-money')

    def _notify_ceo_approved(self, purchase_orders):
        self.ensure_one()
        orders = ', '.join(purchase_orders.mapped('name'))
        earlier = (self._get_analyst_users() | self.approved_by | self.finance_approved_by
                   | self.finance_officer_id.user_id | self._get_pr_requester_users())
        self._notify_flow(
            backward=earlier,
            backward_title=_("Supplier Analysis approved by CEO"),
            backward_message=_("%s was approved by the CEO (%s). Purchase Orders generated: %s.",
                               self.name, self.env.user.name, orders),
            icon='fa-check-circle',
        )

    def _notify_sent_back(self, reason, earlier_handlers):
        self.ensure_one()
        # The analysts must redo the analysis, so they get an action-required message.
        self._notify_flow(
            forward=self._get_analyst_users(),
            forward_title=_("Supplier Analysis returned for re-analysis"),
            forward_message=_("%s was sent back for re-analysis by %s. Reason: %s",
                              self.name, self.env.user.name, reason),
            backward=earlier_handlers,
            backward_title=_("Supplier Analysis sent back"),
            backward_message=_("%s was sent back for re-analysis by %s. Reason: %s",
                               self.name, self.env.user.name, reason),
            icon='fa-undo',
        )

    def _notify_cancelled(self):
        self.ensure_one()
        self._notify_flow(
            backward=self._get_analyst_users() | self.approved_by | self.finance_approved_by | self.finance_officer_id.user_id,
            backward_title=_("Supplier Analysis cancelled"),
            backward_message=_("%s was cancelled by %s. Reason: %s",
                               self.name, self.env.user.name, self.reason_for_cancel),
            icon='fa-ban',
        )

    def _reorder_analysis_lines(self):
        """Reorder supplier analysis lines to maintain product grouping"""
        self.ensure_one()
        
        # Group lines by product
        lines_by_product = {}
        merge_lines_by_product = {}
        
        for line in self.supplier_analysis_lines:
            if line.is_merge_line:
                merge_lines_by_product[line.product_id.id] = line
            else:
                if line.product_id.id not in lines_by_product:
                    lines_by_product[line.product_id.id] = []
                lines_by_product[line.product_id.id].append(line)
        
        # Reorder: for each product, set sequence for merge line first, then product lines
        sequence = 10
        for product_id in sorted(lines_by_product.keys()):
            # Set sequence for merge line
            if product_id in merge_lines_by_product:
                merge_lines_by_product[product_id].write({'sequence': sequence})
                sequence += 10
            
            # Set sequence for product lines
            for line in lines_by_product[product_id]:
                line.write({'sequence': sequence})
                sequence += 10


class SupplierAnalysisLine(models.Model):
    _inherit = ['custom.purchase.tax.amounts.mixin']
    _name = 'supplier.analysis.line'
    _description = "Supplier Analysis Line"
    _order = 'sequence, id'

    @api.model_create_multi
    def create(self, vals_list):
        # Prevent manual creation of supplier analysis lines
        # Allow creation only if context flag 'allow_create_supplier_analysis_line' is set (for programmatic creation)
        if not self.env.context.get('allow_create_supplier_analysis_line'):
            raise UserError(_('Supplier analysis lines cannot be created manually. They must be created through the purchase request workflow.'))
        return super().create(vals_list)

    sequence = fields.Integer(string="Sequence", default=10)
    analysis_id = fields.Many2one('supplier.analysis', string="Analysis")
    # Mirror parent state so we can control readonly in views without attrs
    state = fields.Selection(related='analysis_id.state', string="Status", store=False, readonly=True)
    is_merge_line = fields.Boolean("Is Merge Line", default=False)
    merge_note = fields.Char("Merge Note")

    product_id = fields.Many2one(
        'product.product', 
        string="Product",
    )
    partner_id = fields.Many2one('res.partner', string="Vendor")
    name = fields.Char("Description")
    product_uom_id = fields.Many2one(
        'uom.uom',
        string="Unit of Measure",
        readonly=True,
        store=True
    )
    # Editable only when parent analysis is in draft state
    unit_price = fields.Float(
        "Unit Price",
        help="Unit price - editable only when parent analysis is in draft state"
    )
    quantity = fields.Float(
        "Quantity",
        help="Quantity - editable only when parent analysis is in draft state"
    )
    # Live reference shown in the "Notes for <product>" merge rows: total PR quantity
    # and PR UOM for that product. For product rows they simply mirror the line's own
    # values, so a single list column serves both cases.
    display_uom_id = fields.Many2one(
        'uom.uom',
        string="UOM",
        compute="_compute_display_reference",
        store=False,
        readonly=True,
        help="Reference UOM: the purchase request UOM on note rows, the line's own UOM otherwise.",
    )
    display_quantity = fields.Float(
        string="Quantity",
        compute="_compute_display_reference",
        inverse="_inverse_display_quantity",
        store=False,
        help="Reference quantity: total purchase request quantity on note rows (readonly), "
             "the line's own quantity otherwise.",
    )

    @api.depends(
        'is_merge_line', 'product_id', 'quantity', 'product_uom_id',
        'analysis_id.purchase_request_id.purchase_request_line_ids.product_id',
        'analysis_id.purchase_request_id.purchase_request_line_ids.quantity',
        'analysis_id.purchase_request_id.purchase_request_line_ids.product_uom_id',
    )
    def _compute_display_reference(self):
        for line in self:
            if line.is_merge_line and line.product_id:
                pr_lines = line.analysis_id.purchase_request_id.purchase_request_line_ids.filtered(
                    lambda rl: rl.product_id == line.product_id
                )
                line.display_uom_id = pr_lines[:1].product_uom_id or line.product_id.uom_id
                line.display_quantity = sum(pr_lines.mapped('quantity'))
            else:
                line.display_uom_id = line.product_uom_id
                line.display_quantity = line.quantity

    def _inverse_display_quantity(self):
        for line in self:
            # Note rows are readonly; only product rows write back to their own quantity.
            if not line.is_merge_line:
                line.quantity = line.display_quantity

    selected = fields.Boolean("Selected")
    selected_readonly = fields.Boolean(
        string="Selected Readonly",
        compute="_compute_selected_readonly",
        store=False,
    )

    @api.depends('analysis_id.state')
    def _compute_selected_readonly(self):
        for line in self:
            line.selected_readonly = line.analysis_id.state not in ('draft', 'analyzed')
    chosen_for_inspection = fields.Boolean("Inspect", compute="_compute_chosen_for_inspection", store=True)
    passed_inspection = fields.Boolean("Passed Inspection",readonly=True)
    
    quality_inspection_status = fields.Selection(
        [('passed', 'Passed'), ('failed', 'Failed')],
        string="Inspection Status",
        compute="_compute_quality_inspection_status",
        store=False,
        help="Shows the inspection status from the related Quality Inspection Line for the matching vendor"
    )

    show_merge_note = fields.Boolean(compute="_compute_field_visibility")
    hide_merge_fields = fields.Boolean(compute="_compute_field_visibility")

    subtotal = fields.Float(
        string="Subtotal", compute="_compute_subtotal", store=True
    )
    taxes_id = fields.Many2many(
        'account.tax',
        'supplier_analysis_line_account_tax_rel',
        string="Taxes",
        help="Taxes applied to this line. Editable only while the analysis is in draft.",
    )
    is_newly_added = fields.Boolean(
        string="Newly Added", 
        default=False,
        help="Indicates if this line was added via the Update button"
    )

    @api.depends('selected','analysis_id.qa_required')
    def _compute_chosen_for_inspection(self):
        for line in self:
            if line.selected and line.analysis_id.qa_required == 'yes':
                line.chosen_for_inspection = True
            else:
                line.chosen_for_inspection = False

    @api.depends('unit_price', 'quantity', 'taxes_id')
    def _compute_subtotal(self):
        for line in self:
            line.subtotal = line._compute_taxed_amount(
                line.taxes_id,
                line.unit_price,
                line.quantity,
                partner=line.partner_id,
                product=line.product_id,
            )

    @api.depends('is_merge_line')
    def _compute_field_visibility(self):
        for line in self:
            line.show_merge_note = line.is_merge_line
            line.hide_merge_fields = line.is_merge_line

    def _compute_quality_inspection_status(self):
        """Compute inspection status from related quality.inspection.line matching the vendor"""
        for line in self:
            if not line.partner_id:
                line.quality_inspection_status = False
                continue
            
            # Find the quality inspection line where:
            # 1. supplier_analysis_line_id matches this line
            # 2. The quality inspection's partner_id matches this line's partner_id (vendor)
            quality_inspection_line = self.env['quality.inspection.line'].search([
                ('supplier_analysis_line_id', '=', line.id),
                ('quality_inspection_id.partner_id', '=', line.partner_id.id)
            ], limit=1)
            
            if quality_inspection_line:
                # Show passed/failed if quality inspection is in approved or failed state
                qi_state = quality_inspection_line.quality_inspection_id.state
                if qi_state in ['approved', 'failed']:
                    if quality_inspection_line.passed_inspection:
                        line.quality_inspection_status = 'passed'
                    elif quality_inspection_line.failed_inspection:
                        line.quality_inspection_status = 'failed'
                    else:
                        line.quality_inspection_status = False
                else:
                    # Quality inspection not approved/failed yet, don't show status
                    line.quality_inspection_status = False
            else:
                line.quality_inspection_status = False

    def unlink(self):
        """Prevent deletion of supplier analysis records unless they are in draft state."""
        for record in self:
            if record.state != 'draft':
                raise UserError(_('You cannot delete records that are not in draft state.'))
        return super(SupplierAnalysisLine, self).unlink()




