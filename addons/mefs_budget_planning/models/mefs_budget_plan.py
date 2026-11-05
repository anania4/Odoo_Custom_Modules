from datetime import timedelta

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

    project_start_date = fields.Date(string='Project Start Date', tracking=True)
    project_end_date = fields.Date(
        string='Project End Date', compute='_compute_project_end_date', store=True,
        help='Latest end date in the project schedule.')

    estimate_line_ids = fields.One2many(
        'mefs.budget.estimate.line', 'plan_id',
        string='Project Estimated Cost', copy=True)
    schedule_line_ids = fields.One2many(
        'mefs.budget.schedule.line', 'plan_id',
        string='Project Schedule', copy=True)

    @api.depends('schedule_line_ids.date_end')
    def _compute_project_end_date(self):
        for plan in self:
            ends = [d for d in plan.schedule_line_ids.mapped('date_end') if d]
            plan.project_end_date = max(ends) if ends else False

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
        """Fill the estimate and the schedule with one row per BOQ work item."""
        self._sync_lines_with_boq('estimate_line_ids', 'mefs.budget.estimate.line')
        self._sync_lines_with_boq('schedule_line_ids', 'mefs.budget.schedule.line')

    @api.onchange('project_start_date')
    def _onchange_project_start_date(self):
        for line in self.schedule_line_ids:
            if not line.date_start:
                line.date_start = self.project_start_date

    @api.onchange('schedule_line_ids')
    def _onchange_schedule_line_ids(self):
        """When a planned duration changes by N days, shift every following
        task (start and end) by N days; their own durations stay the same.
        A first-time duration (previously empty) does not shift anything.
        """
        rows = list(self.schedule_line_ids.sorted('sequence'))
        for index, row in enumerate(rows):
            delta = row.duration_days - row.applied_duration_days
            if delta and row.applied_duration_days > 0:
                for following in rows[index + 1:]:
                    if following.date_start:
                        following.date_start += timedelta(days=delta)
            row.applied_duration_days = row.duration_days

    def _sync_lines_with_boq(self, field_name, line_model):
        """Existing rows are moved to the matching item of the new BOQ (by item
        code, then by work item name); rows with no match are removed and BOQ
        items without a row get a new one. Rows are kept in BOQ order.
        """
        if not self.boq_id:
            self[field_name] = [(5, 0, 0)]
            return
        items = self.boq_id._get_budget_work_items()
        by_code = {i.code: i for i in items if i.code}
        by_name = {}
        for item in items:
            by_name.setdefault((item.name or '').strip().lower(), item)
        for line in self[field_name]:
            old = line.boq_line_id
            if old.boq_id == self.boq_id:
                continue
            match = by_code.get(old.code) or by_name.get((old.name or '').strip().lower())
            if match:
                line.boq_line_id = match
            else:
                self[field_name] -= line

        covered = self[field_name].boq_line_id
        Line = self.env[line_model]
        for item in items - covered:
            vals = {'boq_line_id': item.id}
            if line_model == 'mefs.budget.schedule.line':
                vals['date_start'] = self.project_start_date
            self[field_name] += Line.new(vals)
        position = {item.id: index for index, item in enumerate(items)}
        for line in self[field_name]:
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

    @api.constrains('estimate_line_ids', 'schedule_line_ids', 'boq_id')
    def _check_lines_boq(self):
        for plan in self:
            lines = plan.estimate_line_ids.boq_line_id | plan.schedule_line_ids.boq_line_id
            if any(item.boq_id != plan.boq_id for item in lines):
                raise ValidationError(_('All estimated cost and schedule lines must use items of the selected BOQ.'))
