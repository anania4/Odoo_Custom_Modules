from decimal import Decimal
from odoo import models, fields, api, _
from odoo.exceptions import UserError


def num_to_words_en(num):
    """Convert an integer to English words."""
    if num == 0:
        return "Zero"

    units = [
        "", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine",
        "Ten", "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen",
        "Seventeen", "Eighteen", "Nineteen"
    ]
    tens = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]
    scales = ["", "Thousand", "Million", "Billion", "Trillion"]

    def convert_hundreds(n):
        words = []
        h = n // 100
        r = n % 100
        if h > 0:
            words.append(units[h] + " Hundred")
        if r > 0:
            if r < 20:
                words.append(units[r])
            else:
                t = r // 10
                u = r % 10
                if u > 0:
                    words.append(f"{tens[t]} {units[u]}")
                else:
                    words.append(tens[t])
        return " ".join(words)

    chunks = []
    temp = abs(num)
    while temp > 0:
        chunks.append(temp % 1000)
        temp //= 1000

    words = []
    for i in range(len(chunks) - 1, -1, -1):
        c = chunks[i]
        if c > 0:
            c_words = convert_hundreds(c)
            scale = scales[i]
            if scale:
                words.append(f"{c_words} {scale}")
            else:
                words.append(c_words)

    result = " ".join(words).strip()
    return f"Negative {result}" if num < 0 else result


def amount_to_birr_words(amount, currency_name="Birr"):
    """
    Format amount to words in construction IPC format:
    e.g. 15558974.48 -> 'Fifteen Million Five Hundred Fifty Eight Thousand Nine Hundred Seventy Four Birr and 48/100'
    """
    if amount is None:
        return ""
    try:
        amt = Decimal(str(round(amount, 2)))
        int_part = int(amt)
        dec_part = int(round((amt - Decimal(str(int_part))) * 100))
        if dec_part < 0:
            dec_part = abs(dec_part)

        int_words = num_to_words_en(int_part)
        return f"{int_words} {currency_name} and {dec_part:02d}/100"
    except Exception:
        return f"{amount} {currency_name}"


class MefsBoqPayment(models.Model):
    _name = 'mefs.boq.payment'
    _description = 'BOQ Payment / Interim Payment Certificate'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Payment No.',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )
    boq_id = fields.Many2one(
        'mefs.boq',
        string='BOQ Reference',
        required=True,
        ondelete='cascade',
        tracking=True,
    )
    project_id = fields.Many2one(
        'project.project',
        string='Project',
        related='boq_id.project_id',
        store=True,
        readonly=False,
        tracking=True,
    )
    partner_id = fields.Many2one(
        'res.partner',
        string='Client',
        related='boq_id.partner_id',
        store=True,
        readonly=False,
        tracking=True,
    )
    consultant = fields.Char(
        string='Consultant',
        default="Citta Consulting Architects PLC",
    )
    contractor = fields.Char(
        string='Contractor',
        default="M E FOUNDATION SPECIALIST PLC",
    )
    date = fields.Date(
        string='Payment Date',
        default=fields.Date.context_today,
        required=True,
        tracking=True,
    )
    currency_id = fields.Many2one(
        'res.currency',
        string='Currency',
        related='boq_id.currency_id',
        store=True,
        readonly=False,
    )
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('paid', 'Paid'),
        ('cancel', 'Cancelled'),
    ], string='Status', default='draft', tracking=True, copy=False)

    # Dates & Approvals
    certificate_date = fields.Date(string='Certificate Date')
    approved_date = fields.Date(string='Approved Date')
    paid_date = fields.Date(string='Paid Date')
    certified_by = fields.Char(string='Certified By', default="M E FOUNDATION SPECIALIST PLC")
    approved_by = fields.Char(string='Approved By')

    line_ids = fields.One2many(
        'mefs.boq.payment.line',
        'payment_id',
        string='Payment Lines',
        copy=True,
    )

    # Contract Sums
    main_contract_amount = fields.Float(
        string='Main Contract',
        compute='_compute_contract_totals',
        store=True,
        readonly=False,
    )
    supplementary_contract_amount = fields.Float(
        string='Supplementary Contract',
        default=0.0,
    )
    variation_order_amount = fields.Float(
        string='Variation Order',
        default=0.0,
    )
    contract_vat_amount = fields.Float(
        string='Contract VAT (15%)',
        compute='_compute_contract_totals',
        store=True,
        readonly=False,
    )
    total_contract_sum = fields.Float(
        string='Total Contract Sum',
        compute='_compute_contract_totals',
        store=True,
        readonly=False,
    )

    # Progress Payment Totals
    total_previous_amount = fields.Float(
        string='Previous Executed Amount',
        compute='_compute_line_totals',
        store=True,
        readonly=False,
    )
    total_current_amount = fields.Float(
        string='Payment Due for Executed Work',
        compute='_compute_line_totals',
        store=True,
        readonly=False,
        help='Current payment amount due for work executed before deductions and VAT.',
    )
    total_todate_amount = fields.Float(
        string='Todate Executed Amount',
        compute='_compute_line_totals',
        store=True,
        readonly=False,
    )

    # Advance Payment Summary
    advance_payment_net = fields.Float(string='Advance Payment Net')
    advance_payment_vat = fields.Float(string='Advance Payment VAT')

    # Deductions
    previous_payments_deduction = fields.Float(
        string='1. Previous Payments',
        default=0.0,
        help='Cumulative previous net payments made to contractor',
    )
    loan_repayment = fields.Float(string='2. Loan Repayment', default=0.0)
    retention_rate = fields.Float(string='Retention (%)', default=5.0)
    retention_amount = fields.Float(
        string='3. Retention (5%)',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    advance_repayment = fields.Float(string='4. Advance Repayment', default=0.0)
    other_deductions = fields.Float(string='5. Others', default=0.0)
    total_deductions = fields.Float(
        string='Total Deductions',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )

    # Net Amount & VAT
    net_amount_before_vat = fields.Float(
        string='Net Amount Due Contractor Before VAT',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    vat_rate = fields.Float(string='VAT Rate (%)', default=15.0)
    vat_on_executed = fields.Float(
        string='VAT on Work Executed',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    vat_on_advance_repayment = fields.Float(
        string='VAT on Advance Repayment',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    vat_on_previous_payment = fields.Float(
        string='VAT on Previous Payment',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    vat_on_loan_repayment = fields.Float(
        string='VAT on Loan Repayment',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    total_vat_deductions = fields.Float(
        string='Total VAT Deductions',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    vat_amount = fields.Float(
        string='VAT Payable',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    net_amount_due = fields.Float(
        string='Net Amount Due Contractor (Inc. VAT)',
        compute='_compute_financial_summary',
        store=True,
        readonly=False,
    )
    amount_words = fields.Char(
        string='Amount in Words',
        compute='_compute_amount_words',
        store=True,
        readonly=False,
    )

    note = fields.Text(
        string='Terms & Remarks',
        default="We certify that the Contractor is now entitled in the sum certified herein for work properly executed.",
    )

    @api.depends('boq_id', 'boq_id.total_amount', 'supplementary_contract_amount', 'variation_order_amount')
    def _compute_contract_totals(self):
        for rec in self:
            main_amt = rec.boq_id.total_amount or 0.0
            rec.main_contract_amount = main_amt
            sub_total = main_amt + (rec.supplementary_contract_amount or 0.0) + (rec.variation_order_amount or 0.0)
            vat = round(sub_total * 0.15, 2)
            rec.contract_vat_amount = vat
            rec.total_contract_sum = round(sub_total + vat, 2)

    @api.depends(
        'line_ids.previous_amount',
        'line_ids.current_amount',
        'line_ids.todate_amount',
        'line_ids.is_subtotal',
        'line_ids.display_type'
    )
    def _compute_line_totals(self):
        for rec in self:
            prev = 0.0
            curr = 0.0
            todate = 0.0
            for line in rec.line_ids:
                if line.is_subtotal or line.display_type in ('line_section', 'line_note'):
                    continue
                prev += line.previous_amount or 0.0
                curr += line.current_amount or 0.0
                todate += line.todate_amount or 0.0
            rec.total_previous_amount = round(prev, 2)
            rec.total_current_amount = round(curr, 2)
            rec.total_todate_amount = round(todate, 2)

    @api.depends(
        'total_current_amount',
        'retention_rate',
        'previous_payments_deduction',
        'loan_repayment',
        'advance_repayment',
        'other_deductions',
        'vat_rate'
    )
    def _compute_financial_summary(self):
        for rec in self:
            curr = rec.total_current_amount or 0.0
            retention = round(curr * ((rec.retention_rate or 0.0) / 100.0), 2)
            rec.retention_amount = retention

            deductions = (
                (rec.previous_payments_deduction or 0.0) +
                (rec.loan_repayment or 0.0) +
                retention +
                (rec.advance_repayment or 0.0) +
                (rec.other_deductions or 0.0)
            )
            rec.total_deductions = round(deductions, 2)
            net_before_vat = round(curr - deductions, 2)
            rec.net_amount_before_vat = net_before_vat

            vat_rate_dec = (rec.vat_rate or 0.0) / 100.0
            vat_exec = round(curr * vat_rate_dec, 2)
            vat_adv = round((rec.advance_repayment or 0.0) * vat_rate_dec, 2)
            vat_prev = round((rec.previous_payments_deduction or 0.0) * vat_rate_dec, 2)
            vat_loan = round((rec.loan_repayment or 0.0) * vat_rate_dec, 2)
            tot_vat_ded = round(vat_adv + vat_prev + vat_loan, 2)
            vat_payable = round(vat_exec - tot_vat_ded, 2)

            rec.vat_on_executed = vat_exec
            rec.vat_on_advance_repayment = vat_adv
            rec.vat_on_previous_payment = vat_prev
            rec.vat_on_loan_repayment = vat_loan
            rec.total_vat_deductions = tot_vat_ded
            rec.vat_amount = vat_payable
            rec.net_amount_due = round(net_before_vat + vat_payable, 2)

    @api.depends('net_amount_due', 'currency_id')
    def _compute_amount_words(self):
        for rec in self:
            curr_name = rec.currency_id.name or 'Birr'
            if curr_name == 'ETB':
                curr_name = 'Birr'
            rec.amount_words = amount_to_birr_words(rec.net_amount_due, curr_name)

    @api.onchange(
        'total_current_amount',
        'retention_rate',
        'previous_payments_deduction',
        'loan_repayment',
        'advance_repayment',
        'other_deductions',
        'vat_rate'
    )
    def _onchange_financial_inputs(self):
        curr = self.total_current_amount or 0.0
        self.retention_amount = round(curr * ((self.retention_rate or 0.0) / 100.0), 2)
        self.total_deductions = round(
            (self.previous_payments_deduction or 0.0) +
            (self.loan_repayment or 0.0) +
            self.retention_amount +
            (self.advance_repayment or 0.0) +
            (self.other_deductions or 0.0),
            2
        )
        self.net_amount_before_vat = round(curr - self.total_deductions, 2)

        vat_rate_dec = (self.vat_rate or 0.0) / 100.0
        vat_exec = round(curr * vat_rate_dec, 2)
        vat_adv = round((self.advance_repayment or 0.0) * vat_rate_dec, 2)
        vat_prev = round((self.previous_payments_deduction or 0.0) * vat_rate_dec, 2)
        vat_loan = round((self.loan_repayment or 0.0) * vat_rate_dec, 2)
        tot_vat_ded = round(vat_adv + vat_prev + vat_loan, 2)
        vat_payable = round(vat_exec - tot_vat_ded, 2)

        self.vat_on_executed = vat_exec
        self.vat_on_advance_repayment = vat_adv
        self.vat_on_previous_payment = vat_prev
        self.vat_on_loan_repayment = vat_loan
        self.total_vat_deductions = tot_vat_ded
        self.vat_amount = vat_payable
        self.net_amount_due = round(self.net_amount_before_vat + vat_payable, 2)

        curr_name = self.currency_id.name or 'Birr'
        if curr_name == 'ETB':
            curr_name = 'Birr'
        self.amount_words = amount_to_birr_words(self.net_amount_due, curr_name)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('name') or vals.get('name') in (_('New'), 'New'):
                boq_id = vals.get('boq_id')
                if boq_id:
                    existing_count = self.search_count([('boq_id', '=', boq_id)])
                    vals['name'] = f"IPC-{existing_count + 1:02d}"
                else:
                    seq = self.env['ir.sequence'].next_by_code('mefs.boq.payment') or '01'
                    vals['name'] = f"IPC-{seq}" if not str(seq).startswith('IPC-') else str(seq)
        return super().create(vals_list)

    @api.onchange('boq_id')
    def _onchange_boq_id(self):
        if self.boq_id:
            if not self.name or self.name in (_('New'), 'New') or self.name.startswith('IPC-'):
                count = self.search_count([
                    ('boq_id', '=', self.boq_id.id),
                    ('id', '!=', self._origin.id or 0),
                ])
                self.name = f"IPC-{count + 1:02d}"
            if not self.line_ids:
                self.action_load_boq_lines()

    def action_load_boq_lines(self):
        """
        Populates or refreshes payment lines from the referenced BOQ.
        Inherits previously executed quantities and amounts from the latest existing payment.
        """
        self.ensure_one()
        if not self.boq_id:
            raise UserError(_("Please select a BOQ first."))

        # Find latest payment for the same BOQ (excluding self and cancelled)
        prev_payments = self.search([
            ('boq_id', '=', self.boq_id.id),
            ('id', '!=', self.id or 0),
            ('state', 'not in', ('draft', 'cancel')),
        ], order='date desc, id desc')
        if not prev_payments:
            prev_payments = self.search([
                ('boq_id', '=', self.boq_id.id),
                ('id', '!=', self.id or 0),
                ('state', '!=', 'cancel'),
            ], order='date desc, id desc')

        prev_line_map = {}
        if prev_payments:
            latest_payment = prev_payments[0]
            for pline in latest_payment.line_ids:
                if pline.boq_line_id:
                    prev_line_map[pline.boq_line_id.id] = pline
                elif pline.bill_no:
                    prev_line_map[pline.bill_no] = pline

        # Unlink existing lines
        self.line_ids.unlink()

        lines_to_create = []
        for line in self.boq_id.boq_line_ids.sorted(key=lambda l: (l.sequence, l.id)):
            if line.display_type == 'line_note':
                lines_to_create.append({
                    'payment_id': self.id,
                    'boq_line_id': line.id,
                    'name': line.name,
                    'display_type': line.display_type,
                    'sequence': line.sequence,
                })
                continue

            prev_executed = 0.0
            prev_amount = 0.0
            prev_line = prev_line_map.get(line.id) or (prev_line_map.get(line.bill_no) if line.bill_no else None)
            if prev_line:
                prev_executed = prev_line.todate_executed_qty or 0.0
                prev_amount = prev_line.todate_amount or 0.0

            qty = line.revised_contract_qty or line.original_contract_qty or 0.0
            price = line.unit_price or 0.0
            contract_amt = line.subtotal if line.is_subtotal else (qty * price)

            lines_to_create.append({
                'payment_id': self.id,
                'boq_line_id': line.id,
                'bill_no': line.bill_no,
                'name': line.name,
                'display_type': line.display_type,
                'is_subtotal': line.is_subtotal,
                'uom_id': line.uom_id.id if line.uom_id else False,
                'contract_qty': qty,
                'unit_price': price,
                'contract_amount': contract_amt,
                'previously_executed_qty': prev_executed,
                'currently_executed_qty': 0.0,
                'todate_executed_qty': prev_executed,
                'previous_amount': prev_amount,
                'current_amount': 0.0,
                'todate_amount': prev_amount,
                'sequence': line.sequence,
            })

        self.env['mefs.boq.payment.line'].create(lines_to_create)
        self.main_contract_amount = self.boq_id.total_amount

    def action_sync_from_daily_reports(self):
        """
        Synchronizes currently executed quantities from project daily reports if recorded.
        Calculates currently executed = total executed to-date - previously executed.
        """
        self.ensure_one()
        updated_count = 0
        for line in self.line_ids:
            if line.boq_line_id and hasattr(line.boq_line_id, 'executed_quantity'):
                exec_qty = line.boq_line_id.executed_quantity or 0.0
                if exec_qty:
                    prev_qty = line.previously_executed_qty or 0.0
                    curr_qty = max(0.0, exec_qty - prev_qty)
                    line.currently_executed_qty = curr_qty
                    line.todate_executed_qty = prev_qty + curr_qty
                    line.current_amount = round(curr_qty * (line.unit_price or 0.0), 2)
                    line.todate_amount = round((line.previous_amount or 0.0) + line.current_amount, 2)
                    updated_count += 1

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': _('Synced with Daily Reports'),
                'message': _('Updated %d line(s) from site daily reports executed quantities.') % updated_count,
                'type': 'success',
                'sticky': False,
            }
        }

    def action_submit(self):
        self.write({'state': 'submitted'})

    def action_approve(self):
        self.write({
            'state': 'approved',
            'approved_date': fields.Date.context_today(self),
        })

    def action_mark_paid(self):
        self.write({
            'state': 'paid',
            'paid_date': fields.Date.context_today(self),
        })

    def action_set_to_draft(self):
        self.write({'state': 'draft'})

    def action_cancel(self):
        self.write({'state': 'cancel'})

    def action_print_ipc(self):
        self.ensure_one()
        return self.env.ref('mefs_bill_of_quantity.action_report_mefs_boq_payment').report_action(self)

    def _get_payment_report_data(self):
        """
        Prepares formatted data matching the official Excel IPC document:
        - Cover Sheet: INTERIM PAYMENT CERTIFICATE (Contract sums, Advance, Deductions, VAT, Signatures)
        - Sheet 2: BOQ Progress Breakdown table with Bill subtotals and Grand Summary.
        """
        self.ensure_one()

        def format_currency(val):
            if val is None or val == '':
                return ''
            try:
                fval = float(val)
                if abs(fval) < 0.001:
                    return '0.00'
                return f"{fval:,.2f}"
            except (ValueError, TypeError):
                return str(val)

        def format_qty(val):
            if val is None or val == '':
                return ''
            try:
                fval = float(val)
                if abs(fval) < 0.0001:
                    return ''
                if fval.is_integer():
                    return f"{int(fval):,}"
                return f"{fval:,.3f}".rstrip('0').rstrip('.')
            except (ValueError, TypeError):
                return str(val)

        rows = []
        section_summaries = []
        current_sec_num = 0
        current_sec_title = ''
        current_sec_contract = 0.0
        current_sec_prev = 0.0
        current_sec_curr = 0.0
        current_sec_todate = 0.0

        lines = self.line_ids.sorted(key=lambda l: (l.sequence, l.id))

        def close_section(sec_num, title, c_tot, p_tot, cur_tot, t_tot):
            if sec_num > 0 or cur_tot or c_tot:
                section_summaries.append({
                    'num': str(sec_num) if sec_num > 0 else '1',
                    'title': f"Bill No. {sec_num}: {title}" if sec_num > 0 else f"Bill No. 1: {title or 'Main Works'}",
                    'contract_amount': format_currency(c_tot),
                    'previous_amount': format_currency(p_tot),
                    'current_amount': format_currency(cur_tot),
                    'todate_amount': format_currency(t_tot),
                    'c_raw': c_tot,
                    'p_raw': p_tot,
                    'cur_raw': cur_tot,
                    't_raw': t_tot,
                })

        for line in lines:
            dt = line.display_type
            if dt == 'line_section':
                if current_sec_num > 0:
                    rows.append({
                        'bill_no': '',
                        'name': f"Sub-Total Bill No. {current_sec_num}",
                        'is_section': False,
                        'is_subtotal': True,
                        'is_note': False,
                        'unit': '',
                        'contract_qty': '',
                        'unit_price': '',
                        'contract_amount': format_currency(current_sec_contract),
                        'previously_executed_qty': '',
                        'currently_executed_qty': '',
                        'todate_executed_qty': '',
                        'previous_amount': format_currency(current_sec_prev),
                        'current_amount': format_currency(current_sec_curr),
                        'todate_amount': format_currency(current_sec_todate),
                    })
                    close_section(
                        current_sec_num, current_sec_title,
                        current_sec_contract, current_sec_prev,
                        current_sec_curr, current_sec_todate
                    )

                sec_digits = ''.join(c for c in (line.bill_no or '') if c.isdigit())
                current_sec_num = int(sec_digits) if sec_digits else (current_sec_num + 1)
                current_sec_title = line.name or ''
                current_sec_contract = 0.0
                current_sec_prev = 0.0
                current_sec_curr = 0.0
                current_sec_todate = 0.0

                rows.append({
                    'bill_no': line.bill_no or str(current_sec_num),
                    'name': line.name or '',
                    'is_section': True,
                    'is_subtotal': False,
                    'is_note': False,
                    'unit': '',
                    'contract_qty': '',
                    'unit_price': '',
                    'contract_amount': '',
                    'previously_executed_qty': '',
                    'currently_executed_qty': '',
                    'todate_executed_qty': '',
                    'previous_amount': '',
                    'current_amount': '',
                    'todate_amount': '',
                })
            elif line.is_subtotal:
                continue
            elif dt == 'line_note':
                rows.append({
                    'bill_no': '',
                    'name': line.name or '',
                    'is_section': False,
                    'is_subtotal': False,
                    'is_note': True,
                    'unit': '',
                    'contract_qty': '',
                    'unit_price': '',
                    'contract_amount': '',
                    'previously_executed_qty': '',
                    'currently_executed_qty': '',
                    'todate_executed_qty': '',
                    'previous_amount': '',
                    'current_amount': '',
                    'todate_amount': '',
                })
            else:
                c_amt = line.contract_amount or round((line.contract_qty or 0.0) * (line.unit_price or 0.0), 2)
                p_amt = line.previous_amount or 0.0
                cur_amt = line.current_amount or 0.0
                t_amt = line.todate_amount or round(p_amt + cur_amt, 2)

                current_sec_contract += c_amt
                current_sec_prev += p_amt
                current_sec_curr += cur_amt
                current_sec_todate += t_amt

                rows.append({
                    'bill_no': line.bill_no or '',
                    'name': line.name or '',
                    'is_section': False,
                    'is_subtotal': False,
                    'is_note': False,
                    'unit': line.uom_id.name if line.uom_id else '',
                    'contract_qty': format_qty(line.contract_qty),
                    'unit_price': format_currency(line.unit_price) if line.unit_price else '',
                    'contract_amount': format_currency(c_amt) if c_amt else '',
                    'previously_executed_qty': format_qty(line.previously_executed_qty),
                    'currently_executed_qty': format_qty(line.currently_executed_qty),
                    'todate_executed_qty': format_qty(line.todate_executed_qty),
                    'previous_amount': format_currency(p_amt) if (p_amt or line.previously_executed_qty) else '0.00',
                    'current_amount': format_currency(cur_amt) if (cur_amt or line.currently_executed_qty) else '0.00',
                    'todate_amount': format_currency(t_amt) if (t_amt or line.todate_executed_qty) else '0.00',
                })

        # Close final section
        if current_sec_num > 0 or current_sec_contract or current_sec_curr:
            sec_display_num = current_sec_num if current_sec_num > 0 else 1
            sec_display_title = current_sec_title or 'Main Works'
            rows.append({
                'bill_no': '',
                'name': f"Sub-Total Bill No. {sec_display_num}",
                'is_section': False,
                'is_subtotal': True,
                'is_note': False,
                'unit': '',
                'contract_qty': '',
                'unit_price': '',
                'contract_amount': format_currency(current_sec_contract),
                'previously_executed_qty': '',
                'currently_executed_qty': '',
                'todate_executed_qty': '',
                'previous_amount': format_currency(current_sec_prev),
                'current_amount': format_currency(current_sec_curr),
                'todate_amount': format_currency(current_sec_todate),
            })
            close_section(
                sec_display_num, sec_display_title,
                current_sec_contract, current_sec_prev,
                current_sec_curr, current_sec_todate
            )

        sum_contract = sum(s['c_raw'] for s in section_summaries) if section_summaries else (self.main_contract_amount or 0.0)
        sum_prev = sum(s['p_raw'] for s in section_summaries) if section_summaries else (self.total_previous_amount or 0.0)
        sum_curr = sum(s['cur_raw'] for s in section_summaries) if section_summaries else (self.total_current_amount or 0.0)
        sum_todate = sum(s['t_raw'] for s in section_summaries) if section_summaries else (self.total_todate_amount or 0.0)

        vat_contract = round(sum_contract * 0.15, 2)
        vat_prev = round(sum_prev * 0.15, 2)
        vat_curr = round(sum_curr * 0.15, 2)
        vat_todate = round(sum_todate * 0.15, 2)

        grand_contract = sum_contract + vat_contract
        grand_prev = sum_prev + vat_prev
        grand_curr = sum_curr + vat_curr
        grand_todate = sum_todate + vat_todate

        # Extract number for title: e.g. "IPC-01" -> "1"
        ipc_num_str = self.name.replace('IPC-', '').lstrip('0') or '1'

        # Advance payment rows
        advance_payment_list = []
        tot_adv_net = self.advance_payment_net or 0.0
        tot_adv_vat = self.advance_payment_vat or round(tot_adv_net * 0.15, 2)
        if tot_adv_net:
            advance_payment_list.append({
                'no': 'Adva. 1',
                'date': self.date.strftime('%d/%m/%Y') if self.date else '',
                'net_payment': format_currency(tot_adv_net),
                'vat': format_currency(tot_adv_vat),
            })

        # Previous payments rows
        previous_payment_list = []
        tot_prev_net = 0.0
        tot_prev_vat = 0.0
        prev_payments = self.search([
            ('boq_id', '=', self.boq_id.id),
            ('id', '!=', self.id or 0),
            ('state', 'in', ('approved', 'paid')),
            ('date', '<=', self.date),
        ], order='date asc, id asc')

        for p in prev_payments:
            p_net = p.net_amount_before_vat or 0.0
            p_vat = p.vat_amount or 0.0
            tot_prev_net += p_net
            tot_prev_vat += p_vat
            previous_payment_list.append({
                'no': p.name,
                'date': p.date.strftime('%d/%m/%Y') if p.date else '',
                'net_payment': format_currency(p_net),
                'vat': format_currency(p_vat),
            })

        if not previous_payment_list and self.previous_payments_deduction:
            prev_vat_calc = round(self.previous_payments_deduction * 0.15, 2)
            tot_prev_net = self.previous_payments_deduction
            tot_prev_vat = prev_vat_calc
            previous_payment_list.append({
                'no': '1',
                'date': '',
                'net_payment': format_currency(self.previous_payments_deduction),
                'vat': format_currency(prev_vat_calc),
            })

        vat_rate_dec = (self.vat_rate or 15.0) / 100.0
        curr_executed = self.total_current_amount or sum_curr
        vat_exec = self.vat_on_executed or round(curr_executed * vat_rate_dec, 2)
        vat_adv = self.vat_on_advance_repayment or round((self.advance_repayment or 0.0) * vat_rate_dec, 2)
        vat_prev = self.vat_on_previous_payment or round((self.previous_payments_deduction or 0.0) * vat_rate_dec, 2)
        vat_loan = self.vat_on_loan_repayment or round((self.loan_repayment or 0.0) * vat_rate_dec, 2)
        tot_vat_ded = round(vat_adv + vat_prev + vat_loan, 2)
        vat_payable = self.vat_amount or round(vat_exec - tot_vat_ded, 2)

        return {
            'ipc_number': ipc_num_str,
            'payment_no': self.name,
            'project_name': self.project_id.name or '',
            'client_name': self.partner_id.name or '',
            'consultant': self.consultant or 'Citta Consulting Architects PLC',
            'contractor': self.contractor or 'M E FOUNDATION SPECIALIST PLC',
            'date_month_year': self.date.strftime('%B, %Y') if self.date else '',
            'date_full': self.date.strftime('%b. %d, %Y') if self.date else '',
            'currency_name': self.currency_id.name or 'ETB',
            # Contract Sums
            'main_contract_amount': format_currency(self.main_contract_amount or sum_contract),
            'supplementary_contract_amount': format_currency(self.supplementary_contract_amount) if self.supplementary_contract_amount else '',
            'variation_order_amount': format_currency(self.variation_order_amount) if self.variation_order_amount else '',
            'contract_vat_amount': format_currency(self.contract_vat_amount or vat_contract),
            'total_contract_sum': format_currency(self.total_contract_sum or grand_contract),
            # Executed Work
            'total_current_amount': format_currency(curr_executed),
            # Advance Payment Summary
            'advance_payment_list': advance_payment_list,
            'advance_payment_total_net': format_currency(tot_adv_net) if tot_adv_net else '0.00',
            'advance_payment_total_vat': format_currency(tot_adv_vat) if tot_adv_vat else '0.00',
            # Previous Payment Summary
            'previous_payment_list': previous_payment_list,
            'previous_payment_total_net': format_currency(tot_prev_net) if tot_prev_net else '0.00',
            'previous_payment_total_vat': format_currency(tot_prev_vat) if tot_prev_vat else '0.00',
            # Deductions
            'previous_payments_deduction': format_currency(self.previous_payments_deduction) if self.previous_payments_deduction else '0.00',
            'loan_repayment': format_currency(self.loan_repayment) if self.loan_repayment else '',
            'retention_amount': format_currency(self.retention_amount),
            'advance_repayment': format_currency(self.advance_repayment) if self.advance_repayment else '',
            'other_deductions': format_currency(self.other_deductions) if self.other_deductions else '',
            'total_deductions': format_currency(self.total_deductions),
            # Net & VAT
            'net_amount_before_vat': format_currency(self.net_amount_before_vat),
            'vat_on_executed': format_currency(vat_exec),
            'vat_on_advance': format_currency(vat_adv) if self.advance_repayment else '0.00',
            'vat_on_previous': format_currency(vat_prev) if self.previous_payments_deduction else '0.00',
            'vat_on_loan': format_currency(vat_loan) if self.loan_repayment else '0.00',
            'total_vat_deductions': format_currency(tot_vat_ded) if tot_vat_ded else '0.00',
            'vat_payable': format_currency(vat_payable),
            'vat_amount': format_currency(self.vat_amount or vat_payable),
            'net_amount_due': format_currency(self.net_amount_due),
            'amount_words': self.amount_words or '',
            # Signatures
            'certified_by': self.certified_by or 'M E FOUNDATION SPECIALIST PLC',
            'approved_by': self.approved_by or (self.partner_id.name or ''),
            'certificate_date': self.certificate_date.strftime('%d/%m/%Y') if self.certificate_date else '',
            'approved_date': self.approved_date.strftime('%d/%m/%Y') if self.approved_date else '',
            'paid_date': self.paid_date.strftime('%d/%m/%Y') if self.paid_date else '',
            # Lines and Summaries
            'rows': rows,
            'section_summaries': section_summaries,
            'summary_total_before_vat': {
                'contract': format_currency(sum_contract),
                'prev': format_currency(sum_prev),
                'curr': format_currency(sum_curr),
                'todate': format_currency(sum_todate),
            },
            'vat_15': {
                'contract': format_currency(vat_contract),
                'prev': format_currency(vat_prev),
                'curr': format_currency(vat_curr),
                'todate': format_currency(vat_todate),
            },
            'grand_total': {
                'contract': format_currency(grand_contract),
                'prev': format_currency(grand_prev),
                'curr': format_currency(grand_curr),
                'todate': format_currency(grand_todate),
            },
        }


class MefsBoqPaymentLine(models.Model):
    _name = 'mefs.boq.payment.line'
    _description = 'BOQ Payment Line'
    _order = 'sequence, id'

    payment_id = fields.Many2one(
        'mefs.boq.payment',
        string='Payment Certificate',
        ondelete='cascade',
        required=True,
    )
    boq_line_id = fields.Many2one(
        'mefs.boq.line',
        string='BOQ Line',
        ondelete='set null',
    )
    sequence = fields.Integer(string='Sequence', default=10)
    bill_no = fields.Char(string='Bill No.')
    name = fields.Char(string='Description of Works', required=True)
    display_type = fields.Selection([
        ('line_section', 'Section'),
        ('line_sub_section', 'Sub-section'),
        ('line_sub', 'Sub-line Section'),
        ('line_sub2', 'Sub-line'),
        ('line_note', 'Note'),
    ], default=False)
    is_subtotal = fields.Boolean(string='Is Subtotal', default=False)
    uom_id = fields.Many2one('uom.uom', string='Unit')

    # Contract Baseline
    contract_qty = fields.Float(string='Quantity', default=0.0)
    unit_price = fields.Float(string='Price in ETB', default=0.0)
    contract_amount = fields.Float(string='Total in ETB', default=0.0)

    # 1. Previously Executed (from last payment)
    previously_executed_qty = fields.Float(string='Previously Executed', default=0.0)
    previous_amount = fields.Float(string='Previous Amount', default=0.0)

    # 2. Currently Executed (this period to be paid)
    currently_executed_qty = fields.Float(string='Currently Executed', default=0.0)
    current_amount = fields.Float(string='Current Amount', default=0.0)

    # 3. Todate / Total Executed
    todate_executed_qty = fields.Float(string='Todate Executed', default=0.0)
    todate_amount = fields.Float(string='Todate Amount', default=0.0)

    @api.onchange('currently_executed_qty')
    def _onchange_currently_executed_qty(self):
        for line in self:
            curr_qty = line.currently_executed_qty or 0.0
            price = line.unit_price or 0.0
            line.current_amount = round(curr_qty * price, 2)
            line.todate_executed_qty = (line.previously_executed_qty or 0.0) + curr_qty
            line.todate_amount = round((line.previous_amount or 0.0) + line.current_amount, 2)

    @api.onchange('previously_executed_qty')
    def _onchange_previously_executed_qty(self):
        for line in self:
            prev_qty = line.previously_executed_qty or 0.0
            price = line.unit_price or 0.0
            line.previous_amount = round(prev_qty * price, 2)
            line.todate_executed_qty = prev_qty + (line.currently_executed_qty or 0.0)
            line.todate_amount = round(line.previous_amount + (line.current_amount or 0.0), 2)

    @api.onchange('unit_price')
    def _onchange_unit_price(self):
        for line in self:
            price = line.unit_price or 0.0
            line.contract_amount = round((line.contract_qty or 0.0) * price, 2)
            line.previous_amount = round((line.previously_executed_qty or 0.0) * price, 2)
            line.current_amount = round((line.currently_executed_qty or 0.0) * price, 2)
            line.todate_amount = round(line.previous_amount + line.current_amount, 2)

    @api.onchange('contract_qty')
    def _onchange_contract_qty(self):
        for line in self:
            line.contract_amount = round((line.contract_qty or 0.0) * (line.unit_price or 0.0), 2)

    @api.onchange('previous_amount', 'current_amount')
    def _onchange_amounts(self):
        for line in self:
            line.todate_amount = round((line.previous_amount or 0.0) + (line.current_amount or 0.0), 2)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('display_type') and not vals.get('is_subtotal'):
                price = vals.get('unit_price', 0.0)
                contract_qty = vals.get('contract_qty', 0.0)
                prev_qty = vals.get('previously_executed_qty', 0.0)
                curr_qty = vals.get('currently_executed_qty', 0.0)

                if 'contract_amount' not in vals and contract_qty and price:
                    vals['contract_amount'] = round(contract_qty * price, 2)
                if 'previous_amount' not in vals and prev_qty and price:
                    vals['previous_amount'] = round(prev_qty * price, 2)
                if 'current_amount' not in vals and curr_qty and price:
                    vals['current_amount'] = round(curr_qty * price, 2)
                if 'todate_executed_qty' not in vals:
                    vals['todate_executed_qty'] = prev_qty + curr_qty
                if 'todate_amount' not in vals:
                    vals['todate_amount'] = round(
                        vals.get('previous_amount', 0.0) + vals.get('current_amount', 0.0),
                        2
                    )
        return super().create(vals_list)
