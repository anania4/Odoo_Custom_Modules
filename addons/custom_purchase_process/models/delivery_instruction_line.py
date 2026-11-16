from odoo import _, api, fields, models
from collections import defaultdict
from odoo.exceptions import ValidationError, UserError
from odoo.osv.expression import AND

from datetime import datetime, timedelta


class DeliveryInstructionLine(models.Model):
    _name = 'delivery.instruction.line'
    _description = 'Delivery Instruction Line'

    name = fields.Char(string="Remark", required=True)
    expected_date = fields.Date(string="Expected Date", required=True)
    quantity = fields.Float(string="Quantity", required=True)
    purchase_order_id = fields.Many2one('purchase.order', string="Purchase Order", required=True, ondelete='cascade')

