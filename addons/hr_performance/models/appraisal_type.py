from odoo import models, fields


class HrPerformanceAppraisalType(models.Model):
    _name = "hr.performance.appraisal.type"
    _description = "Performance Appraisal Type"
    _order = "sequence, name"

    name = fields.Char(required=True, translate=True)
    period = fields.Selection(
        [("half", "Half Year"), ("annual", "Annual")],
        string="Period",
        required=True,
        default="annual",
    )
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    description = fields.Text()

    _sql_constraints = [
        ("name_unique", "unique(name)", "An appraisal type with this name already exists."),
    ]
