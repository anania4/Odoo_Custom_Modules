# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)


class FleetDashboard(models.Model):
    _name = 'fleet.dashboard'
    _description = 'Fleet Dashboard'

    @api.model
    def get_dashboard_data(self):
        try:
            company = self.env.company
            today = fields.Date.today()
            thirty_days_ago = today - timedelta(days=30)

            vehicles = self.env['fleet.vehicle'].search([('company_id', '=', company.id)])
            total_vehicles = len(vehicles)
            available_vehicles = len(vehicles.filtered(lambda v: v.state == 'available'))
            in_maintenance_vehicles = len(vehicles.filtered(lambda v: v.state == 'in_maintenance'))

            vehicle_by_status = {}
            vehicle_by_category = {}
            for vehicle in vehicles:
                plate = vehicle.license_plate or vehicle.name
                status = vehicle.status_id.name if vehicle.status_id else 'Unknown'
                category = vehicle.category_id.name if vehicle.category_id else 'Uncategorized'

                status_entry = vehicle_by_status.setdefault(
                    status, {'name': status, 'value': 0, 'plates': []}
                )
                status_entry['value'] += 1
                status_entry['plates'].append(plate)

                category_entry = vehicle_by_category.setdefault(
                    category, {'name': category, 'value': 0, 'plates': []}
                )
                category_entry['value'] += 1
                category_entry['plates'].append(plate)

            fuel_logs = self.env['fleet.fuel.log'].search([
                ('company_id', '=', company.id),
                ('date', '>=', thirty_days_ago),
            ])
            total_fuel_cost = sum(fuel_logs.mapped('total_cost'))
            total_fuel_quantity = sum(fuel_logs.mapped('quantity'))

            fuel_cost_by_vehicle = {}
            for log in fuel_logs:
                vehicle = log.vehicle_id
                if not vehicle:
                    continue
                entry = fuel_cost_by_vehicle.setdefault(vehicle.id, {
                    'name': vehicle.license_plate or vehicle.name,
                    'vehicle': vehicle.name,
                    'value': 0.0,
                })
                entry['value'] += log.total_cost

            # Services
            service_model = self.env['fleet.service']
            service_domain = [
                ('company_id', '=', company.id),
                ('active', '=', True),
            ]
            total_services = service_model.search_count(service_domain)
            upcoming_services_count = service_model.search_count(
                service_domain + [('date', '>=', today)]
            )
            upcoming_service_records = service_model.search(
                service_domain + [('date', '>=', today)],
                order='date asc, id asc',
                limit=5,
            )
            upcoming_service_details = [{
                'vehicle': service.vehicle_id.name,
                'plate': service.vehicle_id.license_plate or '',
                'service': service.service_type_id.name,
                'date': service.date.strftime('%Y-%m-%d') if service.date else '',
                'days_until': (service.date - today).days if service.date else 0,
            } for service in upcoming_service_records]

            # Fleet Requests Statistics (provided by the optional Fleet Requests module)
            try:
                requests_model = self.env['fleet.request']
            except KeyError:
                requests_model = None

            if requests_model:
                total_requests = requests_model.search_count([])
                draft_requests = requests_model.search_count([('state', '=', 'draft')])
                open_requests = requests_model.search_count([
                    ('state', 'in', ('submitted', 'dept_approved', 'fleet_approved'))
                ])
                assigned_requests = requests_model.search_count([('state', '=', 'assigned')])
                rejected_requests = requests_model.search_count([('state', '=', 'rejected')])
            else:
                total_requests = draft_requests = open_requests = 0
                assigned_requests = rejected_requests = 0

            # Contract Statistics
            contract_model = self.env['fleet.contract']
            running_contracts = contract_model.search_count([
                ('company_id', '=', company.id),
                ('active', '=', True),
                ('state', '=', 'running'),
            ])
            total_contracts = contract_model.search_count([
                ('company_id', '=', company.id),
                ('active', '=', True),
            ])

            expiring_contracts = contract_model.search([
                ('company_id', '=', company.id),
                ('active', '=', True),
                ('state', '=', 'running'),
                ('end_date', '>=', today),
                ('end_date', '<=', today + timedelta(days=30)),
            ], order='end_date asc')
            expired_contracts = contract_model.search([
                ('company_id', '=', company.id),
                ('active', '=', True),
                ('state', '=', 'running'),
                ('end_date', '<', today),
                ('end_date', '>=', today - timedelta(days=90)),
            ], order='end_date desc')

            contract_details = [{
                'contract': contract.name,
                'contract_id': contract.id,
                'vehicle': contract.vehicle_id.name,
                'plate': contract.vehicle_id.license_plate or '',
                'contract_type': dict(contract._fields['contract_type'].selection).get(
                    contract.contract_type, ''
                ),
                'provider': contract.partner_id.name or '',
                'end_date': contract.end_date.strftime('%Y-%m-%d') if contract.end_date else '',
                'days_left': (contract.end_date - today).days if contract.end_date else 0,
            } for contract in (expired_contracts + expiring_contracts)[:5]]

            return {
                'kpis': {
                    'total_vehicles': total_vehicles,
                    'available_vehicles': available_vehicles,
                    'in_service_vehicles': in_maintenance_vehicles,
                    'running_contracts': running_contracts,
                    'total_contracts': total_contracts,
                    'total_fuel_cost': total_fuel_cost,
                    'total_fuel_quantity': total_fuel_quantity,
                    'total_services': total_services,
                    'upcoming_services': upcoming_services_count,
                    'total_requests': total_requests,
                    'draft_requests': draft_requests,
                    'open_requests': open_requests,
                    'assigned_requests': assigned_requests,
                    'rejected_requests': rejected_requests,
                },
                'currency': {
                    'symbol': company.currency_id.symbol or '$',
                    'position': company.currency_id.position or 'before',
                    'decimal_places': company.currency_id.decimal_places or 2,
                },
                'charts': {
                    'vehicle_by_status': list(vehicle_by_status.values()),
                    'vehicle_by_category': list(vehicle_by_category.values()),
                    'fuel_cost_by_vehicle': sorted(
                        fuel_cost_by_vehicle.values(),
                        key=lambda item: item['value'],
                        reverse=True,
                    ),
                },
                'alerts': {
                    'expired_contracts': len(expired_contracts),
                    'expiring_contracts': len(expiring_contracts),
                    'contract_details': contract_details,
                    'upcoming_services': upcoming_service_details,
                },
            }
        except Exception as e:
            _logger.error(f"Error in get_dashboard_data: {str(e)}", exc_info=True)
            return {
                'kpis': {
                    'total_vehicles': 0,
                    'available_vehicles': 0,
                    'in_service_vehicles': 0,
                    'running_contracts': 0,
                    'total_contracts': 0,
                    'total_fuel_cost': 0,
                    'total_fuel_quantity': 0,
                    'total_services': 0,
                    'upcoming_services': 0,
                    'total_requests': 0,
                    'draft_requests': 0,
                    'open_requests': 0,
                    'assigned_requests': 0,
                    'rejected_requests': 0,
                },
                'currency': {
                    'symbol': '$',
                    'position': 'before',
                    'decimal_places': 2,
                },
                'charts': {
                    'vehicle_by_status': [],
                    'vehicle_by_category': [],
                    'fuel_cost_by_vehicle': [],
                },
                'alerts': {
                    'expired_contracts': 0,
                    'expiring_contracts': 0,
                    'contract_details': [],
                    'upcoming_services': [],
                },
            }
