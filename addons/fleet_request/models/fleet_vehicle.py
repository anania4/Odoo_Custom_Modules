# -*- coding: utf-8 -*-

from odoo import models, fields


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    request_ids = fields.One2many(
        'fleet.request',
        'vehicle_id',
        string='Accepted Fleet Requests',
        help='Fleet requests this vehicle accepted (driver assigned)'
    )
    accepted_request_count = fields.Integer(
        string='Accepted Requests',
        compute='_compute_accepted_request_count',
        store=False,
        help='Number of fleet requests accepted by this vehicle'
    )

    def _compute_accepted_request_count(self):
        """Count fleet requests accepted (assigned) by this vehicle"""
        if not self.env['fleet.request'].has_access('read'):
            # e.g. Fleet Viewer: may open vehicles but not fleet requests
            self.accepted_request_count = 0
            return
        for vehicle in self:
            vehicle.accepted_request_count = self.env['fleet.request'].search_count([
                ('vehicle_id', '=', vehicle.id),
                ('state', '=', 'assigned'),
            ])
