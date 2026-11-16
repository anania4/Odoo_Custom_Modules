import json
import logging
from collections import defaultdict

from requests import Session

from odoo import models, fields, api, _
from odoo.addons.mail.tools.web_push import push_to_end_point, DeviceUnreachableError

_logger = logging.getLogger(__name__)


class GenericNotification(models.Model):
    _name = 'generic.notification'
    _description = 'Generic Notification'
    _order = 'create_date desc'

    name = fields.Char(string="Title", required=True, readonly=True)
    body = fields.Text(string="Message", readonly=True)
    user_id = fields.Many2one('res.users', string="Recipient", required=True, ondelete='cascade')
    is_read = fields.Boolean(string="Read", default=False)
    res_model = fields.Char(string="Related Model")
    res_id = fields.Integer(string="Related Record ID", index=True)
    # Somebody has to act on the record. Such a notification cannot be read or
    # cleared by hand: it stays until the workflow removes it for everyone
    # (see clear_action_required).
    action_required = fields.Boolean(string="Action Required", default=False)
    
    module_category = fields.Selection([
        ('hr', 'HR'),
        ('sales', 'Sales'),
        ('tender', 'Tender'),
        ('other', 'Other')
    ], string='Category', default='other')
    
    notif_type = fields.Selection([
        ('info', 'Info'),
        ('success', 'Success'),
        ('warning', 'Warning'),
        ('danger', 'Danger')
    ], string="Notification Type", default='info')

    icon_class = fields.Char(string="Icon Class", default='fa-bell')

    # Whether the corner popup for this notification was already shown to the
    # recipient. Default True only so notifications that already existed when
    # this field was added are not replayed; create() sets False for new ones.
    is_popped = fields.Boolean(string="Popup Shown", default=True)

    @api.model
    def _infer_category(self, model_name):
        try:
            model = self.env.get(model_name)
            if not model:
                return 'other'
            module = getattr(model, '_module', '')
            if module.startswith('hr_') or model_name.startswith('hr.'):
                return 'hr'
            elif module.startswith('sale_') or model_name.startswith('sale.'):
                return 'sales'
            elif module.startswith('tender_') or model_name.startswith('tender.'):
                return 'tender'
            else:
                return 'other'
        except Exception:
            return 'other'

    @api.model
    def create(self, vals):
        if not vals.get('module_category') and vals.get('res_model'):
            vals['module_category'] = self._infer_category(vals['res_model'])
        vals.setdefault('is_popped', False)
        return super().create(vals)

    @api.model
    def send_notification(self, user_id, title, message, res_model=None, res_id=None,
                          notif_type='info', icon_class='fa-bell', action_required=False):
        notif = self.sudo().create({
            'user_id': user_id,
            'name': title,
            'body': message,
            'res_model': res_model,
            'res_id': res_id,
            'notif_type': notif_type,
            'icon_class': icon_class,
            'action_required': bool(action_required and res_model and res_id),
        })
        recipient = self.env['res.users'].sudo().browse(user_id)
        if recipient.partner_id:
            self.env['bus.bus']._sendone(
                recipient.partner_id,
                "generic_notification_update",
                {
                    "action": "add",
                    "notification": {
                        "id": notif.id,
                        "name": notif.name,
                        "body": notif.body,
                        "create_date": str(notif.create_date),
                        "res_model": notif.res_model,
                        "res_id": notif.res_id,
                        "is_read": notif.is_read,
                        "module_category": notif.module_category,
                        "notif_type": notif.notif_type,
                        "icon_class": notif.icon_class,
                        "action_required": notif.action_required,
                    }
                }
            )
        notif._send_web_push()
        return notif

    # ------------------------------------------------------------------
    # Web Push: phone / desktop notification even when Odoo is closed
    # ------------------------------------------------------------------

    def _web_push_payload(self):
        self.ensure_one()
        icon = '/web/static/img/odoo-icon-192x192.png'
        has_record = bool(self.res_model and self.res_id)
        return {
            'title': self.name,
            'options': {
                'body': (self.body or '')[:300],
                'icon': icon,
                'badge': icon,
                'tag': 'gbn-%s' % self.id,
                'requireInteraction': True,
                'data': {
                    'gbn': True,  # handled by bell_push_sw.js, not by Odoo's own push code
                    'id': self.id,
                    'url': '/odoo/%s/%s' % (self.res_model, self.res_id) if has_record else '/odoo',
                },
            },
        }

    def _send_web_push(self):
        """Send the notification to the recipient's registered browsers / phones
        through Odoo's built-in Web Push (devices and VAPID keys of the mail module).
        Sent after commit, and a failure never blocks the business action."""
        self.ensure_one()
        try:
            devices = self.env['mail.push.device'].sudo().search([
                ('partner_id', '=', self.user_id.partner_id.id)])
            if not devices:
                return
            params = self.env['ir.config_parameter'].sudo()
            private_key = params.get_param('mail.web_push_vapid_private_key')
            public_key = params.get_param('mail.web_push_vapid_public_key')
            if not private_key or not public_key:
                return
            payload = json.dumps(self._web_push_payload())
            base_url = self.get_base_url()
            device_list = [{'id': d.id, 'endpoint': d.endpoint, 'keys': d.keys} for d in devices]
            registry, dbname = self.pool, self.env.cr.dbname
        except Exception:
            _logger.exception("Bell web push: could not prepare notification %s", self.id)
            return

        def push():
            session = Session()
            unreachable = []
            for device in device_list:
                try:
                    push_to_end_point(
                        base_url=base_url, device=device, payload=payload,
                        vapid_private_key=private_key, vapid_public_key=public_key,
                        session=session)
                except DeviceUnreachableError:
                    unreachable.append(device['id'])
                except Exception as e:  # never block on a notification
                    _logger.warning("Bell web push failed for device %s: %s", device['id'], e)
            if unreachable:
                try:
                    with registry.cursor() as cr:
                        cr.execute("DELETE FROM mail_push_device WHERE id IN %s", (tuple(unreachable),))
                except Exception:
                    _logger.exception("Bell web push: could not remove dead devices in %s", dbname)

        self.env.cr.postcommit.add(push)

    @api.model
    def clear_action_required(self, records):
        """The record was dealt with: remove its action-required notifications
        for every recipient, live for those who are online. Other notifications
        about the record stay. A failure here never blocks the business action."""
        if not records:
            return
        try:
            with self.env.cr.savepoint():
                notifications = self.sudo().search([
                    ('action_required', '=', True),
                    ('res_model', '=', records._name),
                    ('res_id', 'in', records.ids),
                ])
                ids_by_user = defaultdict(list)
                for notification in notifications:
                    ids_by_user[notification.user_id].append(notification.id)
                for user, ids in ids_by_user.items():
                    if user.partner_id:
                        self.env['bus.bus']._sendone(
                            user.partner_id,
                            "generic_notification_update",
                            {"action": "remove", "notification_ids": ids},
                        )
                notifications.unlink()
        except Exception:
            _logger.exception("Could not clear the notifications of %s %s", records._name, records.ids)

    @api.model
    def pop_pending(self, limit=20):
        """Unread notifications whose corner popup was never shown to the
        current user (e.g. they arrived while the user was offline).
        Returned once, then flagged so they are not popped again."""
        pending = self.search([
            ('user_id', '=', self.env.uid),
            ('is_read', '=', False),
            ('is_popped', '=', False),
        ], order='create_date desc, id desc', limit=limit)
        result = [{
            'id': n.id,
            'name': n.name,
            'body': n.body or '',
            'notif_type': n.notif_type or 'info',
        } for n in pending]
        pending.write({'is_popped': True})
        return result

    @api.model
    def action_mark_popped(self, notif_id):
        """A notification that arrived live (user online) already got its popup."""
        notification = self.search([('id', '=', notif_id), ('user_id', '=', self.env.uid)])
        if notification:
            notification.write({'is_popped': True})
        return True

    @api.model
    def action_mark_as_read(self, notif_id):
        notification = self.search([
            ('id', '=', notif_id),
            ('user_id', '=', self.env.uid),
            ('action_required', '=', False),
        ])
        if notification:
            notification.write({'is_read': True})
        return True

    @api.model
    def action_mark_all_as_read(self):
        return self.search([
            ('user_id', '=', self.env.uid),
            ('is_read', '=', False),
            ('action_required', '=', False),
        ]).write({'is_read': True})

    @api.model
    def action_clear_all(self):
        return self.search([('user_id', '=', self.env.uid), ('action_required', '=', False)]).unlink()

    @api.model
    def action_open_record(self, notif_id):
        notification = self.search([('id', '=', notif_id), ('user_id', '=', self.env.uid)])
        if not notification:
            return {'type': 'ir.actions.act_window_close'}
        # Opening is not dealing with it: an action-required notification stays unread.
        if not notification.action_required:
            notification.write({'is_read': True})
        if not notification.res_model or not notification.res_id:
            return {'type': 'ir.actions.act_window_close'}

        record = self.env[notification.res_model].sudo().browse(notification.res_id)
        if not record.exists():
            if notification.action_required:
                notification.unlink()
            return {'type': 'ir.actions.act_window_close'}

        return {
            'type': 'ir.actions.act_window',
            'res_model': notification.res_model,
            'res_id': notification.res_id,
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'current',
        }
