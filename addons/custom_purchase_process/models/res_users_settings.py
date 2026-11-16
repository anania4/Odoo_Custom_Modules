from odoo import models, fields

class ResUserAccessControl(models.Model):
    _name = 'res.user.access.control'
    _description = 'User Access Control'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin"]
    _bell_only_notifications = True

    _sql_constraints = [
        ('unique_name_company', 'UNIQUE(name, company_id)', 'A committee with this name already exists in this company!')
    ]

    name = fields.Char(string="Committee Name", required=True, tracking=True)

    committee_user_ids = fields.Many2many(
        'res.users',
        string="Committee Members",
        required=True,
        tracking=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
        index=True,
        tracking=True,
        readonly=True
    )
