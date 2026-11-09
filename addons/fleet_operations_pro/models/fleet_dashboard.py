# -*- coding: utf-8 -*-

from odoo import models, fields, api
from datetime import timedelta
import logging

_logger = logging.getLogger(__name__)



class FleetDashboard(models.Model):
    _name = 'fleet.dashboard'
    _description = 'Fleet Dashboard'

    @api.model
    def _can_read(self, model_name):
        """True if the optional model is installed and the current user may read it"""
        return model_name in self.env and self.env[model_name].has_access('read')

    @api.model
    def _get_vehicle_board(self, vehicles):
        """Small live cards: plate, car name, delegated driver and a status dot.

        Green dot = Active, red dot = In Use, grey = any other status.
        In Use vehicles first, then Active, then the rest.
        """
        dot_by_code = {'active': 'active', 'in use': 'in_use', 'in_use': 'in_use'}
        order = {'in_use': 0, 'active': 1, 'other': 2}
        cards = []
        for vehicle in vehicles:
            dot = dot_by_code.get((vehicle.status_code or '').strip().lower(), 'other')
            cards.append({
                'id': vehicle.id,
                'plate': vehicle.license_plate or '',
                'name': vehicle.name or '',
                'driver': vehicle.driver_id.name or '',
                'status': vehicle.status_id.name or '',
                'dot': dot,
            })
        cards.sort(key=lambda c: (order[c['dot']], c['plate']))
        return {
            'cards': cards[:60],
            'total': len(cards),
            'active': sum(1 for c in cards if c['dot'] == 'active'),
            'in_use': sum(1 for c in cards if c['dot'] == 'in_use'),
        }

    @api.model
    def _get_needs_action(self, today, expired, expiring, due_by_km):
        """One list of things to act on, most urgent first (lowest 'urgency')."""
        items = []
        for contract in expired:
            days = (today - contract.end_date).days
            items.append({
                'key': f'expired-{contract.id}',
                'kind': 'Vehicle Agreement expired',
                'title': f"{contract.name} · {contract.vehicle_id.display_name} · {contract.contract_type_id.name or ''}",
                'detail': f"Ended {contract.end_date}",
                'badge': f"Expired {days} day{'s' if days != 1 else ''} ago",
                'badge_class': 'danger',
                'res_model': 'fleet.contract',
                'res_id': contract.id,
                'urgency': -1000 - days,
            })
        for contract in expiring - expired:
            days = contract.days_until_expiry
            items.append({
                'key': f'expiring-{contract.id}',
                'kind': 'Vehicle Agreement expiring',
                'title': f"{contract.name} · {contract.vehicle_id.display_name} · {contract.contract_type_id.name or ''}",
                'detail': f"Ends {contract.end_date}",
                'badge': 'Ends today' if days == 0 else f"Ends in {days} day{'s' if days != 1 else ''}",
                'badge_class': 'warning',
                'res_model': 'fleet.contract',
                'res_id': contract.id,
                'urgency': days,
            })
        for service in due_by_km:
            vehicle = service.vehicle_id
            over = vehicle.odometer - service.next_service_odometer
            items.append({
                'key': f'km-{service.id}',
                'kind': 'Service due by km',
                'title': f"{vehicle.display_name} · {service.service_type_id.name}",
                'detail': f"at {vehicle.odometer:,.0f} km, due at {service.next_service_odometer:,.0f} km",
                'badge': f"Over by {over:,.0f} km" if over else 'Due now',
                'badge_class': 'warning',
                'res_model': 'fleet.vehicle',
                'res_id': vehicle.id,
                'urgency': -int(over // 100),
            })
        items.sort(key=lambda item: item['urgency'])
        return items

    @api.model
    def _get_card_data(self, company, today):
        """Top row: Active Vehicles, Services, Vehicle Agreements, Pending Fleet Requests"""
        # 1. Active vehicles out of the total (+ in maintenance)
        vehicles = self.env['fleet.vehicle'].search([('company_id', 'in', self.env.companies.ids)])
        active = vehicles.filtered(lambda v: v.status_code == 'active')
        available = vehicles.filtered(lambda v: v.status_code == 'available')
        in_maintenance = vehicles.filtered(lambda v: v.status_code == 'in_maintenance')

        # 2. Services: open ones, plus vehicles that reached the km of their next service
        Service = self.env['fleet.service']
        open_services = Service.search([
            ('company_id', 'in', self.env.companies.ids),
            ('state', 'in', ('new', 'running')),
        ])
        done_services = Service.search([
            ('company_id', 'in', self.env.companies.ids),
            ('state', '=', 'done'),
            ('next_service_odometer', '>', 0),
        ], order='end_date desc, odometer desc, id desc')
        latest_by_vehicle_type = {}
        for service in done_services:
            latest_by_vehicle_type.setdefault((service.vehicle_id.id, service.service_type_id.id), service)
        open_keys = {(s.vehicle_id.id, s.service_type_id.id) for s in open_services}
        due_by_km = [
            s for key, s in latest_by_vehicle_type.items()
            if key not in open_keys and s.vehicle_id.odometer >= s.next_service_odometer
        ]

        # 3. Vehicle Agreements needing attention: expiring or expired.
        #    Expired = past the end date and not closed yet: still running, or already set to
        #    Expired by the daily check (they stay here until renewed or closed).
        agreements = self.env['fleet.contract'].search([
            ('company_id', 'in', self.env.companies.ids),
            ('state', 'in', ('running', 'expired')),
        ])
        running = agreements.filtered(lambda c: c.state == 'running')
        expired = agreements.filtered(
            lambda c: c.state == 'expired' or (c.end_date and c.end_date < today))
        expiring = running.filtered(lambda c: c.expiring_alert)
        attention = expired | expiring

        # 4. Pending fleet requests (optional Fleet Requests module)
        pending = {'submitted': 0, 'dept_approved': 0, 'fleet_approved': 0}
        if self._can_read('fleet.request'):
            for state, count in self.env['fleet.request']._read_group(
                    [('state', 'in', list(pending)), ('company_id', 'in', self.env.companies.ids)],
                    ['state'], ['__count']):
                pending[state] = count

        # 4b. Pending fuel requests: waiting for approval or for filling
        fuel_pending = {'submitted': 0, 'approved': 0}
        if self._can_read('fleet.fuel.request'):
            for state, count in self.env['fleet.fuel.request']._read_group(
                    [('state', 'in', list(fuel_pending)), ('company_id', 'in', self.env.companies.ids)],
                    ['state'], ['__count']):
                fuel_pending[state] = count

        needs_action = self._get_needs_action(today, expired, expiring, due_by_km)

        return {
            'needs_action': needs_action[:10],
            'needs_action_total': len(needs_action),
            'available_list': [{
                'id': v.id,
                'plate': v.license_plate,
                'name': v.name,
                'driver': v.driver_id.name or '',
            } for v in active.sorted('license_plate')[:50]],  # Active vehicles (table on the dashboard)
            'status_list': [{
                'id': v.id,
                'plate': v.license_plate,
                'name': v.name,
                'status': v.status_id.name or '',
                'color': v.status_id.color or 0,
            } for v in vehicles.sorted(lambda v: (v.status_id.sequence, v.license_plate or ''))[:50]],
            'board': self._get_vehicle_board(vehicles),
            'vehicles': {
                'active': len(active),
                'available': len(available),
                'total': len(vehicles),
                'in_maintenance': len(in_maintenance),
            },
            'services': {
                'open': len(open_services),
                'running': len(open_services.filtered(lambda s: s.state == 'running')),
                'due_by_km': len({s.vehicle_id.id for s in due_by_km}),  # vehicles, matches the list it opens
                'due_by_km_vehicle_ids': list({s.vehicle_id.id for s in due_by_km}),
            },
            'contracts': {
                'attention': len(attention),
                'attention_ids': attention.ids,
                'expiring': len(expiring),
                'expired': len(expired),
                'running': len(running),
            },
            'requests': {
                'installed': 'fleet.request' in self.env,
                'allowed': self._can_read('fleet.request'),
                'pending': sum(pending.values()) + sum(fuel_pending.values()),
                'fleet_pending': sum(pending.values()),
                'awaiting_department': pending['submitted'],
                'awaiting_fleet_manager': pending['dept_approved'],
                'awaiting_assignment': pending['fleet_approved'],
                'fuel_pending': sum(fuel_pending.values()),
                'fuel_awaiting_approval': fuel_pending['submitted'],
                'fuel_awaiting_filling': fuel_pending['approved'],
            },
        }

    @api.model
    def get_dashboard_data(self):
        try:
            company = self.env.company
            today = fields.Date.today()
            thirty_days_ago = today - timedelta(days=30)

            vehicles = self.env['fleet.vehicle'].search([('company_id', 'in', self.env.companies.ids)])
            total_vehicles = len(vehicles)
            available_vehicles = len(vehicles.filtered(lambda v: v.status_code == 'available'))
            in_maintenance_vehicles = len(vehicles.filtered(lambda v: v.status_code == 'in_maintenance'))

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
                ('company_id', 'in', self.env.companies.ids),
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
                    'vehicle': vehicle.display_name,
                    'value': 0.0,
                })
                entry['value'] += log.total_cost

            # Services
            service_model = self.env['fleet.service']
            service_domain = [
                ('company_id', 'in', self.env.companies.ids),
                ('active', '=', True),
            ]
            total_services = service_model.search_count(service_domain)
            upcoming_services_count = service_model.search_count(
                service_domain + [('date', '>=', today), ('state', 'in', ('new', 'running'))]
            )
            upcoming_service_records = service_model.search(
                service_domain + [('date', '>=', today), ('state', 'in', ('new', 'running'))],
                order='date asc, id asc',
                limit=5,
            )
            upcoming_service_details = [{
                'vehicle': service.vehicle_id.display_name,
                'plate': service.vehicle_id.license_plate or '',
                'service': service.service_type_id.name,
                'date': service.date.strftime('%Y-%m-%d') if service.date else '',
                'days_until': (service.date - today).days if service.date else 0,
            } for service in upcoming_service_records]

            # Fleet Requests Statistics (provided by the optional Fleet Requests module)
            requests_model = self.env['fleet.request'] if self._can_read('fleet.request') else None

            if requests_model is not None:
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

            # Vehicle Agreement Statistics
            contract_model = self.env['fleet.contract']
            running_contracts = contract_model.search_count([
                ('company_id', 'in', self.env.companies.ids),
                ('active', '=', True),
                ('state', '=', 'running'),
            ])
            total_contracts = contract_model.search_count([
                ('company_id', 'in', self.env.companies.ids),
                ('active', '=', True),
            ])

            expiring_contracts = contract_model.search([
                ('company_id', 'in', self.env.companies.ids),
                ('active', '=', True),
                ('state', '=', 'running'),
                ('end_date', '>=', today),
                ('end_date', '<=', today + timedelta(days=30)),
            ], order='end_date asc')
            expired_contracts = contract_model.search([
                ('company_id', 'in', self.env.companies.ids),
                ('active', '=', True),
                ('state', '=', 'running'),
                ('end_date', '<', today),
                ('end_date', '>=', today - timedelta(days=90)),
            ], order='end_date desc')

            contract_details = [{
                'contract': contract.name,
                'contract_id': contract.id,
                'vehicle': contract.vehicle_id.display_name,
                'plate': contract.vehicle_id.license_plate or '',
                'contract_type': contract.contract_type_id.name or '',
                'provider': contract.partner_id.name or '',
                'end_date': contract.end_date.strftime('%Y-%m-%d') if contract.end_date else '',
                'days_left': (contract.end_date - today).days if contract.end_date else 0,
            } for contract in (expired_contracts + expiring_contracts)[:5]]

            return {
                'cards': self._get_card_data(company, today),
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
        except Exception:
            _logger.exception("Error in get_dashboard_data")
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
