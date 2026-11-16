import logging

from odoo import _, api, fields, models

_logger = logging.getLogger(__name__)

# Models of this module; notifications about them are filed under "Purchase".
PURCHASE_PROCESS_MODELS = (
    'material.request',
    'purchase.request',
    'purchase.quotation',
    'supplier.analysis',
    'quality.inspection',
    'product.siv',
)


class GenericNotification(models.Model):
    _inherit = 'generic.notification'

    module_category = fields.Selection(selection_add=[('purchase', 'Purchase')])

    @api.model
    def _infer_category(self, model_name):
        if model_name in PURCHASE_PROCESS_MODELS:
            return 'purchase'
        return super()._infer_category(model_name)


class PurchaseNotifyMixin(models.AbstractModel):
    """Helpers that connect the purchase workflow to the generic bell.

    Each workflow step produces:

    * forward  - action-required bell message for the people who are next in line
                 ("... awaits your approval"). The message stays until the step is done.
    * backward - bell message for the people who started or handled the record earlier
                 ("... has been approved by the Finance Manager")

    Only the generic bell is used: no Odoo activities, inbox, email or push
    (inbox/email/push are blocked by ``_bell_only_notifications``).
    The action-required messages of the previous step are cleared.
    Failures never block the business action.
    """
    _name = 'custom.purchase.notify.mixin'
    _description = 'Purchase Process Notification Helpers'

    # ------------------------------------------------------------------
    # Status changes
    # ------------------------------------------------------------------
    def write(self, vals):
        """As soon as one person acts on a record (approve, reject, next step...),
        its status changes and the action-required bell messages of that step
        disappear for everybody who received them, live for those online.

        The workflow methods change the status first and send the messages for
        the next step afterwards, so the new messages are not affected."""
        changed = self.browse()
        if 'state' in vals and 'state' in self._fields:
            changed = self.filtered(lambda record: record.state != vals['state'])
        res = super().write(vals)
        if changed and 'generic.notification' in self.env:
            self.env['generic.notification'].sudo().clear_action_required(changed)
        return res

    # ------------------------------------------------------------------
    # Recipients
    # ------------------------------------------------------------------
    def _get_group_users(self, group_xmlid, exclude_group_xmlids=()):
        """Active users of a group, minus the users of the given higher groups.

        The purchase groups imply each other (CEO > Finance Manager > Procurement
        Manager ...), so the plain user list of a group also contains everybody
        above it. Excluding the higher groups leaves the people whose turn it
        really is. Users are limited to the record's company when it has one.
        """
        self.ensure_one()
        group = self.env.ref(group_xmlid, raise_if_not_found=False)
        if not group:
            return self.env['res.users']
        users = group.sudo().users.filtered('active')
        for xmlid in exclude_group_xmlids:
            higher = self.env.ref(xmlid, raise_if_not_found=False)
            if higher:
                users -= higher.sudo().users
        company = self.company_id if 'company_id' in self._fields else False
        if company:
            users = users.filtered(lambda user: company in user.company_ids)
        return users

    # ------------------------------------------------------------------
    # Senders
    # ------------------------------------------------------------------
    def _bell_notify(self, users, title, message, notif_type='info', icon='fa-bell',
                     action_required=False, include_self=False):
        """Send one bell notification per user, not to the person acting unless include_self."""
        self.ensure_one()
        if 'generic.notification' not in self.env:
            return
        users = (users or self.env['res.users']).sudo().filtered('active')
        if not include_self:
            users -= self.env.user
        notification = self.env['generic.notification'].sudo()
        for user in users:
            try:
                with self.env.cr.savepoint():
                    notification.send_notification(
                        user_id=user.id,
                        title=title,
                        message=message,
                        res_model=self._name,
                        res_id=self.id,
                        notif_type=notif_type,
                        icon_class=icon,
                        action_required=action_required,
                    )
            except Exception:
                _logger.exception("Could not send bell notification to user %s", user.id)

    def _close_flow_activities(self):
        """Clear the action-required bell notifications of this record, for everyone.

        Workflow activities left over from older versions are removed too;
        To-Dos people scheduled by hand stay."""
        try:
            with self.env.cr.savepoint():
                self.sudo().activity_ids.filtered('automated').unlink()
        except Exception:
            _logger.exception("Could not remove the old activities of %s", self.display_name)
        if 'generic.notification' in self.env:
            self.env['generic.notification'].sudo().clear_action_required(self)

    def _notify_flow(self, forward=None, forward_title=None, forward_message=None,
                     backward=None, backward_title=None, backward_message=None,
                     notif_type='info', icon='fa-bell'):
        """One workflow step: the previous action-required messages are cleared, the next
        in line get an action-required bell message, and earlier handlers are informed."""
        self.ensure_one()
        self._close_flow_activities()
        if forward:
            self._bell_notify(forward, forward_title, forward_message or '', notif_type, icon,
                              action_required=True)
        if backward:
            # A person who is both next in line and an earlier handler gets the
            # forward message only.
            backward = backward - (forward or self.env['res.users'])
            self._bell_notify(backward, backward_title, backward_message or '', 'success', icon)

    def _notify_label(self):
        """Short text naming the record, e.g. "SR/00012"."""
        self.ensure_one()
        return self.display_name or self.name or ''
