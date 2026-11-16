def migrate(cr, version):
    """
    The custom PO states 'advance_payment', 'awaiting_delivery' and
    'credit_settlement' were removed: the printed Purchase Order report only
    renders the PO number for the standard states, so POs confirmed into those
    custom states had no PO number on the print.

    Rows still holding one of the removed values are reset to 'purchase'
    *before* the module update, so the state selection no longer contains
    unknown values when the ORM reloads the model.
    """
    cr.execute(
        """
        UPDATE purchase_order
           SET state = 'purchase'
         WHERE state IN ('advance_payment', 'awaiting_delivery', 'credit_settlement')
        """
    )
    print(
        "Migration completed: %s purchase order(s) moved back to 'purchase'"
        % cr.rowcount
    )
