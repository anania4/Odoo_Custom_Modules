import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    quality_evaluation = fields.Boolean(string="Quality Assurance")
    passed_evaluation = fields.Boolean(string="Passed Evaluation")
    evaluation_remark = fields.Char(string="Evaluation Remark")
    remark = fields.Char(string="Remark")
    purchase_request_id = fields.Many2one('purchase.request', string="Purchase Request")
    purchase_request_supplier_id = fields.Many2one('supplier.analysis', string="Purchase Request")

    # Shown in the list view. Related text fields are read with sudo, so the list works for
    # purchasers who cannot read employees or the other users.
    finance_officer_name = fields.Char(
        string="Finance Officer",
        related='purchase_request_supplier_id.finance_officer_id.name',
    )
    finance_manager_name = fields.Char(
        string="Finance Manager",
        related='purchase_request_supplier_id.finance_approved_by.name',
    )

    procurement_type = fields.Selection([
        ('pay_to_procure', 'Pay to Procure'),
        ('procure_to_pay', 'Procure to Pay')
    ], string="Procurement Type", required=True, default='pay_to_procure')

    delivery_instruction_ids = fields.One2many(
        'delivery.instruction.line', 'purchase_order_id', string="Delivery Instructions"
    )

    is_unlocked = fields.Boolean(
        string="Unlocked", default=False, copy=False, readonly=True, tracking=True,
        help="Set when a Purchase Administrator unlocks a confirmed order: every field "
             "(vendor, products, quantities, unit prices...) can then be edited until "
             "the order is locked again.",
    )

    def button_unlock(self):
        """Only Purchase Administrators can unlock. Unlocking a confirmed or locked
        order makes all of its fields editable until it is locked again."""
        if not self.env.user.has_group('purchase.group_purchase_manager'):
            raise UserError(_("Only a Purchase Administrator can unlock a purchase order."))
        locked = self.filtered(lambda o: o.state == 'done')
        if locked:
            super(PurchaseOrder, locked).button_unlock()
        to_unlock = self.filtered(lambda o: o.state == 'purchase' and not o.is_unlocked)
        to_unlock.write({'is_unlocked': True})
        for order in to_unlock:
            order.message_post(body=_("Purchase order unlocked for editing by %s.", self.env.user.name))
        return True

    def button_done(self):
        """Locking the order ends the unlocked editing."""
        res = super().button_done()
        self.filtered('is_unlocked').write({'is_unlocked': False})
        return res

    def button_cancel(self):
        res = super().button_cancel()
        self.filtered('is_unlocked').write({'is_unlocked': False})
        return res

    @api.model
    def _install_finance_list_columns(self):
        """Add the Finance Officer / Finance Manager columns to the purchase order lists.

        The standard list view names differ between Odoo versions, so the extension is only
        created for the list views that exist and have a Buyer column; a missing or
        different view is skipped (and logged) instead of failing the module upgrade.
        """
        View = self.env['ir.ui.view'].sudo()
        arch = (
            '<data><xpath expr="//field[@name=\'user_id\']" position="after">'
            '<field name="finance_officer_name" optional="show"/>'
            '<field name="finance_manager_name" optional="show"/>'
            '</xpath></data>'
        )
        for xmlid in ('purchase.purchase_order_view_tree', 'purchase.purchase_order_tree'):
            base = self.env.ref(xmlid, raise_if_not_found=False)
            if not base or base.model != 'purchase.order':
                _logger.info("List view %s not found, finance columns not added to it", xmlid)
                continue
            data_name = 'view_finance_columns_%s' % xmlid.split('.')[1]
            if self.env.ref('custom_purchase_process.%s' % data_name, raise_if_not_found=False):
                continue
            try:
                with self.env.cr.savepoint():
                    view = View.create({
                        'name': 'purchase.order.list.finance.%s' % xmlid.split('.')[1],
                        'model': 'purchase.order',
                        'inherit_id': base.id,
                        'mode': 'extension',
                        'arch': arch,
                    })
                    self.env['ir.model.data'].sudo().create({
                        'module': 'custom_purchase_process',
                        'name': data_name,
                        'model': 'ir.ui.view',
                        'res_id': view.id,
                        'noupdate': True,
                    })
            except Exception:
                _logger.exception("Could not add the finance columns to list view %s", xmlid)

    def _get_sr_warehouse(self):
        """Warehouse selected on the Store Requisition (older requests without one fall
        back to the warehouse of their Store)."""
        self.ensure_one()
        material_request = self.purchase_request_id.material_request_id
        return material_request.warehouse_id or material_request.from_location_id.warehouse_id

    @api.model
    def _incoming_type_of_warehouse(self, warehouse, company_id):
        if not warehouse:
            return self.env['stock.picking.type']
        return self.env['stock.picking.type'].search([
            ('code', '=', 'incoming'),
            ('warehouse_id', '=', warehouse.id),
            ('warehouse_id.company_id', '=', company_id),
        ], limit=1)

    def _get_store_incoming_picking_type(self):
        """Incoming (receipt) operation type of the warehouse selected on the SR."""
        self.ensure_one()
        return self._incoming_type_of_warehouse(self._get_sr_warehouse(), self.company_id.id)

    def _get_sr_receipt_location(self):
        """Location the goods are received into: the SR Store when it belongs to the SR
        warehouse, otherwise the main stock location of that warehouse."""
        self.ensure_one()
        material_request = self.purchase_request_id.material_request_id
        warehouse = self._get_sr_warehouse()
        location = material_request.from_location_id
        if warehouse and (not location or location.warehouse_id != warehouse):
            return warehouse.lot_stock_id
        return location

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get('purchase_request_id'):
                continue
            request = self.env['purchase.request'].browse(vals['purchase_request_id'])
            # The Buyer is the Procurement Officer assigned on the Purchase Request.
            if request.user_id and not vals.get('user_id'):
                vals['user_id'] = request.user_id.id
            # Receive into the warehouse selected on the Store Requisition: keep an
            # explicitly chosen operation type, otherwise use that warehouse's receipts.
            if vals.get('picking_type_id'):
                continue
            material_request = request.material_request_id
            warehouse = material_request.warehouse_id or material_request.from_location_id.warehouse_id
            picking_type = self._incoming_type_of_warehouse(
                warehouse, vals.get('company_id') or self.env.company.id)
            if picking_type:
                vals['picking_type_id'] = picking_type.id
        return super().create(vals_list)

    def button_confirm(self):
        """The receipt must go to the warehouse selected on the Store Requisition,
        whatever 'Deliver To' was left on the order."""
        for order in self.filtered(lambda o: o.state in ('draft', 'sent') and o.purchase_request_id):
            warehouse = order._get_sr_warehouse()
            if not warehouse or order.picking_type_id.warehouse_id == warehouse:
                continue
            picking_type = order._get_store_incoming_picking_type()
            if not picking_type:
                raise UserError(_(
                    "Warehouse '%s' selected on the Store Requisition has no receipt operation type.",
                    warehouse.display_name))
            order.picking_type_id = picking_type
        return super().button_confirm()

    def _get_destination_location(self):
        """Receive where the Store Requisition says (see _get_sr_receipt_location).

        purchase_stock uses this for BOTH the incoming picking and its stock moves,
        so overriding it keeps the receipt and its operation lines in sync.
        """
        self.ensure_one()
        location = self._get_sr_receipt_location() if self.purchase_request_id.material_request_id else False
        if location:
            return location.id
        return super()._get_destination_location()

    def _get_final_location_record(self):
        """Keep the move's final location consistent with the SR warehouse/Store."""
        self.ensure_one()
        location = self._get_sr_receipt_location() if self.purchase_request_id.material_request_id else False
        if location:
            return location
        return super()._get_final_location_record()

    def _prepare_picking(self):
        vals = super()._prepare_picking()
        self.ensure_one()

        request = self.purchase_request_id
        material_request = request.material_request_id

        # Carry the Project of the process down to the receipt
        project = self.project_id or request.project_id or material_request.project_id
        if project:
            vals['project_id'] = project.id

        return vals

    def action_view_purchase_orders(self):
        """Open the purchase orders related to this purchase request."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('purchase_request_id', '=', self.id)],
            'context': {'default_purchase_request_id': self.id},
        }

    def action_view_purchase_orders_suppliers(self):
        """Open the purchase orders related to this purchase request."""
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Purchase Orders'),
            'res_model': 'purchase.order',
            'view_mode': 'list,form',
            'domain': [('purchase_request_supplier_id', '=', self.id)],
            'context': {'default_purchase_request_supplier_id': self.id},
        }


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    @api.depends('invoice_lines.move_id.state', 'invoice_lines.quantity', 'qty_received', 'product_uom_qty', 'order_id.state')
    def _compute_qty_invoiced(self):
        super()._compute_qty_invoiced()
        # Allow billing on ordered quantities even when the product's Control
        # Policy is "On received quantities". The goods are received later, so
        # without this the bill cannot be created until the receipt is done.
        for line in self:
            if line.order_id.state in ('purchase', 'done'):
                line.qty_to_invoice = line.product_qty - line.qty_invoiced
