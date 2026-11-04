{
    'name': 'MEFS Project BOQ Construction',
    'version': '18.0.1.0.0',
    'summary': 'Bill of Quantities (BOQ) for Construction and Contracting Projects',
    'description': """
        MEFS Construction Project BOQ and Cost Tracking.
        Features:
        - BOQ Revision Management with auto-generation.
        - BOQ Locking/Unlocking.
        - Integration with Project and Job Cost Sheets.
        - PDF Reports for Customers.
    """,
    'author': 'MEFS Construction',
    'website': 'https://www.mefsconstruction.com',
    'category': 'Project Management',
    'depends': [
        'project',
        'hr_timesheet',
        'analytic',
        'uom',
        'account',
        'mefs_project_lifecycle',
    ],
    'data': [
        'security/boq_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'data/mefs_boq_work_type_data.xml',
        'report/boq_report_template.xml',
        'report/boq_report_action.xml',
        'report/boq_payment_report_template.xml',
        'report/boq_payment_report_action.xml',
        'views/mefs_boq_work_type_views.xml',
        'views/mefs_boq_views.xml',
        'views/mefs_boq_payment_views.xml',
        'views/project_views.xml',
        'views/res_partner_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mefs_bill_of_quantity/static/src/xml/boq_list_renderer.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
