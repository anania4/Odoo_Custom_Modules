from odoo import models, fields, api, _


class HrPerformanceTemplate(models.Model):
    _name = "hr.performance.template"
    _description = "Performance Evaluation Template"

    name = fields.Char(required=True)
    active = fields.Boolean(default=True)
    description = fields.Text()

    department_ids = fields.Many2many(
        "hr.department",
        "hr_performance_template_department_rel",
        "template_id",
        "department_id",
        string="Departments",
    )

    department_manager_ids = fields.Many2many(
        "hr.employee",
        "hr_performance_template_manager_rel",
        "template_id",
        "employee_id",
        string="Managers",
        compute="_compute_department_info",
        store=True,
    )

    parent_department_ids = fields.Many2many(
        "hr.department",
        "hr_performance_template_parent_dept_rel",
        "template_id",
        "department_id",
        string="Parent Departments",
        compute="_compute_department_info",
        store=True,
    )

    @api.depends("department_ids", "department_ids.manager_id", "department_ids.parent_id")
    def _compute_department_info(self):
        for rec in self:
            rec.department_manager_ids = rec.department_ids.mapped("manager_id")
            rec.parent_department_ids = rec.department_ids.mapped("parent_id")

    question_ids = fields.Many2many(
        "hr.performance.question",
        "hr_performance_template_question_rel",
        "template_id",
        "question_id",
        string="Questions",
    )

    question_count = fields.Integer(compute="_compute_question_count")

    def _compute_question_count(self):
        for rec in self:
            rec.question_count = len(rec.question_ids)

    @api.constrains("question_ids")
    def _check_has_questions(self):
        for rec in self:
            if not rec.question_ids:
                raise models.ValidationError(
                    _("Template '%s' must have at least one question.") % rec.name
                )

    @api.constrains("department_ids", "active")
    def _check_unique_active_per_department(self):
        for rec in self:
            if not rec.active or not rec.department_ids:
                continue
            for dept in rec.department_ids:
                duplicates = self.search([
                    ("active", "=", True),
                    ("department_ids", "in", dept.id),
                    ("id", "!=", rec.id),
                ])
                if duplicates:
                    raise models.ValidationError(
                        _("Department '%s' already has an active template: '%s'. "
                          "Deactivate it before assigning a new one.")
                        % (dept.name, duplicates[0].name)
                    )
