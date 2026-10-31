# -*- coding: utf-8 -*-
"""Vehicle State was merged into the configurable Status: drop the old column.

Every vehicle already has a Status (it was required), so it is kept as is.
Vehicles without one (should not happen) get the status matching their old state.
"""


def migrate(cr, version):
    if not version:
        return
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'fleet_vehicle' AND column_name = 'state'
    """)
    if not cr.fetchone():
        return
    cr.execute("""
        UPDATE fleet_vehicle v SET status_id = s.id, status_code = s.code
        FROM fleet_vehicle_status s
        WHERE v.status_id IS NULL AND s.code = v.state
    """)
    cr.execute("ALTER TABLE fleet_vehicle DROP COLUMN state")
