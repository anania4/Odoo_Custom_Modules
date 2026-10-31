# -*- coding: utf-8 -*-
{
    'name': 'Fleet Requests',
    'version': '18.0.1.0.0',
    'category': 'Operations/Fleet',
    'summary': 'Employee fleet request and approval workflow',
    'description': """
Fleet Requests
==============
Standalone module for managing employee fleet requests and their approval
workflow. It is linked to Fleet Operations Pro through a module dependency.

Features:
- Employees request a vehicle and schedule a trip
- Department manager and fleet manager approval workflow
- Driver and vehicle assignment by the fleet manager
- Accepted requests accessible from the vehicle form
- Fuel requests with previous fuel history, odometer readings and approvals
    """,
    'author': 'Cyshield',
    'website': 'https://www.cyshield.com',
    'license': 'GPL-3',
    'depends': [
        'fleet_operations_pro',
        'mail',
        'hr',
    ],
    'data': [
        'security/fleet_request_security.xml',
        'security/ir.model.access.csv',
        'data/fuel_request_sequence.xml',
        'views/fleet_request_views.xml',
        'views/fleet_fuel_request_views.xml',
        'views/fleet_vehicle_views.xml',
        'views/fleet_menu_views.xml',
    ],
    'demo': [],
    'installable': True,
    'application': True,
    'auto_install': False,
}
