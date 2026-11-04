from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


class MefsBudgetPlan(models.Model):
    _name = 'mefs.budget.plan'
    _description = 'Budget Plan'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(
        string='Reference', required=True, copy=False, readonly=True,
        default=lambda self: _('New'))
    composed_by_id = fields.Many2one(
        'hr.employee', string='Composed By', required=True, tracking=True,
        default=lambda self: self.env.user.employee_id)
    date = fields.Date(
        string='Date', required=True, readonly=True, copy=False,
        default=fields.Date.context_today)
    project_id = fields.Many2one(
        'project.project', string='Project', required=True, tracking=True)
    boq_id = fields.Many2one(
        'mefs.boq', string='BOQ', required=True, tracking=True,
        domain="[('project_id', '=', project_id), ('state', '=', 'locked')]",
        help='Approved BOQ of the selected project.')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)

    estimate_line_ids = fields.One2many(
        'mefs.budget.estimate.line', 'plan_id',
        string='Project Estimated Cost', copy=True)

    total_material_cost = fields.Monetary(
        string='Total Material Cost', compute='_compute_totals', store=True)
    total_equipment_cost = fields.Monetary(
        string='Total Equipment Cost', compute='_compute_totals', store=True)
    total_manpower_cost = fields.Monetary(
        string='Total Manpower Cost', compute='_compute_totals', store=True)
    total_subcontractor_cost = fields.Monetary(
        string='Total Subcontractor Cost', compute='_compute_totals', store=True)
    total_estimated_cost = fields.Monetary(
        string='Total Estimated Cost', compute='_compute_totals', store=True)

    @api.depends(
        'estimate_line_ids.total_material_cost',
        'estimate_line_ids.total_equipment_cost',
        'estimate_line_ids.total_manpower_cost',
        'estimate_line_ids.total_subcontractor_cost')
    def _compute_totals(self):
        for plan in self:
            lines = plan.estimate_line_ids
            plan.total_material_cost = sum(lines.mapped('total_material_cost'))
            plan.total_equipment_cost = sum(lines.mapped('total_equipment_cost'))
            plan.total_manpower_cost = sum(lines.mapped('total_manpower_cost'))
            plan.total_subcontractor_cost = sum(lines.mapped('total_subcontractor_cost'))
            plan.total_estimated_cost = (
                plan.total_material_cost + plan.total_equipment_cost
                + plan.total_manpower_cost + plan.total_subcontractor_cost)

    @api.onchange('project_id')
    def _onchange_project_id(self):
        if self.boq_id and self.boq_id.project_id != self.project_id:
            self.boq_id = False
        if self.project_id and not self.boq_id:
            boqs = self.env['mefs.boq'].search([
                ('project_id', '=', self.project_id.id),
                ('state', '=', 'locked'),
            ], limit=2)
            if len(boqs) == 1:
                self.boq_id = boqs

    @api.onchange('boq_id')
    def _onchange_boq_id(self):
        """Fill the estimate with one row per work item of the selected BOQ.

        Existing rows are moved to the matching item of the new BOQ (by item
        code, then by work item name); rows with no match are removed and
        BOQ items without a row get a new one.
        """
        if not self.boq_id:
            self.estimate_line_ids = [(5, 0, 0)]
            return
        items = self.boq_id._get_budget_work_items()
        by_code = {i.code: i for i in items if i.code}
        by_name = {}
        for item in items:
            by_name.setdefault((item.name or '').strip().lower(), item)
        for line in self.estimate_line_ids:
            old = line.boq_line_id
            if old.boq_id == self.boq_id:
                continue
            match = by_code.get(old.code) or by_name.get((old.name or '').strip().lower())
            if match:
                line.boq_line_id = match
            else:
                self.estimate_line_ids -= line

        covered = self.estimate_line_ids.boq_line_id
        Line = self.env['mefs.budget.estimate.line']
        for item in items - covered:
            self.estimate_line_ids += Line.new({'boq_line_id': item.id})
        # Keep rows in BOQ order; extra material rows stay with their item.
        position = {item.id: index for index, item in enumerate(items)}
        for line in self.estimate_line_ids:
            line.sequence = (position.get(line.boq_line_id.id, len(items)) + 1) * 10

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('mefs.budget.plan') or _('New')
        return super().create(vals_list)

    @api.constrains('boq_id', 'project_id')
    def _check_boq(self):
        for plan in self:
            if plan.boq_id.project_id != plan.project_id:
                raise ValidationError(_('The BOQ must belong to the selected project.'))
            if plan.boq_id.state != 'locked':
                raise ValidationError(_('Only an approved BOQ can be used for budget planning.'))

    @api.constrains('estimate_line_ids', 'boq_id')
    def _check_lines_boq(self):
        for plan in self:
            if any(line.boq_line_id.boq_id != plan.boq_id for line in plan.estimate_line_ids):
                raise ValidationError(_('All estimated cost lines must use items of the selected BOQ.'))
