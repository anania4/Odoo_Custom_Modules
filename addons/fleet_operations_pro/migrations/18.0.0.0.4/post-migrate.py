# -*- coding: utf-8 -*-
"""Contract type became a configurable model; references lose the duplicated FCL part."""

from odoo import api, SUPERUSER_ID

OLD_TYPE_XMLIDS = {
    'insurance': 'fleet_operations_pro.contract_type_insurance',
    'lease': 'fleet_operations_pro.contract_type_lease',
    'service_contract': 'fleet_operations_pro.contract_type_service',
    'other': 'fleet_operations_pro.contract_type_other',
}


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Map the old selection column onto the new contract types
    cr.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'fleet_contract' AND column_name = 'contract_type'
    """)
    if cr.fetchone():
        for old_value, xmlid in OLD_TYPE_XMLIDS.items():
            contract_type = env.ref(xmlid, raise_if_not_found=False)
            if contract_type:
                cr.execute("""
                    UPDATE fleet_contract SET contract_type_id = %s
                    WHERE contract_type_id IS NULL AND contract_type = %s
                """, (contract_type.id, old_value))
    other = env.ref(OLD_TYPE_XMLIDS['other'], raise_if_not_found=False)
    if other:
        cr.execute("UPDATE fleet_contract SET contract_type_id = %s WHERE contract_type_id IS NULL", (other.id,))
    cr.execute("ALTER TABLE fleet_contract ALTER COLUMN contract_type_id SET NOT NULL")

    # 2. Sequences are noupdate: apply the new prefixes (INS/2026/00001, SRV/2026/00001)
    contract_seq = env.ref('fleet_operations_pro.seq_fleet_contract', raise_if_not_found=False)
    if contract_seq and contract_seq.prefix == 'FCL/%(year)s/':
        contract_seq.prefix = '%(year)s/'
    service_seq = env.ref('fleet_operations_pro.seq_fleet_service', raise_if_not_found=False)
    if service_seq and service_seq.prefix == 'SVN':
        service_seq.prefix = 'SRV/%(year)s/'

    # 3. Existing references: INS/FCL/2026/00001 -> INS/2026/00001
    cr.execute("UPDATE fleet_contract SET name = REPLACE(name, '/FCL/', '/') WHERE name LIKE '%%/FCL/%%'")
