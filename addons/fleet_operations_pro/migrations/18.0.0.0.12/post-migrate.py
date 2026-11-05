# -*- coding: utf-8 -*-
"""Contracts are now called Vehicle Agreements: rename the noupdate records too
(only when they still carry the original names, so user edits are kept)."""

from odoo import api, SUPERUSER_ID

RENAMES = [
    ('fleet_operations_pro.contract_type_service', 'Service Contract', 'Service Agreement'),
    ('fleet_operations_pro.ir_cron_fleet_contract_check', 'Fleet: Contract Expiry Check',
     'Fleet: Vehicle Agreement Expiry Check'),
    ('fleet_operations_pro.seq_fleet_contract', 'Fleet Contract', 'Vehicle Agreement'),
]


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    for xmlid, old_name, new_name in RENAMES:
        record = env.ref(xmlid, raise_if_not_found=False)
        if record and record.name == old_name:
            record.name = new_name
