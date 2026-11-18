{
    "name": "HR Performance Evaluation",
    "version": "3.0",
    "category": "Human Resources",
    "summary": "Department-specific performance appraisal with configurable templates",
    "description": """
        Performance Evaluation v3.0:
        - Department-specific evaluation templates
        - Questions reusable across multiple templates
        - Department managers evaluate employees using their department's template
        - HR reviews and finalizes
        - Automatic scoring and grading
        - Employees can view their own completed appraisals
        - Targeted notifications (no broadcast spam)
        - Duplicate appraisal prevention
    """,
    "author": "Hanna Alemayehu",
    "license": "LGPL-3",
    "depends": ["hr", "mail", "generic_bell_notification"],
    "data": [
        "security/groups.xml",
        "security/ir.model.access.csv",
        "security/record_rules.xml",
        "views/appraisal_views.xml",
        "views/question_views.xml",
        "views/template_views.xml",
        "views/menus.xml",
        "data/default_questions.xml",
        "data/migrate_default_template.xml",
    ],
    "application": True,
    "installable": True,

    'assets': {},
}
