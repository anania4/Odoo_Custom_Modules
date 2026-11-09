# -*- coding: utf-8 -*-
{
    'name': 'Fleet Operations Pro',
    'version': '18.0.0.0.16',
    'category': 'Operations/Fleet',
    'summary': 'Comprehensive Fleet Management System',
    'description': """
Fleet Operations Pro
====================
A comprehensive fleet management system for Odoo 18 that includes:

Features:
- Vehicle Master Data Management with categories and status tracking
- Driver Management via HR Employees with vehicle assignments
- Fuel Management with consumption tracking
- Maintenance Management with service history
- Vehicle Agreement Management (insurance policies, leases, service agreements) with expiry reminders
- Service Management with one-time or recurring km intervals
- Toll Records
- Trip Management
- Driver Assignments and a driver switch (Active / In Use) in the top bar
- Dashboard and a date-range Fleet Report (odometer, fuel, services, agreements per vehicle)
- Multi-company support

This module is standalone and does not depend on Odoo's base fleet module.
    """,
    'author': 'Cyshield',
    'website': 'https://www.cyshield.com',
    'license': 'GPL-3',
    'depends': [
        'mail',
        'web',
        'hr',
        'generic_bell_notification',
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
        'data/contract_type_data.xml',
        'data/fleet_cron.xml',

        'views/driver_views.xml',
        'views/fuel_log_views.xml',
        'views/maintenance_views.xml',
        'views/fleet_contract_views.xml',


        'views/toll_views.xml',
        'views/trip_views.xml',
        'views/vehicle_views.xml',
        'views/fleet_dashboard_views.xml',
        'views/fleet_menu_views.xml',
        'views/vehicle_config_views.xml',
        'wizard/fleet_monthly_report_views.xml',
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
            'fleet_operations_pro/static/src/driver_switch/driver_switch.scss',
            'fleet_operations_pro/static/src/driver_switch/driver_switch.js',
            'fleet_operations_pro/static/src/driver_switch/driver_switch.xml',
        ],
    },
}

