# -*- coding: utf-8 -*-

from odoo import _, api, fields, models


class FleetDriverAssignment(models.Model):
    _name = 'fleet.driver.assignment'
    _inherit = ['fleet.driver.assignment', 'fleet.bell.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        assignments = super().create(vals_list)
        for assignment in assignments:
            vehicle = assignment.vehicle_id.display_name
            self_driver = assignment.employee_id
            assignment._bell_notify(
                self_driver.user_id, _('Vehicle delegated to you'),
                _('%(vehicle)s is delegated to you from %(date)s.', vehicle=vehicle, date=assignment.date_start),
                notif_type='success', icon='fa-car')
            assignment._bell_notify(
                assignment.vehicle_id.manager_id, _('Vehicle delegated'),
                _('%(vehicle)s is now delegated to %(driver)s.', vehicle=vehicle, driver=self_driver.name),
                icon='fa-car')
        return assignments


class FleetContract(models.Model):
    _name = 'fleet.contract'
    _inherit = ['fleet.contract', 'fleet.bell.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        contracts = super().create(vals_list)
        for contract in contracts:
            contract._bell_responsible_assigned()
        return contracts

    def write(self, vals):
        old_users = {c.id: c.user_id for c in self} if 'user_id' in vals else {}
        result = super().write(vals)
        for contract in self:
            if old_users and old_users.get(contract.id) != contract.user_id:
                contract._bell_responsible_assigned()
        return result

    def _bell_responsible_assigned(self):
        self._bell_notify(
            self.user_id, _('Vehicle Agreement assigned to you'),
            _('You are responsible for vehicle agreement %(ref)s (%(type)s) of %(vehicle)s, ending %(end)s.',
              ref=self.name, type=self.contract_type_id.name or '-',
              vehicle=self.vehicle_id.display_name, end=self.end_date),
            icon='fa-file-text-o')

    @api.model
    def _cron_check_contracts(self):
        """Also ring the responsible user: reminder sent, contract expired"""
        not_reminded = self.search([('state', '=', 'running'), ('reminder_sent', '=', False)])
        running = self.search([('state', '=', 'running')])
        result = super()._cron_check_contracts()

        for contract in not_reminded.filtered(lambda c: c.reminder_sent):
            contract._bell_notify(
                contract.user_id, _('Vehicle Agreement expiring soon'),
                _('%(ref)s (%(type)s) of %(vehicle)s ends on %(end)s.',
                  ref=contract.name, type=contract.contract_type_id.name or '-',
                  vehicle=contract.vehicle_id.display_name, end=contract.end_date),
                notif_type='warning', icon='fa-file-text-o')
        for contract in running.filtered(lambda c: c.state == 'expired'):
            contract._bell_notify(
                contract.user_id, _('Vehicle Agreement expired'),
                _('%(ref)s (%(type)s) of %(vehicle)s expired on %(end)s.',
                  ref=contract.name, type=contract.contract_type_id.name or '-',
                  vehicle=contract.vehicle_id.display_name, end=contract.end_date),
                notif_type='danger', icon='fa-file-text-o')
        return result


class FleetService(models.Model):
    _name = 'fleet.service'
    _inherit = ['fleet.service', 'fleet.bell.mixin']

    @api.model_create_multi
    def create(self, vals_list):
        services = super().create(vals_list)
        for service in services:
            service._bell_responsible_assigned()
        return services

    def write(self, vals):
        old_users = {s.id: s.user_id for s in self} if 'user_id' in vals else {}
        result = super().write(vals)
        for service in self:
            if old_users and old_users.get(service.id) != service.user_id:
                service._bell_responsible_assigned()
        return result

    def _bell_responsible_assigned(self):
        self._bell_notify(
            self.user_id, _('Service assigned to you'),
            _('You are responsible for service %(ref)s (%(type)s) on %(vehicle)s.',
              ref=self.name, type=self.service_type_id.name or '-', vehicle=self.vehicle_id.display_name),
            icon='fa-wrench')
