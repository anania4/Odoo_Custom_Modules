from odoo import api, fields, models, _


class MefsBudgetDashboard(models.Model):
    """Budget Dashboard: one record per user holding the selected project.

    Every other field is related to the project's mefs.budget.project.info
    record, so all users see and edit the same data for a given project.
    """
    _name = 'mefs.budget.dashboard'
    _description = 'Budget Dashboard'

    user_id = fields.Many2one(
        'res.users', required=True, ondelete='cascade',
        default=lambda self: self.env.user)
    project_id = fields.Many2one('project.project', string='Project')
    info_id = fields.Many2one(
        'mefs.budget.project.info', compute='_compute_info_id')
    currency_id = fields.Many2one(related='info_id.currency_id')

    budget_plan_id = fields.Many2one(related='info_id.budget_plan_id', readonly=False)
    income_line_ids = fields.One2many(related='info_id.income_line_ids', readonly=False)
    expense_line_ids = fields.One2many(related='info_id.expense_line_ids', readonly=False)
    # Contract period, from the selected budget plan
    project_start_date = fields.Date(related='budget_plan_id.project_start_date')
    project_end_date = fields.Date(related='budget_plan_id.project_end_date')
    contract_period_days = fields.Integer(
        string='Contract Period', compute='_compute_contract_period_days',
        help='Days from the project start date to the end of the project schedule.')
    # Headline figures (computed from the live lines, so they follow edits)
    income_total = fields.Monetary(string='Planned Income', compute='_compute_kpis')
    expense_total = fields.Monetary(string='Planned Expenses', compute='_compute_kpis')
    margin_total = fields.Monetary(string='Planned Margin', compute='_compute_kpis')
    margin_percent = fields.Float(string='Margin %', compute='_compute_kpis')
    # Placeholders that host the chart widgets (they read the line fields)
    income_chart = fields.Char(string='Planned Income Chart', compute='_compute_chart_placeholders')
    income_cumulative_chart = fields.Char(
        string='Planned Cumulative Income Chart', compute='_compute_chart_placeholders')
    expense_chart = fields.Char(string='Planned Expenses Chart', compute='_compute_chart_placeholders')

    _sql_constraints = [
        ('user_uniq', 'unique(user_id)', 'Each user has a single budget dashboard.'),
    ]

    def _compute_display_name(self):
        for dashboard in self:
            dashboard.display_name = _('Budget Schedule')

    def _compute_chart_placeholders(self):
        self.income_chart = False
        self.income_cumulative_chart = False
        self.expense_chart = False

    @api.depends('project_start_date', 'project_end_date')
    def _compute_contract_period_days(self):
        for dashboard in self:
            start, end = dashboard.project_start_date, dashboard.project_end_date
            dashboard.contract_period_days = (end - start).days if start and end and end > start else 0

    @api.depends('income_line_ids.amount', 'expense_line_ids.amount')
    def _compute_kpis(self):
        for dashboard in self:
            income = sum(dashboard.income_line_ids.mapped('amount'))
            expense = sum(dashboard.expense_line_ids.mapped('amount'))
            dashboard.income_total = income
            dashboard.expense_total = expense
            dashboard.margin_total = income - expense
            dashboard.margin_percent = ((income - expense) / income) if income else 0.0

    @api.depends('project_id')
    def _compute_info_id(self):
        Info = self.env['mefs.budget.project.info']
        for dashboard in self:
            dashboard.info_id = Info.search(
                [('project_id', '=', dashboard.project_id.id)], limit=1
            ) if dashboard.project_id else False

    @api.onchange('income_line_ids')
    def _onchange_income_line_ids(self):
        """Keep the cumulative income column live while lines are being edited."""
        running = 0.0
        for line in self.income_line_ids.sorted(lambda l: (l.sequence, l._origin.id or 0)):
            running += line.amount
            line.cumulative_income = running

    @api.onchange('budget_plan_id')
    def _onchange_budget_plan_id(self):
        """Refill the expense rows fetched from the plan; manual rows stay."""
        Line = self.env['mefs.budget.expense.line']
        manual = self.expense_line_ids.filtered(lambda l: not l.is_auto)
        fetched = Line
        for vals in self.env['mefs.budget.project.info']._get_plan_expense_vals(self.budget_plan_id):
            fetched |= Line.new(vals)
        self.expense_line_ids = fetched | manual
        self._onchange_expense_line_ids()

    @api.onchange('expense_line_ids')
    def _onchange_expense_line_ids(self):
        """Keep % of cost and the total live while lines are being edited."""
        total = sum(self.expense_line_ids.mapped('amount'))
        for line in self.expense_line_ids:
            line.cost_percent = (line.amount / total) if total else 0.0

    def action_refresh_dashboard(self):
        """Re-fetch the expense rows from the budget plan and reload the page."""
        self.info_id._sync_expense_lines()
        return {'type': 'ir.actions.client', 'tag': 'soft_reload'}

    def action_save_dashboard(self):
        """The form saves itself before calling a button; nothing else to do."""
        return True

    @api.model
    def action_open_dashboard(self):
        self.env['mefs.budget.project.info']._ensure_for_projects()
        dashboard = self.search([('user_id', '=', self.env.uid)], limit=1)
        if not dashboard:
            default_project = self.env['mefs.budget.plan'].search([], limit=1).project_id
            dashboard = self.create({'project_id': default_project.id})
        info = dashboard.info_id
        if info:
            if not info.budget_plan_id:
                info.budget_plan_id = info._latest_plan(info.project_id)
            info._sync_expense_lines()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Budget Schedule'),
            'res_model': self._name,
            'res_id': dashboard.id,
            'view_mode': 'form',
            'views': [(self.env.ref('mefs_budget_planning.view_mefs_budget_dashboard_form').id, 'form')],
            'target': 'current',
        }


class ProjectProject(models.Model):
    _inherit = 'project.project'

    @api.model_create_multi
    def create(self, vals_list):
        projects = super().create(vals_list)
        self.env['mefs.budget.project.info'].sudo()._ensure_for_projects(projects)
        return projects
