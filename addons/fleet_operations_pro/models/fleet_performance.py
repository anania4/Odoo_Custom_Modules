# -*- coding: utf-8 -*-

from odoo import models


class FleetPerformanceIndexes(models.AbstractModel):
    """
    Abstract model to create database indexes for performance optimization
    This runs once during module installation/upgrade
    """
    _name = 'fleet.performance.indexes'
    _description = 'Fleet Performance Optimization'
    
    def init(self):
        """Create database indexes on frequently queried fields"""
        cr = self.env.cr
        
        # Vehicle indexes
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_vehicle_status_idx 
            ON fleet_vehicle(status_id) 
            WHERE status_id IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_vehicle_category_idx 
            ON fleet_vehicle(category_id) 
            WHERE category_id IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_vehicle_company_idx 
            ON fleet_vehicle(company_id) 
            WHERE company_id IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_vehicle_license_plate_idx 
            ON fleet_vehicle(license_plate) 
            WHERE license_plate IS NOT NULL;
        """)
        
        # Fuel log indexes
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_fuel_log_date_idx 
            ON fleet_fuel_log(date DESC);
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_fuel_log_vehicle_idx 
            ON fleet_fuel_log(vehicle_id) 
            WHERE vehicle_id IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_fuel_log_driver_idx 
            ON fleet_fuel_log(driver_id) 
            WHERE driver_id IS NOT NULL;
        """)
        
        # Maintenance indexes
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_maintenance_date_idx 
            ON fleet_maintenance(date DESC);
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_maintenance_vehicle_idx 
            ON fleet_maintenance(vehicle_id) 
            WHERE vehicle_id IS NOT NULL;
        """)
        
        # Cost record indexes
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_cost_record_date_idx 
            ON fleet_cost_record(date DESC);
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_cost_record_vehicle_idx 
            ON fleet_cost_record(vehicle_id) 
            WHERE vehicle_id IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_cost_record_category_idx 
            ON fleet_cost_record(category_id) 
            WHERE category_id IS NOT NULL;
        """)
        
        # Certificate indexes
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_certificate_expiry_idx 
            ON fleet_vehicle_certificate(expiry_date) 
            WHERE expiry_date IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_certificate_vehicle_idx 
            ON fleet_vehicle_certificate(vehicle_id) 
            WHERE vehicle_id IS NOT NULL;
        """)
        
        # Rental contract indexes
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_rental_state_idx 
            ON fleet_rental_contract(state) 
            WHERE state IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_rental_dates_idx 
            ON fleet_rental_contract(start_date, end_date);
        """)
        
        # Trip indexes
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_trip_date_idx 
            ON fleet_trip(date DESC);
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_trip_vehicle_idx 
            ON fleet_trip(vehicle_id) 
            WHERE vehicle_id IS NOT NULL;
        """)
        
        # Driver indexes
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_driver_license_expiry_idx 
            ON fleet_driver(license_expiry_date) 
            WHERE license_expiry_date IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_driver_user_idx 
            ON fleet_driver(user_id) 
            WHERE user_id IS NOT NULL;
        """)
        
        # Composite indexes for common queries
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_fuel_log_vehicle_date_idx 
            ON fleet_fuel_log(vehicle_id, date DESC) 
            WHERE vehicle_id IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_maintenance_vehicle_date_idx 
            ON fleet_maintenance(vehicle_id, date DESC) 
            WHERE vehicle_id IS NOT NULL;
        """)
        
        cr.execute("""
            CREATE INDEX IF NOT EXISTS fleet_cost_vehicle_date_idx 
            ON fleet_cost_record(vehicle_id, date DESC) 
            WHERE vehicle_id IS NOT NULL;
        """)
