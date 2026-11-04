{
    'name': 'MEFS Project Lifecycle Management',
    'version': '18.0.1.0.0',
    'category': 'Project',
    'summary': 'Project stage pipeline with Full Scope and Subcontracted Scope workflows',
    'depends': ['project'],
    'data': [
        'security/ir.model.access.csv',
        'data/stage_data.xml',
        'views/project_views.xml',
        'views/stage_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'mefs_project_lifecycle/static/src/js/pipeline_stage_filter.js',
        ],
    },
    'installable': True,
    'application': False,
    'auto_install': False,
    'license': 'AGPL-3',
}
