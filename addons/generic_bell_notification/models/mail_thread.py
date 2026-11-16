from odoo import models


class MailThread(models.AbstractModel):
    _inherit = 'mail.thread'

    def _notify_thread(self, message, msg_vals=False, **kwargs):
        """Models with ``_bell_only_notifications = True`` notify through the bell
        and activities only: no Odoo inbox, email or push. The chatter keeps its history."""
        if getattr(self, '_bell_only_notifications', False):
            return []
        return super()._notify_thread(message, msg_vals=msg_vals, **kwargs)

    def unlink(self):
        """A deleted record needs no more action."""
        self.env['generic.notification'].sudo().clear_action_required(self)
        return super().unlink()
