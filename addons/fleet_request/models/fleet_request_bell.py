# -*- coding: utf-8 -*-

from odoo import _, models

FLEET_MANAGER = 'fleet_operations_pro.group_fleet_manager'
FUEL_FILLER = 'fleet_request.group_fuel_filler'


class FleetRequest(models.Model):
    _name = 'fleet.request'
    _inherit = ['fleet.request', 'fleet.bell.mixin']

    def write(self, vals):
        old_states = {request.id: request.state for request in self} if 'state' in vals else {}
        result = super().write(vals)
        for request in self:
            if old_states and old_states.get(request.id) != request.state:
                request._bell_on_state_change()
        return result

    def _bell_requester(self):
        return self.employee_id.user_id

    def _bell_on_state_change(self):
        self.ensure_one()
        employee = self.employee_id.name or ''
        if self.state == 'submitted':
            approvers = self.employee_id.parent_id.user_id | self.employee_id.department_id.manager_id.user_id
            self._bell_notify(
                approvers, _('Fleet request to approve'),
                _('%(ref)s from %(employee)s needs your approval (department manager).',
                  ref=self.name, employee=employee),
                notif_type='warning')
        elif self.state == 'dept_approved':
            self._bell_notify(
                self._bell_group_users(FLEET_MANAGER), _('Fleet request to approve'),
                _('%(ref)s from %(employee)s was approved by the department manager and needs fleet approval.',
                  ref=self.name, employee=employee),
                notif_type='warning')
        elif self.state == 'fleet_approved':
            self._bell_notify(
                self._bell_group_users(FLEET_MANAGER), _('Assign a driver'),
                _('%(ref)s from %(employee)s is approved and waiting for a driver.',
                  ref=self.name, employee=employee))
        elif self.state == 'assigned':
            self._bell_notify(
                self.driver_id.user_id, _('New trip delegated to you'),
                _('%(ref)s: drive %(vehicle)s for %(employee)s, %(pickup)s to %(destination)s.',
                  ref=self.name, vehicle=self.vehicle_id.display_name, employee=employee,
                  pickup=self.pickup_location or '-', destination=self.destination or '-'),
                notif_type='warning', icon='fa-road')
            self._bell_notify(
                self._bell_requester(), _('Driver assigned'),
                _('%(ref)s: %(driver)s will drive you with %(vehicle)s.',
                  ref=self.name, driver=self.driver_id.name, vehicle=self.vehicle_id.display_name),
                notif_type='success')
        elif self.state == 'completed':
            self._bell_notify(
                self._bell_requester(), _('Trip completed'),
                _('%(ref)s was completed by %(driver)s.', ref=self.name, driver=self.driver_id.name),
                notif_type='success', icon='fa-check')
        elif self.state == 'rejected':
            self._bell_notify(
                self._bell_requester(), _('Fleet request rejected'),
                _('%(ref)s was rejected: %(reason)s', ref=self.name, reason=self.rejection_reason or '-'),
                notif_type='danger', icon='fa-times')


class FleetFuelRequest(models.Model):
    _name = 'fleet.fuel.request'
    _inherit = ['fleet.fuel.request', 'fleet.bell.mixin']

    def write(self, vals):
        old_states = {request.id: request.state for request in self} if 'state' in vals else {}
        result = super().write(vals)
        for request in self:
            if old_states and old_states.get(request.id) != request.state:
                request._bell_on_state_change()
        return result

    def _bell_on_state_change(self):
        self.ensure_one()
        requester = self.requested_by.user_id
        vehicle = self.vehicle_id.display_name or '-'
        if self.state == 'submitted':
            self._bell_notify(
                self._bell_group_users(FLEET_MANAGER), _('Fuel request to approve'),
                _('%(ref)s from %(employee)s for %(vehicle)s needs your approval.',
                  ref=self.name, employee=self.requested_by.name, vehicle=vehicle),
                notif_type='warning', icon='fa-tint')
        elif self.state == 'approved':
            self._bell_notify(
                self._bell_group_users(FUEL_FILLER), _('Fuel request to fill'),
                _('%(ref)s for %(vehicle)s is approved and ready to be filled.', ref=self.name, vehicle=vehicle),
                notif_type='warning', icon='fa-tint')
            self._bell_notify(
                requester, _('Fuel request approved'),
                _('%(ref)s for %(vehicle)s was approved.', ref=self.name, vehicle=vehicle),
                notif_type='success', icon='fa-tint')
        elif self.state == 'filled':
            self._bell_notify(
                requester, _('Fuel filled'),
                _('%(ref)s for %(vehicle)s has been filled.', ref=self.name, vehicle=vehicle),
                notif_type='success', icon='fa-tint')
