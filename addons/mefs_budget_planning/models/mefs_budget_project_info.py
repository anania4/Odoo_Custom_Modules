from odoo import api, fields, models


class MefsBudgetProjectInfo(models.Model):
    """Budget Schedule dashboard data of a project (one record per project):
    the selected budget plan and the planned income / expense lines.
    """
    _name = 'mefs.budget.project.info'
    _description = 'Budget Dashboard Project Data'
    _rec_name = 'project_id'

    project_id = fields.Many2one(
        'project.project', string='Project', required=True, ondelete='cascade')
    company_id = fields.Many2one(
        'res.company', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(
        'res.currency', related='company_id.currency_id', readonly=True)
    budget_plan_id = fields.Many2one(
        'mefs.budget.plan', string='Budget Plan', ondelete='set null',
        domain="[('project_id', '=', project_id)]",
        help='Budget plan whose Project Estimated Cost fills the Planned Expense Summary.')

    income_line_ids = fields.One2many(
        'mefs.budget.income.line', 'info_id', string='Planned Income Summary')
    expense_line_ids = fields.One2many(
        'mefs.budget.expense.line', 'info_id', string='Total Planned Expenses Summary')

    _sql_constraints = [
        ('project_uniq', 'unique(project_id)',
         'Dashboard data already exists for this project.'),
    ]

    # Estimate cost blocks: (class field, total field)
    _ESTIMATE_BLOCKS = [
        ('material_categ_id', 'total_material_cost'),
        ('equipment_categ_id', 'total_equipment_cost'),
        ('labour_categ_id', 'total_manpower_cost'),
        ('subcontract_categ_id', 'total_subcontractor_cost'),
    ]

    @api.model
    def _get_plan_expense_vals(self, plan):
        """One expense line per cost class of the plan's Project Estimated Cost.

        Each block total goes to its class (Material Class, Equipment Class,
        Labour Class, Subcontracting Class); amounts without a class are skipped.
        Classes keep the order they first appear in (material, equipment,
        manpower, subcontractor).
        """
        if not plan:
            return []
        totals = {}
        lines = plan.estimate_line_ids.sorted(lambda l: (l.sequence, l.id))
        for categ_field, total_field in self._ESTIMATE_BLOCKS:
            for line in lines:
                categ = line[categ_field]
                amount = line[total_field]
                if categ and amount:
                    totals[categ.id] = totals.get(categ.id, 0.0) + amount
        return [{
            'cost_type_id': categ_id,
            'amount': amount,
            'is_auto': True,
            'sequence': (index + 1) * 10,
        } for index, (categ_id, amount) in enumerate(totals.items())]

    def _sync_expense_lines(self):
        """Replace the lines fetched from the budget plan; manual lines stay."""
        Line = self.env['mefs.budget.expense.line']
        for info in self:
            info.expense_line_ids.filtered('is_auto').unlink()
            Line.create([
                dict(vals, info_id=info.id)
                for vals in self._get_plan_expense_vals(info.budget_plan_id)
            ])

    @api.model
    def _latest_plan(self, project):
        return self.env['mefs.budget.plan'].search(
            [('project_id', '=', project.id)], order='id desc', limit=1)

    @api.model
    def _ensure_for_projects(self, projects=None):
        """Create the dashboard data record of every project that has none."""
        projects = projects if projects is not None else self.env['project.project'].search([])
        existing = self.search([('project_id', 'in', projects.ids)]).project_id
        missing = projects - existing
        if missing:
            self.create([{
                'project_id': project.id,
                'budget_plan_id': self._latest_plan(project).id,
                'company_id': (project.company_id or self.env.company).id,
            } for project in missing])


class MefsBudgetIncomeLine(models.Model):
    _name = 'mefs.budget.income.line'
    _description = 'Budget Dashboard Planned Income'
    _order = 'info_id, sequence, id'

    info_id = fields.Many2one(
        'mefs.budget.project.info', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='info_id.currency_id')
    sequence = fields.Integer(default=10)
    work_type_id = fields.Many2one(
        'mefs.boq.work.type', string='Work Type', required=True)
    amount = fields.Monetary(string='Amount')
    cumulative_income = fields.Monetary(
        string='Cumulative Income', compute='_compute_cumulative_income', store=True)
    date = fields.Date(string='Date')

    @api.depends('info_id.income_line_ids.amount', 'info_id.income_line_ids.sequence')
    def _compute_cumulative_income(self):
        self.cumulative_income = 0.0
        for info in self.info_id:
            running = 0.0
            for line in info.income_line_ids.sorted(lambda l: (l.sequence, l._origin.id or 0)):
                running += line.amount
                line.cumulative_income = running


class MefsBudgetExpenseLine(models.Model):
    _name = 'mefs.budget.expense.line'
    _description = 'Budget Dashboard Planned Expense'
    _order = 'info_id, sequence, id'

    info_id = fields.Many2one(
        'mefs.budget.project.info', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='info_id.currency_id')
    sequence = fields.Integer(default=1000)
    is_auto = fields.Boolean(
        string='From Budget Plan',
        help='Filled from the budget plan; refreshed when the plan changes.')
    cost_type_id = fields.Many2one(
        'product.category', string='Cost Type', required=True,
        help='Cost class, as used in the Project Estimated Cost of the budget plan.')
    amount = fields.Monetary(string='Amount')
    cost_percent = fields.Float(
        string='% of Cost', compute='_compute_cost_percent', store=True,
        help='Share of this cost type in the total planned expenses.')

    @api.depends('info_id.expense_line_ids.amount')
    def _compute_cost_percent(self):
        self.cost_percent = 0.0
        for info in self.info_id:
            lines = info.expense_line_ids
            total = sum(lines.mapped('amount'))
            for line in lines:
                line.cost_percent = (line.amount / total) if total else 0.0
