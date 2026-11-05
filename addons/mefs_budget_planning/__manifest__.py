{
    'name': 'MEFS Budget Planning',
    'version': '18.0.1.0.0',
    'summary': 'Project budget planning / estimated cost based on approved BOQ',
    'description': """
        Budget planning for construction projects.
        - Composed by an employee, for a project and its approved BOQ.
        - Project Estimated Cost table per BOQ work item with material, equipment, manpower and subcontractor totals.
    """,
    'author': 'MEFS Construction',
    'category': 'Project Management',
    'depends': [
        'hr',
        'product',
        'uom',
        'project',
        'mefs_bill_of_quantity',
    ],
    'data': [
        'security/budget_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'views/mefs_budget_plan_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mefs_budget_planning/static/src/scss/budget_planning.scss',
            'mefs_budget_planning/static/src/xml/budget_list_footer.xml',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
