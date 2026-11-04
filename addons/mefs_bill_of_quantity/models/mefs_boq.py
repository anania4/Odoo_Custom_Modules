
import logging

from odoo import models, fields, api, _
from odoo.exceptions import UserError, ValidationError


_logger = logging.getLogger(__name__)


class MefsBoq(models.Model):
    _name = 'mefs.boq'
    _description = 'Bill of Quantity'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'id desc'

    name = fields.Char(string='Reference', required=True, copy=False, readonly=True, default=lambda self: _('New'))
    project_id = fields.Many2one('project.project', string='Project', required=True, tracking=True)
    analytic_account_id = fields.Many2one('account.analytic.account', string='Analytic Account', related='project_id.account_id', store=True, readonly=True)
    partner_id = fields.Many2one('res.partner', string='Customer', related='project_id.partner_id', store=True, readonly=True)
    date = fields.Date(string='Date', default=fields.Date.context_today, required=True)
    currency_id = fields.Many2one('res.currency', string='Currency', default=lambda self: self.env.company.currency_id)

    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting_approval', 'Waiting Approval'),
        ('locked', 'Approved'),
        ('revised', 'Revised'),
    ], string='Status', default='draft', tracking=True, copy=False)

    revision_number = fields.Integer(string='Revision Number', default=0, readonly=True)
    revision_name = fields.Char(string='Revision', compute='_compute_revision_name', store=True)

    submitted_by = fields.Many2one('res.users', string='Submitted By', readonly=True, copy=False, tracking=True)
    submitted_on = fields.Datetime(string='Submitted On', readonly=True, copy=False)
    approved_by = fields.Many2one('res.users', string='Approved By', readonly=True, copy=False, tracking=True)
    is_project_manager = fields.Boolean(
        string='Is Project Manager of this BOQ', compute='_compute_is_project_manager',
        help="True when the current user is the Project Manager of the BOQ's project.")
    approved_on = fields.Datetime(string='Approved On', readonly=True, copy=False)

    parent_boq_id = fields.Many2one('mefs.boq', string='Parent BOQ', copy=False, readonly=True)
    child_boq_ids = fields.One2many('mefs.boq', 'parent_boq_id', string='Revisions')
    revision_count = fields.Integer(string='Revision Count', compute='_compute_revision_count')

    payment_ids = fields.One2many('mefs.boq.payment', 'boq_id', string='Payments')
    payment_count = fields.Integer(string='Payment Count', compute='_compute_payment_count')

    note = fields.Text(
        string='Terms & Payment Notes',
        default="Note: Fuel base price: 180.46 ETB/L. Prices shall be adjusted if the fuel price increases using the Sub Contractor cost breakdown."
    )

    boq_line_ids = fields.One2many('mefs.boq.line', 'boq_id', string='BOQ Lines', copy=True)

    total_amount = fields.Float(string='Total Before VAT', compute='_compute_totals')
    vat_amount = fields.Float(string='VAT 15%', compute='_compute_totals')
    grand_total = fields.Float(string='Grand Total', compute='_compute_totals')

    @api.depends('name', 'revision_number')
    def _compute_revision_name(self):
        for boq in self:
            boq.revision_name = f"{boq.name} REV{boq.revision_number}"

    def _compute_revision_count(self):
        for boq in self:
            if boq.name:
                boq.revision_count = self.search_count([('name', '=', boq.name)]) - 1
            else:
                boq.revision_count = 0

    @api.depends('payment_ids')
    def _compute_payment_count(self):
        for boq in self:
            boq.payment_count = len(boq.payment_ids)

    @api.depends(
        'boq_line_ids.subtotal',
        'boq_line_ids.taxes_id',
        'boq_line_ids.unit_price',
        'boq_line_ids.revised_contract_qty',
        'boq_line_ids.display_type',
        'boq_line_ids.is_subtotal',
    )
    def _compute_totals(self):
        for boq in self:
            total = 0.0
            vat_amount = 0.0
            for line in boq.boq_line_ids:
                if line.display_type == 'line_note' or line.is_subtotal:
                    continue
                total += line.subtotal

                if line.taxes_id:
                    taxes_res = line.taxes_id.compute_all(
                        line.unit_price or 0.0,
                        quantity=line.revised_contract_qty or 0.0,
                        currency=boq.currency_id,
                        product=line.product_id,
                    )
                    for tax in taxes_res.get('taxes', []):
                        vat_amount += tax['amount']

            boq.total_amount = total
            boq.vat_amount = round(vat_amount, 2)
            boq.grand_total = round(total + vat_amount, 2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('mefs.boq') or _('New')
        records = super().create(vals_list)
        records._recompute_bill_numbers()
        return records

    def write(self, vals):
        res = super().write(vals)
        if 'boq_line_ids' in vals or 'state' in vals:
            self._recompute_bill_numbers()
        return res

    def unlink(self):
        for boq in self:
            if boq.state != 'draft':
                raise UserError(_("You can only delete draft Bills of Quantity. '%s' is in '%s' status.") % (
                    boq.name, dict(self._fields['state'].selection).get(boq.state, boq.state)
                ))
            if boq.child_boq_ids:
                raise UserError(_("Cannot delete BOQ '%s' because it has revisions.") % boq.name)
            if boq.payment_ids:
                raise UserError(_("Cannot delete BOQ '%s' because it has payment certificates.") % boq.name)
        return super().unlink()

    @api.onchange('boq_line_ids')
    def _onchange_boq_line_ids(self):
        """Live numbering in the form view as the user adds lines."""
        l1 = 0
        l2 = 0
        l3 = 0
        l4 = 0
        for line in self.boq_line_ids:
            if line.is_subtotal or line.display_type == 'line_note':
                line.bill_no = False
                continue
            dt = line.display_type
            if dt == 'line_section':
                l1 += 1
                l2 = l3 = l4 = 0
                line.bill_no = str(l1)
            elif dt == 'line_sub_section':
                if l1 == 0:
                    l1 = 1
                l2 += 1
                l3 = l4 = 0
                line.bill_no = f"{l1}.{l2}"
            elif dt == 'line_sub':
                if l1 == 0:
                    l1 = 1
                if l2 == 0:
                    l2 = 1
                l3 += 1
                l4 = 0
                line.bill_no = f"{l1}.{l2}.{l3}"
            elif dt == 'line_sub2':
                if l1 == 0:
                    l1 = 1
                if l2 == 0:
                    l2 = 1
                if l3 == 0:
                    l3 = 1
                l4 += 1
                line.bill_no = f"{l1}.{l2}.{l3}.{l4}"
            else:
                if l1 == 0:
                    l1 = 1
                if l2 > 0 and l3 > 0:
                    l4 += 1
                    line.bill_no = f"{l1}.{l2}.{l3}.{l4}"
                elif l2 > 0:
                    l3 += 1
                    line.bill_no = f"{l1}.{l2}.{l3}"
                else:
                    l2 += 1
                    line.bill_no = f"{l1}.{l2}"

    def _recompute_bill_numbers(self):
        """
        Assigns hierarchical bill numbers:
          Level 1  line_section      → 1, 2, 3 …
          Level 2  line_sub_section  → 1.1, 1.2 …
          Level 3  line_sub          → 1.1.1, 1.1.2 …
          Level 4  line_sub2         → 1.1.1.1, 1.1.1.2 …
          Normal   (no display_type) → inherits current hierarchy prefix
          Subtotal auto-row          → inserted after every completed Level-1 group
        """
        BoqLine = self.env['mefs.boq.line']
        for boq in self:
            # 1. Remove all previously auto-generated subtotal rows
            BoqLine.search([
                ('boq_id', '=', boq.id),
                ('is_subtotal', '=', True),
            ]).with_context(force_unlink=True).unlink()

            lines = BoqLine.search([
                ('boq_id', '=', boq.id),
                ('display_type', 'in', [False, 'line_section', 'line_sub_section',
                                        'line_sub', 'line_sub2', 'line_note']),
            ], order='sequence, id')

            # Counters for each level
            l1 = 0          # line_section counter
            l2 = 0          # line_sub_section / item counter
            l3 = 0          # line_sub counter
            l4 = 0          # line_sub2 counter

            current_section_total = 0.0   # running total for current L1 group
            ordered_rows = []

            def add_subtotal(section_num, total):
                ordered_rows.append(BoqLine.create({
                    'boq_id': boq.id,
                    'name': f"Sub-Total Bill No. {section_num}",
                    'is_subtotal': True,
                    'unit_price': total,
                    'quantity': 1.0,
                }))

            for line in lines:
                dt = line.display_type

                if dt == 'line_section':
                    # Close previous L1 group with a subtotal when transitioning 1 to 2, 2 to 3, etc.
                    if l1 > 0:
                        add_subtotal(l1, current_section_total)
                    l1 += 1
                    l2 = l3 = l4 = 0
                    current_section_total = line.subtotal or 0.0
                    line.bill_no = str(l1)

                elif dt == 'line_sub_section':
                    # Level 2: 1.1, 1.2 …
                    if l1 == 0:
                        l1 = 1
                    l2 += 1
                    l3 = l4 = 0
                    line.bill_no = f"{l1}.{l2}"
                    current_section_total += line.subtotal

                elif dt == 'line_sub':
                    # Level 3: 1.1.1, 1.1.2 …
                    if l1 == 0:
                        l1 = 1
                    if l2 == 0:
                        l2 = 1
                    l3 += 1
                    l4 = 0
                    line.bill_no = f"{l1}.{l2}.{l3}"
                    current_section_total += line.subtotal

                elif dt == 'line_sub2':
                    # Level 4: 1.1.1.1, 1.1.1.2 …
                    if l1 == 0:
                        l1 = 1
                    if l2 == 0:
                        l2 = 1
                    if l3 == 0:
                        l3 = 1
                    l4 += 1
                    line.bill_no = f"{l1}.{l2}.{l3}.{l4}"
                    current_section_total += line.subtotal

                elif dt == 'line_note':
                    line.bill_no = False

                else:
                    # Normal data line (no display_type)
                    if l1 == 0:
                        l1 = 1
                    if l2 > 0 and l3 > 0:
                        l4 += 1
                        line.bill_no = f"{l1}.{l2}.{l3}.{l4}"
                    elif l2 > 0:
                        l3 += 1
                        line.bill_no = f"{l1}.{l2}.{l3}"
                    else:
                        l2 += 1
                        line.bill_no = f"{l1}.{l2}"
                    current_section_total += line.subtotal

                ordered_rows.append(line)

            # Close the last L1 group only when state is not draft (e.g. waiting_approval, locked, revised)
            if boq.state != 'draft' and l1 > 0:
                add_subtotal(l1, current_section_total)

            # Re-sequence everything
            for index, row in enumerate(ordered_rows):
                row.sequence = (index + 1) * 10

    @api.depends('project_id.user_id')
    @api.depends_context('uid')
    def _compute_is_project_manager(self):
        for boq in self:
            boq.is_project_manager = bool(boq.project_id.user_id) and boq.project_id.user_id == self.env.user

    def _check_is_project_manager(self, action_label):
        """Only the Project Manager of the BOQ's project may do this (superuser excepted)."""
        if self.env.su:
            return
        for boq in self:
            if not boq.is_project_manager:
                raise UserError(_(
                    "Only the Project Manager of project '%s' can %s Bill of Quantity %s."
                ) % (boq.project_id.name or '', action_label, boq.name))

    # --- Notification Helpers (bell only) ---
    def _get_project_manager(self):
        """The Project Manager of the BOQ's project: the only approver who is notified."""
        self.ensure_one()
        return self.project_id.user_id

    def _get_submitter_or_actor(self):
        """Used right after submit: the person who just clicked Submit."""
        self.ensure_one()
        return self.submitted_by or self.env.user

    def _get_submitter(self):
        """The person who submitted the BOQ (creator as fallback for old records)."""
        self.ensure_one()
        return self.submitted_by or self.create_uid

    def _send_generic_bell_notification(self, users, title, message, notif_type='info', icon='fa-list-alt'):
        """Send notification to the Generic Bell Systray (generic_bell_notification).
        This is the ONLY notification channel used by the BOQ (no chatter inbox,
        no activities, no native Odoo bus toasts)."""
        users = users.filtered(lambda u: u.active)
        if not users:
            return
        if 'generic.notification' not in self.env:
            _logger.warning("generic_bell_notification is not installed: BOQ %s notification not sent", self.name)
            return
        notif_model = self.env['generic.notification'].sudo()
        for user in users:
            try:
                # Savepoint: a DB error inside the notification must not abort
                # the whole transaction (Confirm / Approve / Reset to Draft).
                with self.env.cr.savepoint():
                    notif_model.send_notification(
                        user_id=user.id,
                        title=title,
                        message=message,
                        res_model=self._name,
                        res_id=self.id,
                        notif_type=notif_type,
                        icon_class=icon,
                    )
            except Exception:
                _logger.exception("Could not send bell notification to %s for BOQ %s", user.name, self.name)

    def action_confirm(self):
        for boq in self:
            if not boq._get_project_manager():
                raise UserError(_(
                    "Project '%s' has no Project Manager. Set one on the project before submitting "
                    "this BOQ for approval, so the approver can be notified."
                ) % (boq.project_id.name or ''))
        self.write({
            'state': 'waiting_approval',
            'submitted_by': self.env.user.id,
            'submitted_on': fields.Datetime.now(),
        })
        for boq in self:
            submitter = boq._get_submitter_or_actor()
            project_manager = boq._get_project_manager()
            # Bell notification for the Project Manager who must approve it
            if project_manager != submitter:
                boq._send_generic_bell_notification(
                    users=project_manager,
                    title=_("BOQ awaits your approval: %s") % boq.name,
                    message=_("Bill of Quantity %s for project '%s', submitted by %s, awaits your approval.") % (
                        boq.name, boq.project_id.name or '', submitter.name
                    ),
                    notif_type='info',
                    icon='fa-list-alt',
                )

        if len(self) == 1:
            # Instant pop-up for the person who submitted
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Bill of Quantity Submitted"),
                    "message": _("You have submitted Bill of Quantity %s for project '%s' for approval.") % (
                        self.name, self.project_id.name or ''
                    ),
                    "type": "success",
                    "sticky": False,
                    "next": {
                        "type": "ir.actions.act_window",
                        "res_model": "mefs.boq",
                        "res_id": self.id,
                        "views": [(False, "form")],
                        "view_mode": "form",
                        "target": "current",
                    },
                },
            }
        return True

    def action_approve(self):
        self._check_is_project_manager(_("approve"))
        if not self.env.su:
            for boq in self:
                if boq.submitted_by and boq.submitted_by == self.env.user:
                    raise UserError(_(
                        "You submitted Bill of Quantity %s, so you cannot approve it. "
                        "It must be approved by another Project Manager."
                    ) % boq.name)
        self.write({
            'state': 'locked',
            'approved_by': self.env.user.id,
            'approved_on': fields.Datetime.now(),
        })
        for boq in self:
            for line in boq.boq_line_ids:
                if not line.original_contract_qty and line.revised_contract_qty:
                    line.original_contract_qty = line.revised_contract_qty

            # Only the two people involved: the submitter and the Project Manager
            boq._send_generic_bell_notification(
                users=(boq._get_submitter() | boq._get_project_manager()) - self.env.user,
                title=_("BOQ Approved: %s") % boq.name,
                message=_("Bill of Quantity %s for project '%s' has been approved by %s.") % (
                    boq.name, boq.project_id.name or '', self.env.user.name
                ),
                notif_type='success',
                icon='fa-check-circle',
            )

        if len(self) == 1:
            # Instant pop-up for the person who approved
            return {
                "type": "ir.actions.client",
                "tag": "display_notification",
                "params": {
                    "title": _("Bill of Quantity Approved"),
                    "message": _("You have approved Bill of Quantity %s for project '%s'.") % (
                        self.name, self.project_id.name or ''
                    ),
                    "type": "success",
                    "sticky": False,
                    "next": {
                        "type": "ir.actions.act_window",
                        "res_model": "mefs.boq",
                        "res_id": self.id,
                        "views": [(False, "form")],
                        "view_mode": "form",
                        "target": "current",
                    },
                },
            }
        return True

    def action_reset_draft(self):
        for boq in self:
            if boq.state not in ('waiting_approval', 'locked'):
                raise UserError(_("Only BOQs waiting for approval or approved can be reset to draft."))
            if boq.state == 'locked':
                boq._check_is_project_manager(_("reset to draft the approved"))
                if boq.child_boq_ids:
                    raise UserError(_("Cannot reset a BOQ that has revisions. Delete revisions first."))
            submitter = boq._get_submitter()
            boq.write({
                'state': 'draft',
                'approved_by': False,
                'approved_on': False,
            })

            # Only the two people involved: the submitter and the Project Manager
            # (whoever did NOT click the button gets notified).
            boq._send_generic_bell_notification(
                users=submitter | boq._get_project_manager(),
                title=_("BOQ Reset to Draft: %s") % boq.name,
                message=_("Bill of Quantity %s for project '%s' has been reset to draft by %s.") % (
                    boq.name, boq.project_id.name or '', self.env.user.name
                ),
                notif_type='warning',
                icon='fa-undo',
            )

        return True

    @api.constrains('project_id', 'state')
    def _check_single_locked_boq(self):
        for boq in self:
            if boq.state != 'locked':
                continue
            conflicting = self.search([
                ('project_id', '=', boq.project_id.id),
                ('state', '=', 'locked'),
                ('id', '!=', boq.id),
            ], limit=1)
            if conflicting:
                raise ValidationError(_(
                    "Project %s already has an approved (locked) BOQ: %s. "
                    "Unlock or revise it before approving a new one."
                ) % (boq.project_id.name, conflicting.name))

    def action_unlock(self):
        if self.state != 'locked':
            raise UserError(_("Only locked BOQs can be unlocked."))
        if self.child_boq_ids:
            raise UserError(_("Cannot unlock a BOQ that has revisions. Unlock or delete revisions first."))
        self.write({'state': 'draft'})

    def action_create_revision(self):
        self.ensure_one()
        if self.state != 'locked':
            raise UserError(_("Only locked BOQs can be revised."))
        if not self.project_id.stage_id.allow_boq_revision:
            raise UserError(_(
                "BOQ revisions can only be created when the project is in the Construction stage. "
                "Current stage: %s" % self.project_id.stage_id.name
            ))

        new_boq = self.with_context(boq_revision_copy=True).copy({
            'name': self.name,
            'parent_boq_id': self.id,
            'revision_number': self.revision_number + 1,
            'state': 'draft',
        })
        self.write({'state': 'revised'})

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'mefs.boq',
            'view_mode': 'form',
            'res_id': new_boq.id,
            'target': 'current',
        }

    def action_view_revisions(self):
        self.ensure_one()
        return {
            'name': _('Revision History'),
            'type': 'ir.actions.act_window',
            'res_model': 'mefs.boq',
            'view_mode': 'list,form',
            'domain': [('name', '=', self.name)],
            'context': {'default_project_id': self.project_id.id},
            'target': 'current',
        }

    def action_view_payments(self):
        self.ensure_one()
        action = self.env['ir.actions.act_window']._for_xml_id('mefs_bill_of_quantity.action_mefs_boq_payment')
        action['domain'] = [('boq_id', '=', self.id)]
        action['context'] = {
            'default_boq_id': self.id,
            'default_project_id': self.project_id.id,
        }
        if self.payment_count == 1:
            action['views'] = [(self.env.ref('mefs_bill_of_quantity.view_mefs_boq_payment_form').id, 'form')]
            action['res_id'] = self.payment_ids[0].id
        return action

    def action_create_payment(self):
        self.ensure_one()
        self._check_is_project_manager(_("create a payment for"))
        payment_name = f"IPC-{len(self.payment_ids) + 1:02d}"
        payment = self.env['mefs.boq.payment'].create({
            'name': payment_name,
            'boq_id': self.id,
            'date': fields.Date.context_today(self),
        })
        payment.action_load_boq_lines()
        return {
            'name': _('Payment Certificate'),
            'type': 'ir.actions.act_window',
            'res_model': 'mefs.boq.payment',
            'view_mode': 'form',
            'res_id': payment.id,
            'target': 'current',
        }


    def action_print_boq(self):
        self.ensure_one()
        return self.env.ref('mefs_bill_of_quantity.action_report_mefs_boq_original').report_action(self)

    def action_print_original_boq(self):
        return self.action_print_boq()

    def action_print_current_boq(self):
        self.ensure_one()
        return self.env.ref('mefs_bill_of_quantity.action_report_mefs_boq_current').report_action(self)

    def _get_boq_report_data(self, mode='original'):
        """
        Precomputes clean, formatted data structures for Original and Current BOQ PDF prints.
        Matches the layout from the reference document:
          - mode='original': baseline contract quantities and original subtotals.
          - mode='current': remaining quantities and remaining subtotals.
        """
        self.ensure_one()
        is_original = (mode == 'original')
        title = "3. PRICED BILL OF QUANTITY AND TERMS OF PAYMENT"
        subtitle = "ORIGINAL CONTRACT" if is_original else "CURRENT REMAINING WORK"

        rows = []
        section_summaries = []
        current_sec_num = 0
        current_sec_title = ''
        current_sec_total = 0.0
        total_before_vat = 0.0

        lines = self.boq_line_ids.filtered(
            lambda l: not l.is_subtotal and l.display_type != 'line_note'
        ).sorted(key=lambda l: (l.sequence, l.id))

        def format_num(val):
            if val is None or val == '':
                return ''
            try:
                return f"{float(val):,.2f}"
            except (ValueError, TypeError):
                return str(val)

        for line in lines:
            dt = line.display_type

            if is_original:
                qty = line.original_contract_qty if line.original_contract_qty else line.revised_contract_qty
            else:
                if hasattr(line, 'remaining_quantity'):
                    qty = line.remaining_quantity
                else:
                    qty = (line.revised_contract_qty or 0.0) - (getattr(line, 'executed_quantity', 0.0) or 0.0)
                if qty < 0.0:
                    qty = 0.0

            price = line.unit_price or 0.0
            has_qty_price = bool(qty and price)
            line_total = qty * price if has_qty_price else 0.0

            if dt == 'line_section':
                # Close previous section if any
                if current_sec_num > 0:
                    rows.append({
                        'is_section': False,
                        'is_subtotal': True,
                        'bill_no': '',
                        'name': f"Sub-Total Bill No. {current_sec_num}",
                        'unit': '',
                        'quantity': '',
                        'unit_price': '',
                        'total_price': format_num(current_sec_total),
                    })
                    section_summaries.append({
                        'num': str(current_sec_num),
                        'title': f"Bill No. {current_sec_num}: {current_sec_title}",
                        'amount': format_num(current_sec_total),
                    })
                    total_before_vat += current_sec_total

                # Start new section
                current_sec_num = int(''.join(c for c in (line.bill_no or '1') if c.isdigit()) or (current_sec_num + 1))
                current_sec_title = line.name or ''
                current_sec_total = line_total

                rows.append({
                    'is_section': True,
                    'is_subtotal': False,
                    'bill_no': line.bill_no or str(current_sec_num),
                    'name': line.name,
                    'unit': line.uom_id.name if has_qty_price else '',
                    'quantity': format_num(qty) if has_qty_price else '',
                    'unit_price': format_num(price) if has_qty_price else '',
                    'total_price': format_num(line_total) if has_qty_price else '',
                })

            else:
                current_sec_total += line_total
                rows.append({
                    'is_section': False,
                    'is_subtotal': False,
                    'bill_no': line.bill_no or '',
                    'name': line.name,
                    'unit': line.uom_id.name or '',
                    'quantity': format_num(qty) if has_qty_price else (format_num(qty) if qty else ''),
                    'unit_price': format_num(price) if has_qty_price else (format_num(price) if price else ''),
                    'total_price': format_num(line_total) if has_qty_price else '',
                })

        # Close final section
        if current_sec_num > 0:
            rows.append({
                'is_section': False,
                'is_subtotal': True,
                'bill_no': '',
                'name': f"Sub-Total Bill No. {current_sec_num}",
                'unit': '',
                'quantity': '',
                'unit_price': '',
                'total_price': format_num(current_sec_total),
            })
            section_summaries.append({
                'num': str(current_sec_num),
                'title': f"Bill No. {current_sec_num}: {current_sec_title}",
                'amount': format_num(current_sec_total),
            })
            total_before_vat += current_sec_total
        elif rows and total_before_vat == 0.0:
            sec_total = sum(
                (l.original_contract_qty or l.revised_contract_qty if is_original else getattr(l, 'remaining_quantity', l.revised_contract_qty)) * (l.unit_price or 0.0)
                for l in lines
            )
            total_before_vat = sec_total
            section_summaries.append({
                'num': '1',
                'title': 'Bill No. 1: Main Works',
                'amount': format_num(sec_total),
            })

        from decimal import Decimal, ROUND_HALF_UP
        vat_dec = (Decimal(str(round(total_before_vat, 2))) * Decimal('0.15')).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        vat_amount = float(vat_dec)
        grand_total = round(total_before_vat + vat_amount, 2)

        note_text = self.note or "Note: Fuel base price: 180.46 ETB/L. Prices shall be adjusted if the fuel price increases using the Sub Contractor cost breakdown."

        return {
            'mode': mode,
            'title': title,
            'subtitle': subtitle,
            'note': note_text,
            'rows': rows,
            'summaries': section_summaries,
            'total_before_vat': format_num(total_before_vat),
            'vat_amount': format_num(vat_amount),
            'grand_total': format_num(grand_total),
            'currency_name': self.currency_id.name or 'ETB',
        }


class ProjectProject(models.Model):
    _inherit = 'project.project'

    boq_count = fields.Integer(string='BOQ Count', compute='_compute_boq_data')
    boq_total = fields.Float(string='BOQ Total', compute='_compute_boq_data')
    payment_count = fields.Integer(string='Payment Count', compute='_compute_boq_data')

    @api.depends()
    def _compute_boq_data(self):
        if not self.env.user.has_group('mefs_bill_of_quantity.group_mefs_boq_user'):
            for project in self:
                project.boq_count = 0
                project.boq_total = 0.0
                project.payment_count = 0
            return
        Boq = self.env['mefs.boq']
        Payment = self.env['mefs.boq.payment']
        for project in self:
            boqs = Boq.search([('project_id', '=', project.id)])
            project.boq_count = len(boqs)
            project.boq_total = sum(boqs.mapped('grand_total'))
            project.payment_count = Payment.search_count([('project_id', '=', project.id)])
