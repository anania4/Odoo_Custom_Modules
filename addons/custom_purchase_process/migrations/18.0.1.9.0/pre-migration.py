def migrate(cr, version):
    """Description of Work is now a BOQ work type instead of a BOQ line. The old values are
    BOQ line ids and do not match work type ids, so clear them; they are picked again."""
    for table in ('material_request', 'purchase_request'):
        cr.execute("""
            SELECT 1 FROM information_schema.columns
             WHERE table_name = %s AND column_name = 'description_of_work_id'
        """, (table,))
        if cr.fetchone():
            cr.execute("UPDATE %s SET description_of_work_id = NULL" % table)
