from odoo import models, fields, api, _
from odoo.exceptions import AccessError, UserError, ValidationError

GROUP_DEPT_MANAGER = "hr_performance.group_dept_manager"
GROUP_HR_MANAGER = "hr_performance.group_hr_manager"
GROUP_CEO = "hr_performance.group_ceo"

# Roles that run the appraisal process (everyone else is "just" an employee).
STAFF_GROUPS = (GROUP_DEPT_MANAGER, GROUP_HR_MANAGER, GROUP_CEO)
STAFF_GROUPS_CSV = ",".join(STAFF_GROUPS)

# Fields each non-HR participant may write on the appraisal, and when.
EMPLOYEE_WRITABLE_FIELDS = {"employee_comment", "line_ids"}
MANAGER_WRITABLE_FIELDS = {"manager_comment", "line_ids"}


def is_hr(env):
    return env.su or env.user.has_group(GROUP_HR_MANAGER)


def compute_grade(percentage):
    if percentage >= 90:
        return "Outstanding"
    if percentage >= 76:
        return "Very Good"
    if percentage >= 60:
        return "Good"
    return "Needs Improvement"


class HrPerformanceAppraisal(models.Model):
    _name = "hr.performance.appraisal"
    _description = "Performance Appraisal"
    _inherit = ["mail.thread", "mail.activity.mixin"]

    employee_id = fields.Many2one(
        "hr.employee",
        string="Employee",
        required=True,
        tracking=True,
    )

    department_id = fields.Many2one(
        "hr.department",
        string="Department",
        required=True,
    )

    manager_id = fields.Many2one(
        "hr.employee",
        string="Department Manager",
        help="Scores the appraisal after the employee when "
             "'Include Department Manager' is ticked.",
    )

    include_employee = fields.Boolean(
        string="Include Employee",
        default=True,
        help="If ticked, the employee first answers the questions "
             "(self-assessment). Otherwise the employee is skipped.",
        tracking=True,
    )

    include_dept_manager = fields.Boolean(
        string="Include Department Manager",
        help="If ticked, the appraisal goes Employee -> Department Manager "
             "(scores) -> HR (scores again). Otherwise Employee -> HR.",
        tracking=True,
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

    date_from = fields.Date(required=True)
    date_to = fields.Date(required=True)

    appraisal_type = fields.Selection(
        [("half", "Half Year"), ("annual", "Annual")],
        required=True,
    )

    state = fields.Selection(
        [
            ("draft", "Draft"),
            ("employee", "Employee Self-Assessment"),
            ("manager", "Department Manager Scoring"),
            ("submitted", "HR Scoring"),
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

    # Final result = HR scores
    total_score = fields.Float(
        compute="_compute_scores", store=True, groups=STAFF_GROUPS_CSV,
    )
    percentage_score = fields.Float(
        compute="_compute_scores", store=True, groups=STAFF_GROUPS_CSV,
    )
    final_grade = fields.Char(
        compute="_compute_scores", store=True, groups=STAFF_GROUPS_CSV,
    )

    # Department manager's scores, shown next to HR's for comparison
    manager_total_score = fields.Float(
        string="Manager Total", compute="_compute_scores", store=True,
        groups=STAFF_GROUPS_CSV,
    )
    manager_percentage_score = fields.Float(
        string="Manager Percentage", compute="_compute_scores", store=True,
        groups=STAFF_GROUPS_CSV,
    )
    manager_grade = fields.Char(
        string="Manager Grade", compute="_compute_scores", store=True,
        groups=STAFF_GROUPS_CSV,
    )

    manager_comment = fields.Text(groups=STAFF_GROUPS_CSV)
    hr_comment = fields.Text(groups=STAFF_GROUPS_CSV)

    # Employee self-assessment
    employee_comment = fields.Text(string="Employee Comments")
    self_assessment_done = fields.Boolean(
        string="Self-Assessment Submitted", readonly=True, copy=False,
    )
    self_assessment_date = fields.Datetime(
        string="Self-Assessment Date", readonly=True, copy=False,
    )

    # UI permission helpers (per current user)
    is_hr_user = fields.Boolean(compute="_compute_user_roles", compute_sudo=True)
    is_appraised_employee = fields.Boolean(
        compute="_compute_user_roles", compute_sudo=True,
    )
    is_assigned_manager = fields.Boolean(
        compute="_compute_user_roles", compute_sudo=True,
    )
    can_employee_answer = fields.Boolean(
        compute="_compute_user_roles", compute_sudo=True,
    )
    can_manager_score = fields.Boolean(
        compute="_compute_user_roles", compute_sudo=True,
    )
    can_hr_score = fields.Boolean(
        compute="_compute_user_roles", compute_sudo=True,
    )

    @api.depends_context("uid")
    @api.depends("state", "employee_id.user_id", "manager_id.user_id",
                 "include_dept_manager")
    def _compute_user_roles(self):
        user = self.env.user
        hr = user.has_group(GROUP_HR_MANAGER)
        for rec in self:
            rec.is_hr_user = hr
            rec.is_appraised_employee = rec.employee_id.user_id == user
            rec.is_assigned_manager = bool(
                rec.include_dept_manager and rec.manager_id.user_id == user
            )
            rec.can_employee_answer = (
                rec.state == "employee" and rec.is_appraised_employee
            )
            rec.can_manager_score = (
                rec.state == "manager" and rec.is_assigned_manager
            )
            rec.can_hr_score = rec.state == "submitted" and hr

    @api.onchange("employee_id")
    def _onchange_employee_id(self):
        if self.employee_id.department_id:
            self.department_id = self.employee_id.department_id
        self.target_job_id = False

    @api.onchange("department_id")
    def _onchange_department_id(self):
        self.manager_id = self.department_id.manager_id
        if self.target_job_id.department_id != self.department_id:
            self.target_job_id = False

    @api.constrains("date_from", "date_to")
    def _check_dates(self):
        for rec in self:
            if rec.date_from and rec.date_to and rec.date_from > rec.date_to:
                raise ValidationError(
                    _("The 'From' date must be earlier than the 'To' date.")
                )

    @api.constrains("employee_id", "appraisal_type", "date_from", "date_to")
    def _check_no_duplicate_appraisal(self):
        for rec in self:
            duplicate = self.sudo().search([
                ("employee_id", "=", rec.employee_id.id),
                ("appraisal_type", "=", rec.appraisal_type),
                ("date_from", "=", rec.date_from),
                ("date_to", "=", rec.date_to),
                ("id", "!=", rec.id),
            ], limit=1)
            if duplicate:
                raise ValidationError(
                    _("An appraisal already exists for employee '%s' "
                      "with the same type and period.")
                    % rec.employee_id.name
                )

    @api.depends("line_ids.score_value", "line_ids.is_na",
                 "line_ids.manager_score")
    def _compute_scores(self):
        for rec in self:
            hr_lines = rec.line_ids.filtered(lambda l: not l.is_na)
            total = sum(hr_lines.mapped("score_value"))
            rec.total_score = total
            rec.percentage_score = (
                total / (len(hr_lines) * 5) * 100 if hr_lines else 0
            )
            rec.final_grade = compute_grade(rec.percentage_score)

            mgr_lines = rec.line_ids.filtered(lambda l: l.manager_score)
            mgr_total = sum(int(s) for s in mgr_lines.mapped("manager_score"))
            rec.manager_total_score = mgr_total
            rec.manager_percentage_score = (
                mgr_total / (len(mgr_lines) * 5) * 100 if mgr_lines else 0
            )
            rec.manager_grade = (
                compute_grade(rec.manager_percentage_score) if mgr_lines else False
            )

    # ------------------------------------------------------------------
    # Access guards
    # ------------------------------------------------------------------

    def write(self, vals):
        if not is_hr(self.env):
            keys = set(vals)
            for rec in self:
                if rec.can_employee_answer and keys <= EMPLOYEE_WRITABLE_FIELDS:
                    continue
                if rec.can_manager_score and keys <= MANAGER_WRITABLE_FIELDS:
                    continue
                raise AccessError(
                    _("You cannot modify this appraisal at its current stage.")
                )
        return super().write(vals)

    def _check_hr(self):
        if not is_hr(self.env):
            raise AccessError(_("Only HR Managers can do this."))

    def _check_state(self, *states):
        labels = dict(self._fields["state"].selection)
        for rec in self:
            if rec.state not in states:
                raise UserError(
                    _("This action is not allowed while the appraisal is in "
                      "state '%s'.") % labels[rec.state]
                )

    # ------------------------------------------------------------------
    # Workflow
    # ------------------------------------------------------------------

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
        Template = self.env["hr.performance.template"].sudo()

        if dept:
            template = Template.search(
                [("active", "=", True), ("department_ids", "in", dept.id)],
                limit=1,
            )
            if template:
                return template

        template = Template.search(
            [("active", "=", True), ("department_ids", "=", False)], limit=1,
        )
        if template:
            return template

        raise UserError(
            _("No active evaluation template found for department '%s'. "
              "Please configure one under Performance > Evaluation Templates.")
            % (dept.name if dept else _("(unknown)"))
        )

    def action_load_questions(self):
        self.ensure_one()
        self._check_hr()
        self._check_state("draft")
        template = self._get_template_for_department()
        self.sudo().line_ids.unlink()
        self.sudo().write({
            "template_id": template.id,
            "self_assessment_done": False,
            "self_assessment_date": False,
            "employee_comment": False,
        })
        Line = self.env["hr.performance.appraisal.line"].sudo()
        for q in template.question_ids:
            Line.create({"appraisal_id": self.id, "question_id": q.id})

    def action_start(self):
        """HR starts the appraisal. It goes to the employee (if included),
        else to the department manager (if included), else straight to
        HR scoring."""
        self._check_hr()
        self._check_state("draft")
        for rec in self:
            if not rec.line_ids:
                raise UserError(_("Load the questions before starting the "
                                  "appraisal."))
            if rec.include_dept_manager:
                rec._check_manager_user()
            if not rec.include_employee:
                rec._move_after_employee()
                continue
            employee_user = rec.employee_id.user_id
            if not employee_user:
                raise UserError(
                    _("Employee '%s' has no linked user account, so they "
                      "cannot fill in the self-assessment. Untick "
                      "'Include Employee' to skip them.")
                    % rec.employee_id.name
                )
            rec.write({"state": "employee"})
            rec._notify(
                employee_user,
                _("Self-Assessment Requested"),
                _("Please answer the questions of your performance appraisal."),
            )

    def _check_manager_user(self):
        for rec in self:
            if not rec.manager_id:
                raise UserError(
                    _("Select the Department Manager, or untick "
                      "'Include Department Manager'.")
                )
            if not rec.manager_id.user_id:
                raise UserError(
                    _("Department Manager '%s' has no linked user account.")
                    % rec.manager_id.name
                )

    def _move_after_employee(self):
        """Next stage after the (optional) employee step: manager (if
        included) or HR."""
        for rec in self.sudo():
            employee_name = rec.employee_id.name
            if rec.include_dept_manager:
                rec._check_manager_user()
                rec.write({"state": "manager"})
                rec._notify(
                    rec.manager_id.user_id,
                    _("Appraisal Ready for Your Scoring"),
                    _("Please score the performance appraisal of %s.")
                    % employee_name,
                )
            else:
                rec.write({"state": "submitted"})
                if rec.include_employee:
                    rec._notify_hr(
                        _("Appraisal Ready for HR Scoring"),
                        _("%s has completed their self-assessment. Please "
                          "score the appraisal.") % employee_name,
                    )

    def action_submit_self_assessment(self):
        for rec in self:
            if not rec.can_employee_answer:
                raise AccessError(
                    _("Only the appraised employee can submit this "
                      "self-assessment.")
                )
            rec.sudo().write({
                "self_assessment_done": True,
                "self_assessment_date": fields.Datetime.now(),
            })
        self._move_after_employee()

    def action_skip_employee(self):
        """HR moves on without waiting for the employee."""
        self._check_hr()
        self._check_state("employee")
        self._move_after_employee()

    def action_manager_submit(self):
        for rec in self:
            if not (rec.can_manager_score or (is_hr(self.env) and rec.state == "manager")):
                raise AccessError(
                    _("Only the assigned Department Manager can submit "
                      "these scores.")
                )
            if not is_hr(self.env) and not rec.line_ids.filtered("manager_score"):
                raise UserError(_("Please score at least one question."))
        for rec in self.sudo():
            rec.write({"state": "submitted"})
            rec._notify_hr(
                _("Appraisal Ready for HR Scoring"),
                _("%s has scored the appraisal of %s. Please give the HR score.")
                % (rec.manager_id.name, rec.employee_id.name),
            )

    def action_review(self):
        self._check_hr()
        self._check_state("submitted")
        self.write({"state": "reviewed"})

    def action_done(self):
        self._check_hr()
        self._check_state("reviewed")
        self.write({"state": "done"})
        # Only the department manager (if involved) is told; the employee
        # is intentionally not notified when the appraisal is finished.
        for rec in self.sudo():
            if rec.include_dept_manager and rec.manager_id.user_id:
                rec._notify(
                    rec.manager_id.user_id,
                    _("Performance Appraisal Approved"),
                    _("The appraisal for employee %s has been completed and "
                      "approved.") % rec.employee_id.name,
                )

    # ------------------------------------------------------------------
    # Notifications
    # ------------------------------------------------------------------

    def _notify(self, users, title, message):
        self.ensure_one()
        for user in users:
            self.env["generic.notification"].send_notification(
                user_id=user.id,
                title=title,
                message=message,
                res_model=self._name,
                res_id=self.id,
            )

    def _notify_hr(self, title, message):
        hr_users = self.env.ref(GROUP_HR_MANAGER).sudo().users
        self._notify(hr_users, title, message)
