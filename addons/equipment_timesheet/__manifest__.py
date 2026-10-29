# -*- coding: utf-8 -*-
{
    'name': 'Equipment Timesheet',
    'version': '18.0.1.0.0',
    'category': 'Services/Timesheets',
    'summary': 'Track field equipment working time (Day & Night hours) and fuel consumption per project',
    'description': """
Equipment Field Timesheet Tracking
==================================
This module provides a specialized Timesheet system to track equipment working time and fuel on the field:
* **Project Dashboard**: A dedicated dashboard for Project Managers to view projects, total working hours, fuel consumed, and pending timesheets.
* **Role-Based Views**: Normal users only see their own reported/imported timesheets; Project Managers see all projects and all timesheets.
* **Locked Fields for Reporter**: Date (locked to today) and Username (locked to logged-in user).
* **Equipment Integration**: Select equipment directly from Maintenance Equipment Registration (`maintenance.equipment`) with auto-populated type/category, model, and serial number.
* **Shift Tracking**:
  - Day (Morning) Hours: Start time, End time, and auto-calculated Day Hours.
  - Night (Afternoon) Hours: Start time, End time, and auto-calculated Night Hours.
  - Auto-calculated Total Hours.
* **Fuel Tracking**:
  - Fuel Refueled (L)
  - Fuel Left (L)
  - Auto-calculated Fuel Consumed (L) = Fuel Refueled - Fuel Left.
* **Approval Workflow**:
  - Normal users create and submit timesheets.
  - Project Managers review and approve/reject submitted timesheets.
    """,
    'author': 'Custom Development',
    'website': 'https://www.odoo.com',
    'depends': [
        'base',
        'mail',
        'project',
        'maintenance',
        'hr_timesheet',
    ],
    'data': [
        'security/equipment_timesheet_security.xml',
        'security/ir.model.access.csv',
        'data/ir_sequence_data.xml',
        'wizard/equipment_timesheet_export_wizard_views.xml',
        'views/equipment_timesheet_views.xml',
        'views/project_project_views.xml',
        'views/menu_views.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'equipment_timesheet/static/src/css/equipment_timesheet.css',
            'equipment_timesheet/static/src/scss/equipment_timesheet.scss',
            'equipment_timesheet/static/src/js/export_report_menu.js',
            'equipment_timesheet/static/src/xml/export_report_menu.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'post_init_hook': 'post_init_hook',
    'license': 'LGPL-3',
}
