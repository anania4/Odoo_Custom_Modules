# -*- coding: utf-8 -*-

import logging

from odoo import SUPERUSER_ID, api, fields, models

_logger = logging.getLogger(__name__)


class GenericNotification(models.Model):
    _inherit = 'generic.notification'

    module_category = fields.Selection(
        selection_add=[('fleet', 'Fleet')],
        ondelete={'fleet': 'set default'},
    )

    @api.model
    def _infer_category(self, model_name):
        if model_name and model_name.startswith('fleet.'):
            return 'fleet'
        return super()._infer_category(model_name)


class FleetBellMixin(models.AbstractModel):
    """Send bell notifications (Generic Bell Notification) about the current record to its responsible users"""
    _name = 'fleet.bell.mixin'
    _description = 'Fleet Bell Notification Helper'

    @api.model
    def _bell_group_users(self, xmlid):
        group = self.env.ref(xmlid, raise_if_not_found=False)
        return group.sudo().users if group else self.env['res.users']

    def _bell_notify(self, users, title, message, notif_type='info', icon='fa-car'):
        """Notify each user once about this record.

        Skips the user who triggered the event (they already know), OdooBot,
        archived and portal users. A failing bell never blocks the fleet workflow.
        """
        self.ensure_one()
        users = users.sudo().filtered(
            lambda u: u.active and not u.share and u.id not in (SUPERUSER_ID, self.env.uid)
        )
        Notification = self.env['generic.notification'].sudo()
        for user in users:
            try:
                Notification.send_notification(
                    user.id, title, message,
                    res_model=self._name, res_id=self.id,
                    notif_type=notif_type, icon_class=icon,
                )
            except Exception:  # never break the business flow because of a notification
                _logger.exception('Fleet bell notification failed for %s,%s', self._name, self.id)
