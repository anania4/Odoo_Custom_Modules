from odoo import _, api, fields, models
from collections import defaultdict
from odoo.exceptions import ValidationError, UserError
from odoo.osv.expression import AND

from datetime import datetime, timedelta



class ProductSIV(models.Model):
    _name = 'product.siv'
    _description = 'Product Store Issue Voucher (SIV)'
    _inherit = ["mail.thread", "mail.activity.mixin", "analytic.mixin", "custom.purchase.notify.mixin"]
    _bell_only_notifications = True

    name = fields.Char(
        string="SIV Reference",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New')
    )

    requested_date = fields.Date(
        string="Requested Date",
        required=True,
        default=fields.Date.today,
        help="Date when the SIV was requested",
        readonly=True,
    )

    picking_ids = fields.One2many('stock.picking','siv_id', string="Pickings")
    picking_count = fields.Integer(string="Picking Count", compute="_compute_picking_count")

    @api.depends('picking_ids')
    def _compute_picking_count(self):
        for record in self:
            record.picking_count = len(record.picking_ids)

    def _get_destination_location(self):
        """Destination location for the generated transfer.

        The SIV issues goods from the store to an internal location, so the
        destination follows the operation type rather than a customer location.
        """
        self.ensure_one()
        return self.operation_type_id.default_location_dest_id

    def action_deliver(self):
        """Create stock picking for the SIV lines and set the state to delivered."""
        if self.state != 'approved':
            raise UserError(_("Only approved SIVs can be delivered."))

        if not self.product_siv_line_ids:
            raise UserError(_("There are no SIV lines to create a stock picking."))

        location_dest = self._get_destination_location()

        # Create Stock Picking
        picking_vals = {
            'partner_id': self.material_request_id.requested_by_id.partner_id.id if self.material_request_id.requested_by_id else None,
            'location_id': self.operation_type_id.default_location_src_id.id,
            'location_dest_id': location_dest.id,
            'picking_type_id': self.operation_type_id.id,
            'origin': self.name,
            'siv_id': self.id,
            'move_type': 'direct',
            'state': 'draft',
        }
        picking = self.env['stock.picking'].create(picking_vals)

        # Create Stock Moves within Picking
        for line in self.product_siv_line_ids:
            if line.requested_qty <= 0:
                raise UserError(_("Requested quantity must be greater than zero for product %s.") % line.product_id.name)

            self.env['stock.move'].create({
                'picking_id': picking.id,
                'product_id': line.product_id.id,
                'name': f"SIV: {self.name} - {line.product_id.display_name}",
                'product_uom_qty': line.requested_qty,
                'product_uom': line.product_id.uom_id.id,
                'material_request_line_id': line.material_request_line_id.id,
                'location_id': self.operation_type_id.default_location_src_id.id,
                'location_dest_id': location_dest.id,
                'state': 'draft',
            })


        self.state = 'delivered'
        self.issued_by = self.env.user.id
        self._notify_delivered(picking)

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'stock.picking',
            'view_mode': 'form',
            'res_id': picking.id,
            'target': 'current',
        }


    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('product.siv') or _('New')
        return super(ProductSIV, self).create(vals)

    material_request_id = fields.Many2one('material.request', string="Material Request")
    requested_by = fields.Many2one('res.users', string="Requested By", required=True)
    approved_by_id = fields.Many2one('res.users', string="Approved By")
    issued_by = fields.Many2one('res.users', string="Issued By")
    state = fields.Selection([('draft', 'Draft'), ('request_approval', 'Request Approval'), ('approved', 'Approved'), ('delivered', 'Delivered')], string="State", default='draft', required=True)
    operation_type_id = fields.Many2one('stock.picking.type', string="Operation Type", domain="[('code', '=', 'internal')]", required=True)
    product_siv_line_ids = fields.One2many('product.siv.line', 'product_siv_id', string="SIV Lines")
    company_id = fields.Many2one(
        'res.company',
        string="Company", readonly=True,
        required=True,
        default=lambda self: self.env.company
    )

    user_id = fields.Many2one(
        'res.users',
        string="Purchaser",
        domain=lambda self: [
            ('groups_id', 'in', self.env.ref('purchase.group_purchase_user').id),
            ('company_ids', 'in', self.env.context.get('allowed_company_ids', []))
        ],
    )

    @api.depends('approved_by_id')
    def _compute_approved_by_char(self):
        for record in self:
            record.approved_by_char = record.approved_by_id.name if record.approved_by_id else ""

    @api.depends('issued_by')
    def _compute_approved_by_chars(self):
        for record in self:
            record.approved_by_chars = record.issued_by.name if record.issued_by else ""

    def action_request_approval(self):
        """Set state to request approval and notify approvers."""
        for record in self:
            record.state = 'request_approval'
            approvers = record._get_group_users('custom_purchase_process.group_store_request_approver')
            record._notify_flow(
                forward=approvers,
                forward_title=_("Store Issue Voucher awaits your approval"),
                forward_message=_("%s for %s was submitted by %s and awaits your approval.",
                                  record.name, record.material_request_id.name or '', self.env.user.name),
                icon='fa-truck',
            )

    def action_approve(self):
        for record in self:
            record.approved_by_id = self.env.user.id  # Set the approved_by field properly
            record.state = 'approved'
            store_users = record._get_group_users(
                'custom_purchase_process.group_store_request_user',
                ['custom_purchase_process.group_store_request_approver'])
            record._notify_flow(
                forward=store_users,
                forward_title=_("Store Issue Voucher awaits delivery"),
                forward_message=_("%s was approved by %s. Deliver the items.", record.name, self.env.user.name),
                backward=record.requested_by,
                backward_title=_("Your Store Issue Voucher was approved"),
                backward_message=_("%s was approved by %s.", record.name, self.env.user.name),
                icon='fa-truck',
            )





    def _notify_delivered(self, picking):
        self.ensure_one()
        request = self.material_request_id
        self._notify_flow(
            backward=self.requested_by | self.approved_by_id | request.requested_by_id,
            backward_title=_("Store Issue Voucher delivered"),
            backward_message=_("%s%s was delivered by %s.", self.name,
                               _(" for %s", request.name) if request else '', self.env.user.name),
            icon='fa-truck',
        )

    def action_view_moves(self):
        """Open the internal transfer(s) created from this SIV so they can be validated."""
        self.ensure_one()
        pickings = self.picking_ids
        action = {
            'type': 'ir.actions.act_window',
            'name': _('Internal Transfers'),
            'res_model': 'stock.picking',
            'context': dict(self.env.context, create=False,
                            default_picking_type_id=self.operation_type_id.id),
        }
        if len(pickings) == 1:
            action.update({'view_mode': 'form', 'res_id': pickings.id})
        else:
            action.update({'view_mode': 'list,form', 'domain': [('id', 'in', pickings.ids)]})
        return action


class ProductSIVLine(models.Model):
    _name = 'product.siv.line'
    _description = 'Product SIV Line'

    product_siv_id = fields.Many2one('product.siv', string="SIV Reference", ondelete='cascade', required=True)
    product_id = fields.Many2one('product.product', string="Product", required=True)
    material_request_line_id = fields.Many2one('material.request.line', string="Material Request Line", required=True)
    requested_qty = fields.Float(string="Requested Quantity", required=True)
    issued_qty = fields.Float(string="Issued Quantity", required=True)
