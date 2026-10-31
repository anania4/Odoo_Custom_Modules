from odoo import _, fields, models


class FleetVehicle(models.Model):
    _inherit = "fleet.vehicle"

    maintenance_request_ids = fields.One2many(
        comodel_name="maintenance.request",
        inverse_name="vehicle_id",
        string="Maintenance Requests",
    )
    maintenance_request_count = fields.Integer(
        string="Maintenance Request Count",
        compute="_compute_maintenance_request_count",
    )

    def _compute_maintenance_request_count(self):
        counts = {
            vehicle.id: count
            for vehicle, count in self.env["maintenance.request"]._read_group(
                [("vehicle_id", "in", self.ids)], ["vehicle_id"], ["__count"]
            )
        }
        for vehicle in self:
            vehicle.maintenance_request_count = counts.get(vehicle.id, 0)

    def action_view_maintenance_requests(self):
        self.ensure_one()
        return {
            "type": "ir.actions.act_window",
            "name": _("Maintenance: %s", self.display_name),
            "res_model": "maintenance.request",
            "view_mode": "list,kanban,form",
            "domain": [("vehicle_id", "=", self.id)],
            "context": {
                "default_asset_type": "vehicle",
                "default_vehicle_id": self.id,
            },
        }
