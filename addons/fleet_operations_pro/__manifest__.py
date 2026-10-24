# -*- coding: utf-8 -*-
{
    'name': 'Fleet Operations Pro',
    'version': '18.0.0.0.1',
    'category': 'Operations/Fleet',
    'summary': 'Comprehensive Fleet Management System',
    'description': """
Fleet Operations Pro
====================
A comprehensive fleet management system for Odoo 18 that includes:

Features:
- Vehicle Master Data Management with categories and status tracking
- Driver Management with license tracking and expiry alerts
- Fuel Management with consumption tracking
- Maintenance Management with service history
- Compliance & Certificate Management with expiry reminders
- Toll Management
- Trip Management
- Automated Insurance Expiry Reminders
- Driver Assignments
- Preventive Maintenance Scheduling
- Vehicle Analysis Reporting

This module is standalone and does not depend on Odoo's base fleet module.
    """,
    'author': 'Cyshield',
    'website': 'https://www.cyshield.com',
    'license': 'GPL-3',
    'depends': [
        'mail',
        'web',
        'hr',
    ],
    'data': [
        'security/fleet_security.xml',
        'security/fleet_security_rules.xml',
        'security/ir.model.access.csv',        
        'data/fleet_sequence.xml',
        'data/vehicle_category_data.xml',
        'data/vehicle_status_data.xml',
        'data/fuel_type_data.xml',
        'data/maintenance_type_data.xml',
        'data/certificate_type_data.xml',
        'data/maintenance_schedule_cron.xml',
        'data/insurance_cron.xml',
        'data/email_templates/email_template_data.xml',

        'views/driver_views.xml',
        'views/fuel_log_views.xml',
        'views/maintenance_views.xml',
        'views/certificate_views.xml',

        'wizard/fleet_fuel_log_wizard_views.xml',

        'views/toll_views.xml',
        'views/trip_views.xml',
        'views/rental_views.xml',
        'views/insurance_views.xml',
        'views/fleet_request_views.xml',
        'views/maintenance_schedule_views.xml',
        'views/vehicle_views.xml',
        'views/fleet_dashboard_views.xml',
        'views/fleet_menu_views.xml',
        'report/fleet_report_views.xml',
    ],
    'demo': [],
    'images': [
        'static/description/icon.png',
        'static/description/cyshield.png',
        'static/description/trip_route_management_01.png',
        'static/description/maintenance_management_01.png',
        'static/description/maintenance_management_02.png',
        'static/description/fuel_management_01.png',
        'static/description/driver_management_01.png',
        'static/description/vehicle_01.png',
        'static/description/vehicle_02.png',
        'static/description/report_01.png',
    ],
    'installable': True,
    'application': True,
    'auto_install': False,
    'assets': {
        'web.assets_backend': [
            'fleet_operations_pro/static/src/dashboard/fleet_dashboard.scss',
            'fleet_operations_pro/static/src/dashboard/fleet_dashboard.js',
            'fleet_operations_pro/static/src/dashboard/fleet_dashboard.xml',
        ],
    },
}

