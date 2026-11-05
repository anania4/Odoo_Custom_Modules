# -*- coding: utf-8 -*-

from odoo import api, models


class ResPartner(models.Model):
    _inherit = 'res.partner'

    @api.model
    def _fleet_vendor_domain(self):
        """Domain for every vendor field of the fleet system: only vendors.

        Accounting/Purchase mark vendors with a supplier rank (set when a contact is
        created from the Vendors menu or gets a vendor bill). Without those apps,
        fall back to companies.
        """
        if 'supplier_rank' in self._fields:
            return [('supplier_rank', '>', 0)]
        return [('is_company', '=', True)]
