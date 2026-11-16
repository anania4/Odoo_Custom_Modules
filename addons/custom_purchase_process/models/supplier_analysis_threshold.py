from odoo import models, fields

class OvertimeType(models.Model):
    _name = 'supplier_analysis.threshold'
    _description = 'Supplier Analysis thershold'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _bell_only_notifications = True


    name = fields.Char(required=True, tracking=True)
    multiplier = fields.Float(string="Thereshold value", required=True, tracking=True)
