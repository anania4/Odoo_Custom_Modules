# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"
    _rec_names_search = ["code"]

    code = fields.Char(readonly=True, copy=False, default="/")
    asset_type = fields.Selection(
        selection=[("machinery", "Machinery"), ("vehicle", "Vehicle")],
        string="Asset Type",
        default="machinery",
        required=True,
        tracking=True,
        help="Machinery uses Maintenance Equipment; Vehicle uses Fleet Vehicles.",
    )
    vehicle_id = fields.Many2one(
        comodel_name="fleet.vehicle",
        string="Vehicle",
        index=True,
        tracking=True,
        ondelete="restrict",
    )

    @api.onchange("asset_type")
    def _onchange_asset_type(self):
        if self.asset_type == "vehicle":
            self.equipment_id = False
        else:
            self.vehicle_id = False

    @api.constrains("asset_type", "equipment_id", "vehicle_id")
    def _check_asset_type(self):
        for rec in self:
            if rec.asset_type == "vehicle" and rec.equipment_id:
                raise ValidationError(
                    _("A vehicle maintenance request cannot have an equipment.")
                )
            if rec.asset_type == "machinery" and rec.vehicle_id:
                raise ValidationError(
                    _("A machinery maintenance request cannot have a vehicle.")
                )

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get("code", "/") == "/":
                team_id = vals.get("maintenance_team_id")
                sequence = self.env["maintenance.team"].browse(
                    team_id
                ).sequence_id or self.env.ref(
                    "maintenance_request_sequence.seq_maintenance_request_auto"
                )
                vals["code"] = sequence.next_by_id()
        return super().create(vals_list)
