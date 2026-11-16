{
    'name': 'Generic Bell Notification',
    'version': '1.2',
    'depends': ['base', 'web', 'bus', 'mail'],
    'author': 'Bisrat Jenbere',
    'category': 'Tools',
    'data': [
        'security/ir.model.access.csv',
        'security/generic_notification_security.xml',
        'views/generic_notification_views.xml',
    ],
   'assets': {
    'web.assets_backend': [
        'generic_bell_notification/static/src/scss/bell_systray.scss',
        'generic_bell_notification/static/src/xml/bell_systray.xml',
        'generic_bell_notification/static/src/js/bell_alerts.js',
        'generic_bell_notification/static/src/js/bell_systray.js',
    ],
    },

    'installable': True,
    'application': False,
}