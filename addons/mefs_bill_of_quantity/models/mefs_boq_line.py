from odoo import models, fields, api, _
from odoo.exceptions import ValidationError, UserError


class MefsBoqLine(models.Model):
    _name = 'mefs.boq.line'
    _description = 'Bill of Quantity Line'
    _order = 'sequence, id'

    WORK_TYPE_SELECTION = [
        ('anchor', 'Anchor'),
        ('grout', 'Grout'),
        ('pile', 'Pile'),
        ('excavation', 'Excavation'),
        ('soil_nail', 'Soil Nail'),
        ('shotcrete', 'Shotcrete'),
    ]

    sequence = fields.Integer(string='Sequence', default=10)

    boq_id = fields.Many2one('mefs.boq', string='BOQ', ondelete='cascade', required=True)
    display_type = fields.Selection([
        ('line_section', "Main Line"),        # Level 1: 1, 2, 3
        ('line_sub_section', "Section"),      # Level 2: 1.1, 1.2
        ('line_sub', "Sub-line Section"),     # Level 3: 1.1.1, 1.1.2
        ('line_sub2', "Sub-line"),            # Level 4: 1.1.1.1, 1.1.1.2
        ('line_note', "Note"),
    ], default=False, help="Technical field for layout purpose")

    bill_no = fields.Char(string='Bill No.', store=True, readonly=True)
    is_subtotal = fields.Boolean(string='Is Subtotal', default=False)

    work_type_id = fields.Many2one('mefs.boq.work.type', string='Work Type')
    work_type = fields.Selection(WORK_TYPE_SELECTION, string='Work Type Code')
    code = fields.Char(string='Work Item Code', readonly=True, copy=False)

    product_id = fields.Many2one('product.product', string='Product')
    name = fields.Char(string='Description', required=True)
    description = fields.Text(string='Detail Description')

    original_contract_qty = fields.Float(
        string='Original Contract Qty',
        readonly=True,
        default=0.0,
        help='Baseline quantity from the contract, frozen on first lock.'
    )
    revised_contract_qty = fields.Float(
        string='Revised Contract Qty',
        default=0.0,
        help='Current active quantity. On revisions, user enters this fresh.'
    )
    quantity = fields.Float(
        string='Quantity',
        compute='_compute_quantity',
        store=True,
        help='Mirrors revised_contract_qty for backward compatibility.'
    )
    executed_quantity = fields.Float(
        string='Executed Qty',
        default=0.0,
        help='Total quantity executed from submitted daily reports.'
    )
    remaining_quantity = fields.Float(
        string='Remaining Qty',
        compute='_compute_remaining_quantity',
        store=True,
        help='Revised contract quantity minus executed quantity.'
    )
    uom_id = fields.Many2one('uom.uom', string='Unit of Measure')
    unit_price = fields.Float(string='Unit Price', required=False, default=0.0)

    def _default_taxes(self):
        company = self.env.company
        tax = company.account_sale_tax_id
        if not tax:
            tax = self.env['account.tax'].search([
                ('type_tax_use', '=', 'sale'),
                ('amount', '=', 15.0),
                ('company_id', 'in', (company.id, False)),
            ], limit=1)
        if not tax:
            tax = self.env['account.tax'].search([
                ('type_tax_use', '=', 'sale'),
                ('company_id', 'in', (company.id, False)),
            ], limit=1)
        return tax

    taxes_id = fields.Many2many(
        'account.tax',
        string='Taxes',
        context={'active_test': False},
        default=_default_taxes,
    )
    subtotal = fields.Float(
        string='Subtotal',
        compute='_compute_subtotal',
        store=True,
        readonly=False,
    )

    task_id = fields.Many2one('project.task', string='Project Task/WBS', domain="[('project_id', '=', parent.project_id)]")
    role_id = fields.Many2one('hr.job', string='Labour Role')

    @api.constrains('revised_contract_qty', 'executed_quantity')
    def _check_quantities_non_negative(self):
        for line in self:
            if line.is_subtotal or line.display_type == 'line_note':
                continue
            if (line.revised_contract_qty or 0.0) < 0.0:
                raise ValidationError(_("Contract quantity cannot be negative for line '%s'.") % (line.name or line.bill_no or ''))
            if (line.executed_quantity or 0.0) < 0.0:
                raise ValidationError(_("Executed quantity cannot be negative for line '%s'.") % (line.name or line.bill_no or ''))
            if (line.revised_contract_qty or 0.0) < (line.executed_quantity or 0.0):
                raise ValidationError(_(
                    "Remaining quantity cannot be negative for line '%(name)s'. "
                    "Contract quantity is %(contract).2f, but executed quantity is %(executed).2f."
                ) % {
                    'name': line.name or line.bill_no or '',
                    'contract': line.revised_contract_qty or 0.0,
                    'executed': line.executed_quantity or 0.0,
                })

    @api.depends('revised_contract_qty')
    def _compute_quantity(self):
        for line in self:
            line.quantity = line.revised_contract_qty

    @api.depends('revised_contract_qty', 'executed_quantity')
    def _compute_remaining_quantity(self):
        for line in self:
            line.remaining_quantity = (line.revised_contract_qty or 0.0) - (line.executed_quantity or 0.0)

    def _get_work_type_code(self):
        if self.work_type_id and self.work_type_id.code:
            return self.work_type_id.code.upper()
        codes = {
            'anchor': 'ANCHOR',
            'grout': 'GROUT',
            'pile': 'PILE',
            'excavation': 'EXCAV',
            'soil_nail': 'SNAIL',
            'shotcrete': 'SHOT',
        }
        return codes.get(self.work_type, 'GEN')

    def _generate_code(self):
        self.ensure_one()
        if self.display_type == 'line_note' or self.is_subtotal:
            return
        seq_str = self.env['ir.sequence'].next_by_code('mefs.boq.line.code') or '1'
        seq = int(''.join(c for c in seq_str if c.isdigit()) or '1')
        work_code = self._get_work_type_code()
        self.code = f"BOQ-{work_code}-{seq:02d}"

    @api.onchange('work_type_id')
    def _onchange_work_type_id(self):
        if self.work_type_id:
            code_lower = (self.work_type_id.code or '').lower()
            if code_lower in dict(self.WORK_TYPE_SELECTION):
                self.work_type = code_lower
            elif (self.work_type_id.name or '').lower().replace(' ', '_') in dict(self.WORK_TYPE_SELECTION):
                self.work_type = self.work_type_id.name.lower().replace(' ', '_')
            self._update_or_generate_code()

    @api.onchange('work_type')
    def _onchange_work_type(self):
        if self.work_type and not self.work_type_id:
            wt = self.env['mefs.boq.work.type'].search([
                '|',
                ('code', '=ilike', self._get_work_type_code()),
                ('name', '=ilike', dict(self.WORK_TYPE_SELECTION).get(self.work_type, '')),
            ], limit=1)
            if wt:
                self.work_type_id = wt
        if self.work_type or self.work_type_id:
            self._update_or_generate_code()

    def _update_or_generate_code(self):
        if not self.code:
            try:
                self._generate_code()
            except Exception:
                pass
        elif self.code.startswith('BOQ-'):
            parts = self.code.split('-')
            if len(parts) >= 3:
                self.code = f"BOQ-{self._get_work_type_code()}-{parts[2]}"

    @api.model
    def create(self, vals):
        if vals.get('display_type') == 'line_note' or vals.get('is_subtotal'):
            vals['taxes_id'] = False
        elif 'taxes_id' not in vals:
            default_tax = self._default_taxes()
            if default_tax:
                vals['taxes_id'] = [(6, 0, default_tax.ids)]
        if vals.get('work_type') and not vals.get('work_type_id'):
            code = dict(self.WORK_TYPE_SELECTION).get(vals['work_type'], '')
            wt = self.env['mefs.boq.work.type'].search([
                '|', ('code', '=ilike', vals['work_type']), ('name', '=ilike', code)
            ], limit=1)
            if wt:
                vals['work_type_id'] = wt.id
        elif vals.get('work_type_id') and not vals.get('work_type'):
            wt = self.env['mefs.boq.work.type'].browse(vals['work_type_id'])
            if wt and wt.code and wt.code.lower() in dict(self.WORK_TYPE_SELECTION):
                vals['work_type'] = wt.code.lower()
        line = super().create(vals)
        if line.display_type != 'line_note' and not line.is_subtotal and not line.code:
            try:
                line._generate_code()
            except Exception:
                pass
        return line

    def write(self, vals):
        if vals.get('work_type') and not vals.get('work_type_id'):
            code = dict(self.WORK_TYPE_SELECTION).get(vals['work_type'], '')
            wt = self.env['mefs.boq.work.type'].search([
                '|', ('code', '=ilike', vals['work_type']), ('name', '=ilike', code)
            ], limit=1)
            if wt:
                vals['work_type_id'] = wt.id
        elif vals.get('work_type_id') and not vals.get('work_type'):
            wt = self.env['mefs.boq.work.type'].browse(vals['work_type_id'])
            if wt and wt.code and wt.code.lower() in dict(self.WORK_TYPE_SELECTION):
                vals['work_type'] = wt.code.lower()
        res = super().write(vals)
        if 'work_type' in vals or 'work_type_id' in vals:
            for line in self:
                if (line.work_type or line.work_type_id) and not line.is_subtotal and line.display_type != 'line_note':
                    if not line.code:
                        try:
                            line._generate_code()
                        except Exception:
                            pass
                    elif line.code.startswith('BOQ-'):
                        parts = line.code.split('-')
                        if len(parts) >= 3:
                            line.code = f"BOQ-{line._get_work_type_code()}-{parts[2]}"
        return res

    def copy_data(self, default=None):
        if self.env.context.get('boq_revision_copy'):
            default = dict(default or {})
            default['revised_contract_qty'] = 0.0
            default['code'] = False
        return super().copy_data(default=default)

    @api.onchange('role_id')
    def _onchange_role_id(self):
        if self.role_id:
            self.name = self.role_id.name

    @api.onchange('product_id')
    def _onchange_product_id(self):
        if self.product_id:
            self.name = self.product_id.display_name
            self.uom_id = self.product_id.uom_id
            self.unit_price = self.product_id.lst_price
            if self.product_id.taxes_id:
                self.taxes_id = self.product_id.taxes_id
            else:
                self.taxes_id = self._default_taxes()

    @api.depends('revised_contract_qty', 'unit_price', 'display_type', 'is_subtotal')
    def _compute_subtotal(self):
        for line in self:
            if line.display_type == 'line_note':
                line.subtotal = 0.0
            elif line.is_subtotal:
                line.subtotal = line.unit_price
            else:
                line.subtotal = (line.revised_contract_qty or 0.0) * (line.unit_price or 0.0)

    def _get_section_child_lines(self):
        children = self.env['mefs.boq.line']
        for line in self:
            if line.display_type == 'line_section':
                stop_types = ('line_section',)
            elif line.display_type == 'line_sub_section':
                stop_types = ('line_section', 'line_sub_section')
            elif line.display_type == 'line_sub':
                stop_types = ('line_section', 'line_sub_section', 'line_sub')
            else:
                continue
            siblings = line.boq_id.boq_line_ids.sorted(key=lambda l: (l.sequence, l.id))
            try:
                idx = siblings.ids.index(line.id)
            except ValueError:
                continue
            for child in siblings[idx + 1:]:
                if child.display_type in stop_types:
                    break
                children |= child
        return children

    def unlink(self):
        if self.env.context.get('force_unlink'):
            return super().unlink()
        to_delete = self
        sections = self.filtered(
            lambda line: line.display_type in ('line_section', 'line_sub_section', 'line_sub')
        )
        if sections:
            to_delete = self | sections._get_section_child_lines()
        boqs = to_delete.mapped('boq_id')
        res = to_delete.with_context(force_unlink=True).unlink()
        if boqs:
            boqs._recompute_bill_numbers()
        return res
