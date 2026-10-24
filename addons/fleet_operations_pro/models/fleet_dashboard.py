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
        """
        Get comprehensive dashboard data for fleet operations
        Returns a dictionary with all KPIs and chart data
        """
        try:
            company = self.env.company
            today = fields.Date.today()
            thirty_days_ago = today - timedelta(days=30)

            # Vehicle Statistics
            vehicles = self.env['fleet.vehicle'].search([('company_id', '=', company.id)])
            total_vehicles = len(vehicles)
            available_vehicles = len(vehicles.filtered(lambda v: v.state == 'available'))
            in_maintenance_vehicles = len(vehicles.filtered(lambda v: v.state == 'in_maintenance'))

            vehicle_by_status = {}
            vehicle_by_category = {}
            for vehicle in vehicles:
                status = vehicle.status_id.name if vehicle.status_id else 'Unknown'
                vehicle_by_status[status] = vehicle_by_status.get(status, 0) + 1

                category = vehicle.category_id.name if vehicle.category_id else 'Uncategorized'
                vehicle_by_category[category] = vehicle_by_category.get(category, 0) + 1

            # Fuel Statistics (KPI card + trend)
            fuel_logs = self.env['fleet.fuel.log'].search([
                ('company_id', '=', company.id),
                ('date', '>=', thirty_days_ago)
            ])
            total_fuel_cost = sum(fuel_logs.mapped('total_cost'))
            total_fuel_quantity = sum(fuel_logs.mapped('quantity'))

            # Cost Statistics (fuel + maintenance + tolls in the last 30 days)
            maintenances = self.env['fleet.maintenance'].search([
                ('company_id', '=', company.id),
                ('date', '>=', thirty_days_ago)
            ])
            total_maintenance_cost = sum(maintenances.mapped('cost'))

            tolls = self.env['fleet.toll.record'].search([
                ('company_id', '=', company.id),
                ('date', '>=', thirty_days_ago)
            ])
            total_toll_cost = sum(tolls.mapped('amount'))

            cost_map = {
                'Fuel': total_fuel_cost,
                'Maintenance': total_maintenance_cost,
                'Tolls': total_toll_cost,
            }
            total_costs = sum(cost_map.values())
            cost_by_category = [{'name': k, 'value': v} for k, v in cost_map.items() if v > 0]

            # Fleet Requests Statistics
            requests_model = self.env['fleet.request']
            total_requests = requests_model.search_count([])
            draft_requests = requests_model.search_count([('state', '=', 'draft')])
            open_requests = requests_model.search_count([
                ('state', 'in', ('submitted', 'dept_approved', 'fleet_approved'))
            ])
            assigned_requests = requests_model.search_count([('state', '=', 'assigned')])
            rejected_requests = requests_model.search_count([('state', '=', 'rejected')])

            # Driver Statistics
            drivers = self.env['fleet.driver'].search([('company_id', '=', company.id)])
            total_drivers = len(drivers)
            active_drivers = len(drivers.filtered(lambda d: d.employment_status == 'active'))

            # Driver Assignments
            assignment_model = self.env['fleet.driver.assignment']
            if 'company_id' in assignment_model._fields:
                assignments = assignment_model.search([('company_id', '=', company.id)])
            else:
                assignments = assignment_model.search([])
            active_assignments = assignments.filtered(lambda a: a.is_active)

            # Trip Statistics
            trips = self.env['fleet.trip'].search([
                ('company_id', '=', company.id),
                ('date', '>=', thirty_days_ago)
            ])
            total_distance = sum(trips.mapped('distance'))
            total_trips = len(trips)

            # Top Cost Vehicles (last 30 days: maintenance + fuel + tolls)
            vehicle_costs = {}
            for maint in maintenances:
                if maint.vehicle_id:
                    vehicle_costs[maint.vehicle_id.name] = \
                        vehicle_costs.get(maint.vehicle_id.name, 0) + maint.cost
            for log in fuel_logs:
                if log.vehicle_id:
                    vehicle_costs[log.vehicle_id.name] = \
                        vehicle_costs.get(log.vehicle_id.name, 0) + log.total_cost
            for toll_rec in tolls:
                if toll_rec.vehicle_id:
                    vehicle_costs[toll_rec.vehicle_id.name] = \
                        vehicle_costs.get(toll_rec.vehicle_id.name, 0) + toll_rec.amount

            top_cost_vehicles = sorted(vehicle_costs.items(), key=lambda x: x[1], reverse=True)[:5]

            # Calculate KPIs
            avg_cost_per_km = (total_costs / total_distance) if total_distance > 0 else 0
            avg_fuel_efficiency = (total_distance / total_fuel_quantity) if total_fuel_quantity > 0 else 0
            vehicle_utilization = (len(active_assignments) / total_vehicles * 100) if total_vehicles > 0 else 0

            # Fuel consumption trend (last 6 months)
            fuel_trend = []
            for i in range(6, 0, -1):
                month_start = (today.replace(day=1) - timedelta(days=i * 30)).replace(day=1)
                month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)

                month_fuel = self.env['fleet.fuel.log'].search([
                    ('company_id', '=', company.id),
                    ('date', '>=', month_start),
                    ('date', '<=', month_end)
                ])

                fuel_trend.append({
                    'month': month_start.strftime('%B %Y'),
                    'quantity': sum(month_fuel.mapped('quantity')),
                    'cost': sum(month_fuel.mapped('total_cost'))
                })

            # Upcoming Maintenance
            ninety_days_ahead = today + timedelta(days=90)
            upcoming_maintenance = self.env['fleet.maintenance.schedule'].search([
                ('company_id', '=', company.id),
                ('next_maintenance_date', '<=', ninety_days_ahead),
                ('next_maintenance_date', '>=', today),
                ('active', '=', True)
            ], order='next_maintenance_date asc', limit=5)

            # Insurance Alerts
            insurance_model = self.env['fleet.insurance']
            expiring_insurances = insurance_model.search([
                ('active', '=', True),
                ('end_date', '<=', today + timedelta(days=30)),
                ('end_date', '>=', today),
            ], order='end_date asc')
            expired_insurances = insurance_model.search([
                ('active', '=', True),
                ('end_date', '<', today),
            ])
            insurance_details = [{
                'vehicle': policy.vehicle_id.name,
                'vehicle_id': policy.vehicle_id.id,
                'policy_number': policy.policy_number,
                'insurance_company': policy.insurance_company,
                'end_date': policy.end_date.strftime('%Y-%m-%d') if policy.end_date else '',
                'days_left': (policy.end_date - today).days if policy.end_date else 0,
            } for policy in expiring_insurances[:5]]

            # Rental Contract Expiries (active/confirmed contracts ending within 30 days and overdue ones)
            contract_model = self.env['fleet.rental.contract']
            expiring_contracts = contract_model.search([
                ('active', '=', True),
                ('state', 'in', ('confirmed', 'active')),
                ('end_date', '<=', today + timedelta(days=30)),
                ('end_date', '>=', today),
            ], order='end_date asc')
            expired_contracts = contract_model.search([
                ('active', '=', True),
                ('state', '=', 'active'),
                ('end_date', '<', today),
            ])
            contract_details = [{
                'contract': contract.name,
                'contract_id': contract.id,
                'customer': contract.customer_id.name,
                'end_date': contract.end_date.strftime('%Y-%m-%d') if contract.end_date else '',
                'days_left': (contract.end_date - today).days if contract.end_date else 0,
            } for contract in (expiring_contracts + expired_contracts)[:5]]

            # Top Performing Drivers (ranked by trip activity in the last 30 days)
            driver_trips = {}
            for trip in trips:
                if trip.driver_id:
                    driver_trips[trip.driver_id.id] = driver_trips.get(trip.driver_id.id, 0) + 1
            top_driver_ids = sorted(driver_trips.items(), key=lambda x: x[1], reverse=True)[:5]
            top_drivers = self.env['fleet.driver'].browse([d for d, _ in top_driver_ids])

            return {
                'kpis': {
                    'total_vehicles': total_vehicles,
                    'available_vehicles': available_vehicles,
                    'in_service_vehicles': in_maintenance_vehicles,
                    'total_drivers': total_drivers,
                    'active_drivers': active_drivers,
                    'active_assignments': len(active_assignments),
                    'total_costs': total_costs,
                    'total_fuel_cost': total_fuel_cost,
                    'total_fuel_quantity': total_fuel_quantity,
                    'avg_cost_per_km': avg_cost_per_km,
                    'avg_fuel_efficiency': avg_fuel_efficiency,
                    'vehicle_utilization': vehicle_utilization,
                    'total_distance': total_distance,
                    'total_trips': total_trips,
                    'total_maintenance_cost': total_maintenance_cost,
                    'total_requests': total_requests,
                    'draft_requests': draft_requests,
                    'open_requests': open_requests,
                    'assigned_requests': assigned_requests,
                    'rejected_requests': rejected_requests,
                },
                'charts': {
                    'vehicle_by_status': [{'name': k, 'value': v} for k, v in vehicle_by_status.items()],
                    'vehicle_by_category': [{'name': k, 'value': v} for k, v in vehicle_by_category.items()],
                    'cost_by_category': cost_by_category,
                    'top_cost_vehicles': [{'name': k, 'value': v} for k, v in top_cost_vehicles],
                    'fuel_trend': fuel_trend,
                    'top_drivers': [{
                        'name': driver.name,
                        'safety_score': driver_trips.get(driver.id, 0),
                        'license_number': driver.license_number,
                        'image': driver.image if driver.image else False
                    } for driver in top_drivers],
                },
                'alerts': {
                    'expired_insurances': len(expired_insurances),
                    'expiring_insurances': len(expiring_insurances),
                    'insurance_details': insurance_details,
                    'expired_contracts': len(expired_contracts),
                    'expiring_contracts': len(expiring_contracts),
                    'contract_details': contract_details,
                    'upcoming_maintenance': [{
                        'vehicle': maint.vehicle_id.name if maint.vehicle_id else 'All Vehicles',
                        'maintenance_type': maint.maintenance_type_id.name,
                        'due_date': maint.next_maintenance_date.strftime('%Y-%m-%d') if maint.next_maintenance_date else '',
                        'odometer_due': maint.next_maintenance_odometer if maint.next_maintenance_odometer else 0
                    } for maint in upcoming_maintenance],
                }
            }
        except Exception as e:
            _logger.error(f"Error in get_dashboard_data: {str(e)}", exc_info=True)
            # Return empty/default data structure on error
            return {
                'kpis': {
                    'total_vehicles': 0,
                    'available_vehicles': 0,
                    'in_service_vehicles': 0,
                    'total_drivers': 0,
                    'active_drivers': 0,
                    'active_assignments': 0,
                    'total_costs': 0,
                    'total_fuel_cost': 0,
                    'total_fuel_quantity': 0,
                    'avg_cost_per_km': 0,
                    'avg_fuel_efficiency': 0,
                    'vehicle_utilization': 0,
                    'total_distance': 0,
                    'total_trips': 0,
                    'total_maintenance_cost': 0,
                    'total_requests': 0,
                    'draft_requests': 0,
                    'open_requests': 0,
                    'assigned_requests': 0,
                    'rejected_requests': 0,
                },
                'charts': {
                    'vehicle_by_status': [],
                    'vehicle_by_category': [],
                    'cost_by_category': [],
                    'top_cost_vehicles': [],
                    'fuel_trend': [],
                    'top_drivers': [],
                },
                'alerts': {
                    'expired_insurances': 0,
                    'expiring_insurances': 0,
                    'insurance_details': [],
                    'expired_contracts': 0,
                    'expiring_contracts': 0,
                    'contract_details': [],
                    'upcoming_maintenance': [],
                }
            }
