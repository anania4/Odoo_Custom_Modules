{
    'name': 'MEFS Budget Planning',
    'version': '18.0.1.1.0',
    'summary': 'Project budget planning, schedule and budget dashboard based on the approved BOQ',
    'description': """
        Budget planning for construction projects.
        - Budget plan per project and approved BOQ, composed by an employee.
        - Project Estimated Cost per BOQ work item: material, equipment, manpower and
          subcontractor costs, each group collapsible to its total.
        - Project Schedule with a day-by-day Gantt chart (status and progress per task).
        - Budget Schedule dashboard: planned income per work type with cumulative
          timeline, planned expenses per cost class fetched from the budget plan,
          headline figures and charts.
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
        'views/budget_dashboard_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mefs_budget_planning/static/src/scss/budget_planning.scss',
            'mefs_budget_planning/static/src/xml/budget_list_footer.xml',
            'mefs_budget_planning/static/src/js/schedule_gantt.js',
            'mefs_budget_planning/static/src/xml/schedule_gantt.xml',
            'mefs_budget_planning/static/src/js/estimate_groups.js',
            'mefs_budget_planning/static/src/xml/estimate_groups.xml',
            'mefs_budget_planning/static/src/dashboard/income_bar_chart.js',
            'mefs_budget_planning/static/src/dashboard/income_bar_chart.xml',
            'mefs_budget_planning/static/src/dashboard/income_cumulative_chart.js',
            'mefs_budget_planning/static/src/dashboard/income_cumulative_chart.xml',
            'mefs_budget_planning/static/src/dashboard/expense_pie_chart.js',
            'mefs_budget_planning/static/src/dashboard/expense_pie_chart.xml',
            'mefs_budget_planning/static/src/dashboard/budget_dashboard.scss',
        ],
    },
    'installable': True,
    'application': True,
    'license': 'LGPL-3',
}
