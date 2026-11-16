def migrate(cr, version):
    """The purchase workflow now notifies through the generic bell only.
    Remove the workflow activities (automated To-Dos) it created on its records;
    activities people scheduled by hand are kept."""
    cr.execute("""
        DELETE FROM mail_activity
         WHERE automated = TRUE
           AND res_model IN ('material.request', 'purchase.request', 'purchase.quotation',
                             'supplier.analysis', 'quality.inspection', 'product.siv')
    """)
