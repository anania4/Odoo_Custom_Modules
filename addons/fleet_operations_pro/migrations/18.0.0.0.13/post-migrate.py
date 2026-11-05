# -*- coding: utf-8 -*-
"""Payment status was removed from vehicle agreements and services, and the
agreement's next due date is now calculated: drop the old stored columns."""

DROPS = [
    ('fleet_contract', 'payment_state'),
    ('fleet_contract', 'payment_date'),
    ('fleet_contract', 'next_due_date'),
    ('fleet_service', 'payment_state'),
    ('fleet_service', 'payment_date'),
]


def migrate(cr, version):
    if not version:
        return
    for table, column in DROPS:
        cr.execute(f'ALTER TABLE {table} DROP COLUMN IF EXISTS {column}')
