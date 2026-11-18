{
    'name': 'MEFS Project Dashboard',
    'version': '18.0.1.1.0',
    'summary': 'Project dashboard: income, cost vs budget, work packages, machinery & fuel, schedule, ledger',
    'description': """
        Project dashboard in the style of the Budget Schedule dashboard, reading live data:
        approved BOQ and IPCs, budget plan (planned expenses, schedule), vendor bills and
        purchase orders (with the store request's work item and description), equipment
        timesheets, project stages and tasks. Optional sources (store requests, equipment
        timesheets) are used when their modules are installed.
    """,
    'author': 'MEFS Construction',
    'category': 'Project Management',
    # mefs_budget_planning: budget plan + its Budget Schedule styles (o_budget_schedule / o_bd_*);
    # project_purchase: project on purchase orders (links bills to the project)
    'depends': ['project', 'web', 'account', 'project_purchase', 'mefs_budget_planning'],
    'data': [
        'views/project_dashboard_menu.xml',
        'views/project_form_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mefs_project_dashboard/static/src/**/*.scss',
            'mefs_project_dashboard/static/src/**/*.js',
            'mefs_project_dashboard/static/src/**/*.xml',
        ],
    },
    'installable': True,
    'application': False,
    'license': 'LGPL-3',
}
