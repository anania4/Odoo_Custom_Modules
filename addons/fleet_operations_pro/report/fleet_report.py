# -*- coding: utf-8 -*-

from odoo import models, fields, api, tools


class FleetVehicleReport(models.Model):
    _name = 'fleet.vehicle.report'
    _description = 'Fleet Vehicle Analysis Report'
    _auto = False
    _rec_name = 'vehicle_id'
    
    vehicle_id = fields.Many2one('fleet.vehicle', string='Vehicle', readonly=True)
    category_id = fields.Many2one('fleet.vehicle.category', string='Category', readonly=True)
    status_id = fields.Many2one('fleet.vehicle.status', string='Status', readonly=True)
    company_id = fields.Many2one('res.company', string='Company', readonly=True)
    
    # Fuel Cost Metrics
    fuel_cost = fields.Monetary(string='Fuel Cost', readonly=True, currency_field='currency_id')
    
    # Distance Metrics
    total_distance = fields.Float(string='Total Distance (km)', readonly=True)
    
    # Fuel Metrics
    fuel_quantity = fields.Float(string='Fuel Quantity (L)', readonly=True)
    fuel_efficiency = fields.Float(string='Fuel Efficiency (km/L)', readonly=True)
    
    # Trip Metrics
    trip_count = fields.Integer(string='Total Trips', readonly=True)
    
    currency_id = fields.Many2one('res.currency', string='Currency', readonly=True)
    
    def init(self):
        tools.drop_view_if_exists(self.env.cr, 'fleet_vehicle_report')
        self.env.cr.execute("""
            CREATE OR REPLACE VIEW fleet_vehicle_report AS (
                SELECT
                    v.id as id,
                    v.id as vehicle_id,
                    v.category_id as category_id,
                    v.status_id as status_id,
                    v.company_id as company_id,
                    v.currency_id as currency_id,
                    
                    -- Fuel metrics
                    COALESCE(SUM(f.total_cost), 0) as fuel_cost,
                    COALESCE(SUM(f.quantity), 0) as fuel_quantity,
                    CASE 
                        WHEN SUM(f.quantity) > 0 THEN SUM(t.distance) / SUM(f.quantity)
                        ELSE 0
                    END as fuel_efficiency,
                    
                    -- Distance metrics
                    COALESCE(SUM(t.distance), 0) as total_distance,
                    
                    -- Trip metrics
                    COUNT(DISTINCT t.id) as trip_count
                    
                FROM fleet_vehicle v
                LEFT JOIN fleet_fuel_log f ON f.vehicle_id = v.id
                LEFT JOIN fleet_trip t ON t.vehicle_id = v.id
                GROUP BY v.id, v.category_id, v.status_id, v.company_id, v.currency_id
            )
        """)
