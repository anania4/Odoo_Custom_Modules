def migrate(cr, version):
    """Notifications now go through the generic bell only.
    Remove the approval activities the workflow created; activities people
    scheduled by hand are kept."""
    cr.execute("""
        DELETE FROM mail_activity
         WHERE automated = TRUE
           AND res_model IN ('equipment.timesheet')
    """)
