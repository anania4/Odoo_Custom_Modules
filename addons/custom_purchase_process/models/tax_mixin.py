from odoo import _, api, fields, models


class PurchaseTaxAmountsMixin(models.AbstractModel):
    """Shared tax maths for the purchase request / quotation / analysis lines.

    These documents do not carry a currency field, so amounts are always
    interpreted in the current company currency.
    """

    _name = "custom.purchase.tax.amounts.mixin"
    _description = "Purchase Tax Amounts Helper"

    def _compute_taxed_amount(self, taxes, price_unit, quantity, partner=None, product=None):
        """Return the total including taxes for a single line.

        Delegates to Odoo's generic tax computation so that tax groups,
        price-included taxes and rounding behave exactly like
        ``purchase.order.line`` instead of re-implementing them.
        """
        self.ensure_one()
        price_unit = price_unit or 0.0
        quantity = quantity or 0.0
        untaxed = price_unit * quantity
        if not taxes:
            return untaxed
        totals = taxes.sudo().compute_all(
            price_unit,
            currency=self.env.company.currency_id,
            quantity=quantity,
            product=product or self.env["product.product"],
            partner=partner or self.env["res.partner"],
        )
        return totals.get("total_included", untaxed)