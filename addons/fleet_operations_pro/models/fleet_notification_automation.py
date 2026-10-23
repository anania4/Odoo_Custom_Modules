# -*- coding: utf-8 -*-

from odoo import models, api, fields, _
from datetime import timedelta
from odoo.tools import date_utils
import logging

_logger = logging.getLogger(__name__)


class FleetNotificationAutomation(models.AbstractModel):
    _name = 'fleet.notification.automation'
    _description = 'Fleet Notification Automation'
    
    @api.model
    def _create_activity(self, record, activity_type_id, summary, note, date_deadline, user_id=None):
        """Helper method to create activity"""
        if not user_id:
            user_id = self.env.user.id
        
        # Check if similar activity already exists
        existing_activity = self.env['mail.activity'].search([
            ('res_model', '=', record._name),
            ('res_id', '=', record.id),
            ('summary', '=', summary),
            ('date_deadline', '=', date_deadline),
            ('activity_type_id', '=', activity_type_id),
        ], limit=1)
        
        if existing_activity:
            _logger.info(f"Activity already exists for {record._name} #{record.id}: {summary}")
            return existing_activity
        
        # Create new activity
        activity = self.env['mail.activity'].create({
            'res_model_id': self.env['ir.model']._get(record._name).id,
            'res_id': record.id,
            'activity_type_id': activity_type_id,
            'summary': summary,
            'note': note,
            'date_deadline': date_deadline,
            'user_id': user_id,
        })
        
        _logger.info(f"Created activity for {record._name} #{record.id}: {summary}")
        return activity
    
    @api.model
    def _process_certificate_expiry_notifications(self):
        """Process certificate expiry notifications"""
        _logger.info("Processing certificate expiry notifications...")
        
        configs = self.env['fleet.notification.config'].search([
            ('notification_type', '=', 'certificate_expiry'),
            ('active', '=', True)
        ])
        
        today = fields.Date.today()
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        
        for config in configs:
            target_date = today + timedelta(days=config.lead_days)
            
            # Find certificates expiring on target date
            certificates = self.env['fleet.vehicle.certificate'].search([
                ('expiry_date', '=', target_date),
                ('company_id', '=', config.company_id.id)
            ])
            
            for cert in certificates:
                summary = config.summary_template or f"Certificate {cert.certificate_type_id.name} expiring soon"
                note = config.note_template or f"The certificate {cert.certificate_type_id.name} for vehicle {cert.vehicle_id.license_plate} will expire on {cert.expiry_date}. Please renew it."
                
                summary = summary.format(
                    certificate_type=cert.certificate_type_id.name,
                    vehicle=cert.vehicle_id.license_plate,
                    expiry_date=cert.expiry_date
                )
                note = note.format(
                    certificate_type=cert.certificate_type_id.name,
                    vehicle=cert.vehicle_id.license_plate,
                    expiry_date=cert.expiry_date
                )
                
                user = config.user_id or self.env.user
                activity_type_id = config.activity_type_id.id if config.activity_type_id else activity_type.id
                
                self._create_activity(
                    cert.vehicle_id,
                    activity_type_id,
                    summary,
                    note,
                    today,
                    user.id
                )
        
        _logger.info("Certificate expiry notifications processed successfully")
    
    @api.model
    def _process_license_expiry_notifications(self):
        """Process driver license expiry notifications"""
        _logger.info("Processing driver license expiry notifications...")
        
        configs = self.env['fleet.notification.config'].search([
            ('notification_type', '=', 'license_expiry'),
            ('active', '=', True)
        ])
        
        today = fields.Date.today()
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        
        for config in configs:
            target_date = today + timedelta(days=config.lead_days)
            
            # Find drivers with licenses expiring on target date
            drivers = self.env['fleet.driver'].search([
                ('license_expiry_date', '=', target_date),
                ('company_id', '=', config.company_id.id)
            ])
            
            for driver in drivers:
                summary = config.summary_template or f"Driver license expiring soon for {driver.name}"
                note = config.note_template or f"The driver license for {driver.name} (License: {driver.license_number}) will expire on {driver.license_expiry_date}. Please renew it."
                
                summary = summary.format(
                    driver_name=driver.name,
                    license_number=driver.license_number,
                    expiry_date=driver.license_expiry_date
                )
                note = note.format(
                    driver_name=driver.name,
                    license_number=driver.license_number,
                    expiry_date=driver.license_expiry_date
                )
                
                user = config.user_id or self.env.user
                activity_type_id = config.activity_type_id.id if config.activity_type_id else activity_type.id
                
                self._create_activity(
                    driver,
                    activity_type_id,
                    summary,
                    note,
                    today,
                    user.id
                )
        
        _logger.info("Driver license expiry notifications processed successfully")
    
    @api.model
    def _process_rental_start_notifications(self):
        """Process rental contract start notifications"""
        _logger.info("Processing rental contract start notifications...")
        
        configs = self.env['fleet.notification.config'].search([
            ('notification_type', '=', 'rental_start'),
            ('active', '=', True)
        ])
        
        today = fields.Date.today()
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        
        for config in configs:
            target_date = today + timedelta(days=config.lead_days)
            
            # Find rentals starting on target date
            rentals = self.env['fleet.rental.contract'].search([
                ('start_date', '=', target_date),
                ('state', 'in', ['draft', 'confirmed']),
                ('company_id', '=', config.company_id.id)
            ])
            
            for rental in rentals:
                summary = config.summary_template or f"Rental contract {rental.name} starting soon"
                note = config.note_template or f"Rental contract {rental.name} for customer {rental.customer_id.name} is scheduled to start on {rental.start_date}. Please prepare the vehicle(s)."
                
                summary = summary.format(
                    contract_number=rental.name,
                    customer=rental.customer_id.name,
                    start_date=rental.start_date
                )
                note = note.format(
                    contract_number=rental.name,
                    customer=rental.customer_id.name,
                    start_date=rental.start_date,
                    vehicles=', '.join(rental.vehicle_ids.mapped('license_plate'))
                )
                
                user = config.user_id or self.env.user
                activity_type_id = config.activity_type_id.id if config.activity_type_id else activity_type.id
                
                self._create_activity(
                    rental,
                    activity_type_id,
                    summary,
                    note,
                    today,
                    user.id
                )
        
        _logger.info("Rental contract start notifications processed successfully")
    
    @api.model
    def _process_rental_end_notifications(self):
        """Process rental contract end notifications"""
        _logger.info("Processing rental contract end notifications...")
        
        configs = self.env['fleet.notification.config'].search([
            ('notification_type', '=', 'rental_end'),
            ('active', '=', True)
        ])
        
        today = fields.Date.today()
        activity_type = self.env.ref('mail.mail_activity_data_todo', raise_if_not_found=False)
        
        for config in configs:
            target_date = today + timedelta(days=config.lead_days)
            
            # Find rentals ending on target date
            rentals = self.env['fleet.rental.contract'].search([
                ('end_date', '=', target_date),
                ('state', '=', 'active'),
                ('company_id', '=', config.company_id.id)
            ])
            
            for rental in rentals:
                summary = config.summary_template or f"Rental contract {rental.name} ending soon"
                note = config.note_template or f"Rental contract {rental.name} for customer {rental.customer_id.name} is scheduled to end on {rental.end_date}. Please prepare for vehicle return."
                
                summary = summary.format(
                    contract_number=rental.name,
                    customer=rental.customer_id.name,
                    end_date=rental.end_date
                )
                note = note.format(
                    contract_number=rental.name,
                    customer=rental.customer_id.name,
                    end_date=rental.end_date,
                    vehicles=', '.join(rental.vehicle_ids.mapped('license_plate'))
                )
                
                user = config.user_id or self.env.user
                activity_type_id = config.activity_type_id.id if config.activity_type_id else activity_type.id
                
                self._create_activity(
                    rental,
                    activity_type_id,
                    summary,
                    note,
                    today,
                    user.id
                )
        
        _logger.info("Rental contract end notifications processed successfully")
    
    @api.model
    def run_all_notifications(self):
        """Run all notification processes (called by cron)"""
        _logger.info("==== Running Fleet Notification Automation ====")
        
        try:
            self._process_certificate_expiry_notifications()
        except Exception as e:
            _logger.error(f"Error processing certificate expiry notifications: {e}")
        
        try:
            self._process_license_expiry_notifications()
        except Exception as e:
            _logger.error(f"Error processing license expiry notifications: {e}")
        
        try:
            self._process_rental_start_notifications()
        except Exception as e:
            _logger.error(f"Error processing rental start notifications: {e}")
        
        try:
            self._process_rental_end_notifications()
        except Exception as e:
            _logger.error(f"Error processing rental end notifications: {e}")
        
        _logger.info("==== Fleet Notification Automation Completed ====")

