from odoo import models, fields


class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    stock_move_sms_validation = fields.Boolean(
        string="Stock Move SMS Validation",
        config_parameter='stock.stock_move_sms_validation',
        default=False,
        help="Enable SMS validation for stock moves"
    )

    stock_sms_confirmation_template_id = fields.Many2one(
        'sms.template',
        string="Stock SMS Confirmation Template",
        config_parameter='stock.stock_sms_confirmation_template_id',
        domain=[('model', '=', 'stock.picking')],
        help="SMS template used for stock confirmation"
    )

