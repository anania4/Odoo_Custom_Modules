{
    'name': 'MEFS Project Dashboard',
    'version': '18.0.1.0.0',
    'summary': 'Project dashboard: income, cost vs budget, work packages, machinery & fuel, schedule, ledger (UI only)',
    'description': """
        UI-only project dashboard in the style of the Budget Schedule dashboard.
        Shows sample data; not yet wired to the database.
    """,
    'author': 'MEFS Construction',
    'category': 'Project Management',
    # mefs_budget_planning: reuses its Budget Schedule dashboard styles (o_budget_schedule / o_bd_*)
    'depends': ['project', 'web', 'mefs_budget_planning'],
    'data': [
        'views/project_dashboard_menu.xml',
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
