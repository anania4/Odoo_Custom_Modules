def migrate(cr, version):
    """The Finance Officer on a supplier analysis is now an employee instead of a user.
    The old values are user ids and would not match employee ids, so clear them; the
    Finance Manager picks the employee again."""
    cr.execute("""
        SELECT 1 FROM information_schema.columns
         WHERE table_name = 'supplier_analysis' AND column_name = 'finance_officer_id'
    """)
    if cr.fetchone():
        cr.execute("UPDATE supplier_analysis SET finance_officer_id = NULL")
