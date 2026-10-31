# -*- coding: utf-8 -*-
"""Turn the old free-text service provider into a vendor contact."""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'fleet_service' AND column_name = 'service_provider'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        SELECT id, TRIM(service_provider) FROM fleet_service
        WHERE partner_id IS NULL AND COALESCE(TRIM(service_provider), '') != ''
    """)
    rows = cr.fetchall()
    if not rows:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    Partner = env['res.partner']
    cache = {}
    for service_id, provider in rows:
        if provider not in cache:
            cache[provider] = Partner.search([('name', '=ilike', provider)], limit=1) \
                or Partner.create({'name': provider, 'is_company': True})
        cr.execute("UPDATE fleet_service SET partner_id = %s WHERE id = %s", (cache[provider].id, service_id))
