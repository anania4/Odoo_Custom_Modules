from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    """
    The Approved BOQ of a Store Requisition is now derived from its project
    (its BOQ). Requests created earlier have a project but no
    BOQ stored, so fill it in once; the BOQ descriptions are picked from it.
    """
    env = api.Environment(cr, SUPERUSER_ID, {})
    requests = env['material.request'].search([
        ('project_id', '!=', False),
        ('approved_boq_id', '=', False),
    ])
    requests._compute_approved_boq_id()
    print("Filled the approved BOQ on %s store requisition(s)" % len(requests))
