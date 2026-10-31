from odoo import models, api
import logging


class ResUsers(models.Model):
    _inherit = 'res.users'

    @api.model
    def systray_identity(self):
        return {
            'user_id': self.env.uid,
            'partner_id': self.env.user.partner_id.id,
        }
