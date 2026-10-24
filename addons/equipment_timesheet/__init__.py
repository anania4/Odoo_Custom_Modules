from . import models
from . import wizard


def post_init_hook(env):
    """Deactivate default Odoo 18 HR Timesheets menu."""
    menu = env.ref('hr_timesheet.timesheet_menu_root', raise_if_not_found=False)
    if menu:
        menu.sudo().write({
            'active': False,
        })
