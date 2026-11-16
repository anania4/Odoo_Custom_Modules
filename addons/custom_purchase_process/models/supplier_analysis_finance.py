from odoo import _, fields, models
from odoo.exceptions import AccessError, UserError


class SupplierAnalysisFinance(models.Model):
    _inherit = 'supplier.analysis'

    state = fields.Selection(
        ondelete={'approved_by_finance': 'set default'},
    )

    finance_officer_id = fields.Many2one(
        'hr.employee',
        string="Finance Officer",
        tracking=True,
        copy=False,
        help="Employee who follows this analysis up for Finance. The Finance Manager must "
             "assign one before approving.",
    )

    def write(self, vals):
        if vals.get('finance_officer_id') and not self.env.su and not self.env.user.has_group(
                'custom_purchase_process.group_supplier_analysis_finance_manager'):
            raise AccessError(_("Only the Finance Manager can assign the finance officer."))
        return super().write(vals)

    def _get_lines_pending_inspection(self):
        """Selected lines that must pass quality inspection before approval."""
        self.ensure_one()
        if self.qa_required != 'yes':
            return self.supplier_analysis_lines.browse()
        return self.supplier_analysis_lines.filtered(
            lambda line: line.selected and line.chosen_for_inspection and not line.passed_inspection
        )

    def action_finance_approve(self):
        for record in self:
            if record.state != 'approved_by_proc':
                raise UserError(
                    _("Only records in Approved by Procurement Manager state can be approved by the Finance Manager.")
                )

            if not record.finance_officer_id:
                raise UserError(_("Please assign a finance officer before approving."))

            if not record.supplier_analysis_lines.filtered(lambda line: line.selected):
                raise UserError(_("At least one product must be selected for approval."))

            pending_lines = record._get_lines_pending_inspection()
            if pending_lines:
                raise UserError(
                    _("Quality inspection is required but some items have not passed inspection or are still pending.")
                )

            record.write({
                'state': 'approved_by_finance',
                'finance_approved_by': self.env.user.id,
            })
            record._notify_finance_approved()
