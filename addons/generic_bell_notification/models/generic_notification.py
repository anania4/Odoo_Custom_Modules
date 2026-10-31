from odoo import models, fields, api, _

class GenericNotification(models.Model):
    _name = 'generic.notification'
    _description = 'Generic Notification'
    _order = 'create_date desc'

    name = fields.Char(string="Title", required=True, readonly=True)
    body = fields.Text(string="Message", readonly=True)
    user_id = fields.Many2one('res.users', string="Recipient", required=True, ondelete='cascade')
    is_read = fields.Boolean(string="Read", default=False)
    res_model = fields.Char(string="Related Model")
    res_id = fields.Integer(string="Related Record ID")
    
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
                          notif_type='info', icon_class='fa-bell'):
        notif = self.sudo().create({
            'user_id': user_id,
            'name': title,
            'body': message,
            'res_model': res_model,
            'res_id': res_id,
            'notif_type': notif_type,
            'icon_class': icon_class,
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
                    }
                }
            )
        return notif

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
        notification = self.browse(notif_id)
        if notification.exists() and notification.user_id.id == self.env.uid:
            notification.write({'is_popped': True})
        return True

    @api.model
    def action_mark_as_read(self, notif_id):
        notification = self.browse(notif_id)
        if notification.exists():
            notification.write({'is_read': True})
        return True

    @api.model
    def action_mark_all_as_read(self):
        return self.search([('user_id', '=', self.env.uid), ('is_read', '=', False)]).write({'is_read': True})

    @api.model
    def action_clear_all(self):
        return self.search([('user_id', '=', self.env.uid)]).unlink()

    @api.model
    def action_open_record(self, notif_id):
        notification = self.browse(notif_id)
        if not notification.exists():
            return {'type': 'ir.actions.act_window_close'}
        notification.write({'is_read': True})
        if not notification.res_model or not notification.res_id:
            return {'type': 'ir.actions.act_window_close'}

        record = self.env[notification.res_model].sudo().browse(notification.res_id)
        if not record.exists():
            return {'type': 'ir.actions.act_window_close'}

        return {
            'type': 'ir.actions.act_window',
            'res_model': notification.res_model,
            'res_id': notification.res_id,
            'views': [[False, 'form']],
            'view_mode': 'form',
            'target': 'current',
        }
