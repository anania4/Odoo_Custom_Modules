# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


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
                ('state', 'in', ('assigned', 'completed')),
            ])

    # =========================================
    # Driver switch (car icon): complete the trip
    # =========================================

    def _driver_open_requests(self):
        """Assigned requests of this vehicle delegated to the current user"""
        self.ensure_one()
        return self.env['fleet.request'].sudo().search([
            ('vehicle_id', '=', self.id),
            ('state', '=', 'assigned'),
            ('driver_id.user_id', '=', self.env.user.id),
        ], order='scheduled_start, id')

    def _driver_switch_info(self):
        info = super()._driver_switch_info()
        requests = self._driver_open_requests()
        if requests:
            info['task'] = {
                'name': ', '.join(requests.mapped('name')),
                'destination': requests[:1].destination or '',
            }
        return info

    @api.model
    def driver_switch_status(self, vehicle_id):
        """In Use -> Active by the driver completes their assigned trip(s) on that vehicle"""
        vehicle = self.sudo().browse(vehicle_id).exists()
        requests = self.env['fleet.request']
        if vehicle and vehicle in self._my_driver_vehicles() and vehicle._driver_switch_dot() == 'in_use':
            requests = vehicle._driver_open_requests()
        result = super().driver_switch_status(vehicle_id)
        if requests:
            requests.action_complete()
            for request in requests:
                request.message_post(body=_('%s completed the trip from the driver switch.') % self.env.user.name)
            result = self.get_my_driver_vehicles()
        return result
