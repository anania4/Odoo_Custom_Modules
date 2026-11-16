from odoo import _, api, fields, models
from collections import defaultdict
from odoo.exceptions import ValidationError, UserError
from odoo.osv.expression import AND

from datetime import datetime, timedelta

class StockLocation(models.Model):
    _inherit = 'stock.location'

    located_company_id = fields.Many2one(
        'res.company',
        string="Located in",
        default=lambda self: self.env.company
    )

class StockPickingLine(models.Model):
    _inherit = 'stock.move'

    material_request_line_id = fields.Many2one("material.request.line")
    product_siv_line_id = fields.Many2one("product.siv.line")


class StockPickingUpdate(models.Model):
    _inherit = 'stock.picking'

    def button_validate(self):
        """Override button_validate to update material request lines and handle purchase order state."""
        # Avoid recursion by ensuring this is not re-entered
        if self._context.get('button_validate_recursion'):
            return super(StockPickingUpdate, self).button_validate()

        # Call the original button_validate method
        res = super(StockPickingUpdate, self.with_context(button_validate_recursion=True)).button_validate()

        # Update delivered_qty in material request lines
        for move in self.move_ids:
            if move.material_request_line_id:
                delivered_qty = move.quantity
                if delivered_qty > 0:
                    material_request_line = move.material_request_line_id
                    material_request_line.sudo().write({
                        'delivered_qty': material_request_line.delivered_qty + delivered_qty,
                    })


        return res


class StockPicking(models.Model):
    _inherit = 'stock.picking'

    siv_id = fields.Many2one('product.siv', string="SIV Reference")

    @api.model
    def action_done(self):
        res = super(StockPicking, self).action_done()

        # Check if this picking is linked to a product.siv
        for picking in self:
            if picking.siv_id:
                siv = picking.siv_id
                # Update the state of the associated product.siv to 'delivered'
                siv.state = 'delivered'

        return res


