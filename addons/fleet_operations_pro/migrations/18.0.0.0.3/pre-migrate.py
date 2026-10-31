# -*- coding: utf-8 -*-
"""Map removed selection values and prepare service status before the new fields load."""


def migrate(cr, version):
    if not version:
        return
    # Contract status "Cancelled" became "Closed"
    cr.execute("UPDATE fleet_contract SET state = 'closed' WHERE state = 'cancelled'")
    # Rental agreements are now recorded on the vehicle (Ownership > Rental Terms)
    cr.execute("UPDATE fleet_contract SET contract_type = 'other' WHERE contract_type = 'rental_agreement'")

    # Services recorded before the status existed were already performed: mark them Done
    cr.execute("ALTER TABLE fleet_service ADD COLUMN IF NOT EXISTS state varchar")
    cr.execute("ALTER TABLE fleet_service ADD COLUMN IF NOT EXISTS end_date date")
    cr.execute("UPDATE fleet_service SET state = 'done', end_date = COALESCE(end_date, date) WHERE state IS NULL")
