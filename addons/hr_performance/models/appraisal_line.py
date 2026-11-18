from odoo import models, fields, api, _
from odoo.exceptions import AccessError

from .appraisal import STAFF_GROUPS_CSV, is_hr

SCORE_SELECTION = [
    ("0", "0"), ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5"),
]

# Who may write which line field, expressed as the appraisal flag that
# must be true for the current user.
FIELD_PERMISSION = {
    "employee_score": "can_employee_answer",
    "employee_comment": "can_employee_answer",
    "manager_score": "can_manager_score",
    "score": "can_hr_score",
    "is_na": "can_hr_score",
}


class HrPerformanceAppraisalLine(models.Model):
    _name = "hr.performance.appraisal.line"
    _description = "Performance Appraisal Line"
    _order = "question_section, id"

    appraisal_id = fields.Many2one(
        "hr.performance.appraisal", ondelete="cascade"
    )
    question_id = fields.Many2one(
        "hr.performance.question", required=True
    )
    question_section = fields.Selection(
        related="question_id.section",
        string="Section",
        store=True,
        readonly=True,
    )

    # 1. Employee self-assessment (never counts toward the grade)
    employee_score = fields.Selection(SCORE_SELECTION, string="Self Score")
    employee_comment = fields.Text(string="Employee Answer")

    # 2. Department manager score (optional stage, shown for comparison)
    manager_score = fields.Selection(
        SCORE_SELECTION, string="Manager Score", groups=STAFF_GROUPS_CSV,
    )

    # 3. HR score (final, drives the grade)
    score = fields.Selection(
        SCORE_SELECTION, string="HR Score", groups=STAFF_GROUPS_CSV,
    )
    score_value = fields.Integer(
        compute="_compute_score_value", store=True, groups=STAFF_GROUPS_CSV,
    )
    is_na = fields.Boolean(string="N/A", groups=STAFF_GROUPS_CSV)

    @api.depends("score", "is_na")
    def _compute_score_value(self):
        for rec in self:
            if rec.is_na or not rec.score:
                rec.score_value = 0
            else:
                rec.score_value = int(rec.score)

    def write(self, vals):
        if not self.env.su:
            for field_name in vals:
                flag = FIELD_PERMISSION.get(field_name)
                for line in self:
                    allowed = (
                        getattr(line.appraisal_id, flag) if flag
                        else is_hr(self.env)
                    )
                    if not allowed:
                        raise AccessError(
                            _("You cannot change '%s' at this stage of the "
                              "appraisal.")
                            % self._fields[field_name].string
                        )
        return super().write(vals)
