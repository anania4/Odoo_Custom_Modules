from odoo import models, fields, api


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

    score = fields.Selection(
        [("0", "0"), ("1", "1"), ("2", "2"), ("3", "3"), ("4", "4"), ("5", "5")],
        string="Score",
    )
    score_value = fields.Integer(compute="_compute_score_value", store=True)
    is_na = fields.Boolean(string="N/A")

    @api.depends("score", "is_na")
    def _compute_score_value(self):
        for rec in self:
            if rec.is_na or not rec.score:
                rec.score_value = 0
            else:
                rec.score_value = int(rec.score)
