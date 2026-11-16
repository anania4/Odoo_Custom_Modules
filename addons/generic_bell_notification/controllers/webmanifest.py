from odoo.tools import file_open
from odoo.addons.web.controllers import webmanifest


class WebManifest(webmanifest.WebManifest):

    def _get_service_worker_content(self):
        """Bell push handling goes first, so it can take its own pushes before
        Odoo's generic (mail) push code sees them."""
        with file_open('generic_bell_notification/static/src/js/bell_push_sw.js') as f:
            return f.read() + "\n" + super()._get_service_worker_content()
