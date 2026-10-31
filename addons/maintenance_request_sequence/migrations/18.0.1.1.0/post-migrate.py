# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, SUPERUSER_ID

from odoo.addons.maintenance_request_sequence.models.maintenance_team import (
    SEQUENCE_PREFIX,
)


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    sequence = env.ref(
        "maintenance_request_sequence.seq_maintenance_request_auto",
        raise_if_not_found=False,
    )
    if sequence:
        sequence.write(
            {
                "prefix": "MR/%s/" % SEQUENCE_PREFIX,
                "use_date_range": True,
            }
        )
    teams = env["maintenance.team"].search(
        [("sequence_id", "!=", False), ("code_prefix", "!=", False)]
    )
    for team in teams:
        team.sequence_id.write(
            {
                "prefix": team._get_sequence_prefix(team.code_prefix),
                "use_date_range": True,
            }
        )
