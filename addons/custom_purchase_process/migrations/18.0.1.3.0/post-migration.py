from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    Billing is now allowed on ordered quantities even when a product's Control
    Policy is "On received quantities" (see PurchaseOrderLine._compute_qty_invoiced).

    qty_to_invoice is a stored computed field and its dependencies did not
    change, so existing rows keep their stale value (0) until recomputed here.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    lines = env['purchase.order.line'].search(
        [('order_id.state', 'in', ('purchase', 'done'))]
    )
    lines._compute_qty_invoiced()
    env['purchase.order'].search(
        [('state', 'in', ('purchase', 'done'))]
    )._get_invoiced()
    print(
        "Recomputed qty_to_invoice on %s purchase order line(s)" % len(lines)
    )
