from odoo import models, fields, api, _


class HrPerformanceAppraisal(models.Model):
    _name = "hr.performance.appraisal"
    _description = "Performance Appraisal"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    manager_id = fields.Many2one(
        "hr.employee",
        string="Manager",
        default=lambda self: self.env["hr.employee"].search(
            [("user_id", "=", self.env.uid)], limit=1
        ),
        readonly=True,
    )

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        domain="[('department_id', '=', department_id)]",
        required=True,
    )

    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        default=lambda self: self.env["hr.employee"].search(
            [("user_id", "=", self.env.uid)], limit=1
        ).department_id,
        required=True,
    )

    target_job_id = fields.Many2one(
        "hr.job",
        string="Target Position",
        domain="[('department_id', '=', department_id)]",
        required=True,
    )

    template_id = fields.Many2one(
        "hr.performance.template",
        string="Evaluation Template",
        readonly=True,
    )



    can_edit_manager_comment = fields.Boolean(
        compute="_compute_edit_permissions",
        compute_sudo=True,
        store=False,
    )
    can_edit_hr_comment = fields.Boolean(
        compute="_compute_edit_permissions",
        compute_sudo=True,
        store=False,
    )

    @api.onchange('employee_id')
    def _onchange_employee_id(self):
        if self.employee_id and self.employee_id.department_id:
            self.department_id = self.employee_id.department_id
        self.target_job_id = False

    @api.onchange('department_id')
    def _onchange_department_id(self):
        self.target_job_id = False

    @api.depends_context("uid")
    def _compute_edit_permissions(self):
        user = self.env.user
        is_hr_manager = user.has_group("hr_performance.group_hr_manager")
        is_dept_manager = user.has_group("hr_performance.group_dept_manager")
        for appraisal in self:
            appraisal.can_edit_manager_comment = is_dept_manager
            appraisal.can_edit_hr_comment = is_hr_manager

    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)

    appraisal_type = fields.Selection(
        [("half", "Half Year"), ("annual", "Annual")],
        required=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("submitted", "Submitted to HR"),
            ("reviewed", "HR Reviewed"),
            ("done", "Promoted"),
        ],
        default="draft",
        tracking=True,
    )

    line_ids = fields.One2many(
        "hr.performance.appraisal.line",
        "appraisal_id",
        string="Evaluation Lines",
    )

    total_score = fields.Float(compute="_compute_scores", store=True)
    percentage_score = fields.Float(compute="_compute_scores", store=True)
    final_grade = fields.Char(compute="_compute_scores", store=True)

    manager_comment = fields.Text()
    hr_comment = fields.Text()

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise models.ValidationError(
                    _("The 'From' date must be earlier than the 'To' date.")
                )

    @api.constrains("employee_id", "appraisal_type", "date_from", "date_to")
    def _check_no_duplicate_appraisal(self):
        for rec in self:
            duplicate = self.search([
                ("employee_id", "=", rec.employee_id.id),
                ("appraisal_type", "=", rec.appraisal_type),
                ("date_from", "=", rec.date_from),
                ("date_to", "=", rec.date_to),
                ("id", "!=", rec.id),
            ], limit=1)
            if duplicate:
                raise models.ValidationError(
                    _("An appraisal already exists for employee '%s' "
                      "with the same type and period.")
                    % rec.employee_id.name
                )

    @api.depends("line_ids.score_value", "line_ids.is_na")
    def _compute_scores(self):
        for rec in self:
            total_score = 0
            total_count = 0
            for line in rec.line_ids:
                if not line.is_na:
                    total_score += line.score_value
                    total_count += 1
            rec.total_score = total_score
            rec.percentage_score = (
                (total_score / (total_count * 5)) * 100 if total_count else 0
            )
            if rec.percentage_score >= 90:
                rec.final_grade = "Outstanding"
            elif rec.percentage_score >= 76:
                rec.final_grade = "Very Good"
            elif rec.percentage_score >= 60:
                rec.final_grade = "Good"
            else:
                rec.final_grade = "Needs Improvement"

    def _get_template_for_department(self):
        """
        Resolve the correct template for this appraisal's department.
        Priority:
          1. Active template explicitly assigned to this department.
          2. Active default template (no departments assigned = applies to all).
        Raises a user-friendly error if nothing is found.
        """
        self.ensure_one()
        dept = self.department_id

        # 1. Department-specific template
        if dept:
            template = self.env["hr.performance.template"].sudo().search(
                [("active", "=", True), ("department_ids", "in", dept.id)],
                limit=1,
            )
            if template:
                return template

        # 2. Default template (no departments linked = global fallback)
        template = self.env["hr.performance.template"].sudo().search(
            [("active", "=", True), ("department_ids", "=", False)],
            limit=1,
        )
        if template:
            return template

        raise models.UserError(
            _("No active evaluation template found for department '%s'. "
              "Please ask HR to configure one under "
              "Performance > Evaluation Templates.")
            % (dept.name if dept else _("(unknown)"))
        )

    def action_load_questions(self):
        self.ensure_one()
        template = self._get_template_for_department()
        self.sudo().line_ids.unlink()
        self.sudo().write({'template_id': template.id})
        for q in template.question_ids:
            self.env['hr.performance.appraisal.line'].sudo().create({
                'appraisal_id': self.id,
                'question_id': q.id,
            })

    def action_submit(self):
        self.state = "submitted"
        self.action_notify_hr_for_performance_appraisal()

    def action_review(self):
        self.state = "reviewed"

    def action_done(self):
        self.state = "done"
        self.action_notify_dept_for_performance_appraisal_done()
        self.action_notify_employee_their_performance_appraisal_done()

    def action_notify_hr_for_performance_appraisal(self):
        for record in self:
            group = self.env.ref("hr_performance.group_hr_manager")
            for user in group.users:
                self.env["generic.notification"].send_notification(
                    user_id=user.id,
                    title=_("Appraisal Request Submitted by %s") % record.manager_id.name,
                    message=_(
                        "An appraisal has been requested for employee %s."
                    ) % record.employee_id.name,
                    res_model=record._name,
                    res_id=record.id,
                )

    def action_notify_dept_for_performance_appraisal_done(self):
        """
        FIX: Notify ONLY the manager of the evaluated employee's department,
        not all department managers globally.
        """
        for record in self:
            manager_user = record.department_id.manager_id.user_id
            if not manager_user:
                continue
            self.env["generic.notification"].send_notification(
                user_id=manager_user.id,
                title=_("Performance Appraisal Approved"),
                message=_(
                    "The appraisal for employee %s has been completed and approved."
                ) % record.employee_id.name,
                res_model=record._name,
                res_id=record.id,
            )

    def action_notify_employee_their_performance_appraisal_done(self):
        for record in self:
            user = record.employee_id.user_id
            if not user:
                continue
            self.env["generic.notification"].send_notification(
                user_id=user.id,
                title=_("Your Performance Appraisal Has Been Approved"),
                message=_(
                    "Your performance appraisal has been reviewed and approved by HR."
                ),
                res_model=record._name,
                res_id=record.id,
            )
