# -*- coding: utf-8 -*-
"""Driver switch: the car icon in the top bar.

A user with the Fleet Driver access right sees a car icon for the vehicles
delegated to them. One click switches the vehicle between Active (green) and
In Use (red). Any other status (Available, In Maintenance...) is grey and can
only be changed by a Fleet Manager.
"""

from odoo import _, api, fields, models
from odoo.exceptions import AccessError, UserError

DRIVER_GROUP = 'fleet_operations_pro.group_fleet_driver'
ACTIVE_CODES = ('active',)
IN_USE_CODES = ('in use', 'in_use')
BUS_TYPE = 'fleet_driver_vehicle_update'


class FleetVehicle(models.Model):
    _inherit = 'fleet.vehicle'

    status_changed_on = fields.Datetime(
        string='Status Changed On',
        readonly=True,
        copy=False,
        help='When the status was last changed',
    )

    def write(self, vals):
        if 'status_id' in vals:
            vals = dict(vals, status_changed_on=fields.Datetime.now())
        result = super().write(vals)
        if 'status_id' in vals:
            self._notify_driver_switch()
        return result

    def _notify_driver_switch(self):
        """Refresh the car icon of the delegated drivers (and of whoever made the change)"""
        partners = self.sudo().mapped('driver_id.user_id.partner_id') | self.env.user.partner_id
        for partner in partners:
            self.env['bus.bus']._sendone(partner, BUS_TYPE, {'vehicle_ids': self.ids})

    @api.model
    def _status_by_codes(self, codes):
        return self.env['fleet.vehicle.status'].sudo().search([('code', 'in', list(codes))], limit=1)

    def _driver_switch_dot(self):
        self.ensure_one()
        code = (self.status_code or '').strip().lower()
        if code in ACTIVE_CODES:
            return 'active'
        if code in IN_USE_CODES:
            return 'in_use'
        return 'other'

    def _driver_switch_info(self):
        self.ensure_one()
        dot = self._driver_switch_dot()
        target_codes = IN_USE_CODES if dot == 'active' else ACTIVE_CODES if dot == 'in_use' else ()
        return {
            'id': self.id,
            'plate': self.license_plate or '',
            'name': self.name or '',
            'status': self.status_id.name or '',
            'dot': dot,
            'since': fields.Datetime.to_string(self.status_changed_on) if self.status_changed_on else False,
            'can_switch': bool(target_codes and self._status_by_codes(target_codes)),
        }

    @api.model
    def _my_driver_vehicles(self):
        employees = self.env.user.employee_ids
        if not employees:
            return self.browse()
        return self.sudo().search([('driver_id', 'in', employees.ids)], order='license_plate')

    @api.model
    def get_my_driver_vehicles(self):
        """Data for the car icon: is the user a driver, and their delegated vehicles"""
        if not self.env.user.has_group(DRIVER_GROUP):
            return {'is_driver': False, 'vehicles': []}
        return {
            'is_driver': True,
            'vehicles': [vehicle._driver_switch_info() for vehicle in self._my_driver_vehicles()],
        }

    @api.model
    def driver_switch_status(self, vehicle_id):
        """Active -> In Use or In Use -> Active, only for the driver's own delegated vehicle"""
        if not self.env.user.has_group(DRIVER_GROUP):
            raise AccessError(_('Only drivers can switch a vehicle status.'))
        vehicle = self.sudo().browse(vehicle_id).exists()
        if not vehicle or vehicle not in self._my_driver_vehicles():
            raise AccessError(_('This vehicle is not delegated to you.'))

        dot = vehicle._driver_switch_dot()
        if dot == 'active':
            target = self._status_by_codes(IN_USE_CODES)
        elif dot == 'in_use':
            target = self._status_by_codes(ACTIVE_CODES)
        else:
            raise UserError(_(
                '%(plate)s is "%(status)s". Only a Fleet Manager can change it; '
                'you can switch it once it is Active or In Use.',
                plate=vehicle.license_plate, status=vehicle.status_id.name))
        if not target:
            raise UserError(_('The Active / In Use statuses are missing in Configuration > Vehicle Statuses.'))

        old_status = vehicle.status_id.name
        vehicle.write({'status_id': target.id})
        vehicle.message_post(body=_(
            '%(user)s switched the vehicle from %(old)s to %(new)s (driver switch).',
            user=self.env.user.name, old=old_status, new=target.name))
        return self.get_my_driver_vehicles()

    def _set_in_use_for_assignment(self, reason):
        """A driver was assigned a task with this vehicle: show it as In Use.

        Vehicles already In Use are left alone; statuses a Fleet Manager set for a
        reason (In Maintenance, Out of Service, Sold, ...) are not overridden.
        """
        in_use = self._status_by_codes(IN_USE_CODES)
        if not in_use:
            return
        for vehicle in self.sudo():
            if vehicle._driver_switch_dot() == 'in_use':
                continue
            if (vehicle.status_code or '') in ('in_maintenance', 'out_of_service', 'sold', 'disposed'):
                continue
            old_status = vehicle.status_id.name
            vehicle.write({'status_id': in_use.id})
            vehicle.message_post(body=_(
                'Status changed from %(old)s to %(new)s automatically: %(reason)s',
                old=old_status, new=in_use.name, reason=reason))
