from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """The Buyer of a purchase order is the Procurement Officer assigned on its Purchase
    Request. Orders that are not confirmed yet get it now; confirmed ones are left alone."""
    env = api.Environment(cr, SUPERUSER_ID, {})
    orders = env['purchase.order'].search([
        ('purchase_request_id.user_id', '!=', False),
        ('state', 'in', ('draft', 'sent', 'to approve')),
    ])
    for order in orders:
        officer = order.purchase_request_id.user_id
        if order.user_id != officer:
            order.user_id = officer
