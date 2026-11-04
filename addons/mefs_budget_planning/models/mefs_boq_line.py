from odoo import api, models


class MefsBoq(models.Model):
    _inherit = 'mefs.boq'

    def _get_budget_work_items(self):
        """BOQ lines that are work items: every level, but no notes or subtotals."""
        self.ensure_one()
        return self.boq_line_ids.filtered(
            lambda l: l.display_type != 'line_note' and not l.is_subtotal).sorted(
            lambda l: (l.sequence, l.id))


class MefsBoqLine(models.Model):
    _inherit = 'mefs.boq.line'
    _rec_names_search = ['name', 'code', 'bill_no']

    @api.depends_context('mefs_budget_item_no')
    def _compute_display_name(self):
        if not self.env.context.get('mefs_budget_item_no'):
            return super()._compute_display_name()
        # In the budget estimate table the "Item No" column shows the BOQ Bill No.
        for line in self:
            line.display_name = line.bill_no or line.code or line.name or ''
