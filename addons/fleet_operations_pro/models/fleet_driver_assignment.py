# -*- coding: utf-8 -*-

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class FleetDriverAssignment(models.Model):
    _name = 'fleet.driver.assignment'
    _description = 'Driver Vehicle Assignment'
    _order = 'date_start desc, id desc'

    name = fields.Char(
        string='Assignment Reference',
        compute='_compute_name',
        store=True
    )

    employee_id = fields.Many2one(
        'hr.employee',
        string='Driver',
        required=True,
        ondelete='cascade',
        index=True,
        help='Employee (driver) assigned to the vehicle, fetched from the Employees app'
    )

    vehicle_id = fields.Many2one(
        'fleet.vehicle',
        string='Vehicle',
        required=True,
        ondelete='cascade',
        help='Vehicle assigned to the driver'
    )

    date_start = fields.Date(
        string='Start Date',
        required=True,
        default=fields.Date.today,
        help='Date when the assignment starts'
    )

    date_end = fields.Date(
        string='End Date',
        help='Date when the assignment ends (leave empty for ongoing assignment)'
    )

    is_active = fields.Boolean(
        string='Is Active',
        compute='_compute_is_active',
        store=True,
        help='Whether this assignment is currently active'
    )

    odometer_start = fields.Float(
        string='Starting Odometer (km)',
        help='Vehicle odometer reading at assignment start'
    )

    odometer_end = fields.Float(
        string='Ending Odometer (km)',
        help='Vehicle odometer reading at assignment end'
    )

    distance_driven = fields.Float(
        string='Distance Driven (km)',
        compute='_compute_distance_driven',
        store=True,
        help='Total distance driven during this assignment'
    )

    notes = fields.Text(
        string='Notes',
        help='Additional notes about the assignment'
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        related='vehicle_id.company_id',
        store=True,
        readonly=True
    )

    @api.depends('employee_id', 'vehicle_id', 'date_start')
    def _compute_name(self):
        """Generate assignment reference name"""
        for assignment in self:
            if assignment.employee_id and assignment.vehicle_id:
                assignment.name = f"{assignment.employee_id.name} - {assignment.vehicle_id.license_plate}"
            else:
                assignment.name = 'New Assignment'

    @api.depends('date_start', 'date_end')
    def _compute_is_active(self):
        """Check if assignment is currently active"""
        today = fields.Date.today()
        for assignment in self:
            if assignment.date_start <= today:
                if not assignment.date_end or assignment.date_end >= today:
                    assignment.is_active = True
                else:
                    assignment.is_active = False
            else:
                assignment.is_active = False

    @api.depends('odometer_start', 'odometer_end')
    def _compute_distance_driven(self):
        """Calculate distance driven during assignment"""
        for assignment in self:
            if assignment.odometer_end and assignment.odometer_start:
                assignment.distance_driven = assignment.odometer_end - assignment.odometer_start
            else:
                assignment.distance_driven = 0.0

    @api.constrains('date_start', 'date_end')
    def _check_dates(self):
        """Validate assignment dates"""
        for assignment in self:
            if assignment.date_end and assignment.date_end < assignment.date_start:
                raise ValidationError(_('End date cannot be before start date'))

            # Check for overlapping assignments for the same driver
            overlapping = self.search([
                ('id', '!=', assignment.id),
                ('employee_id', '=', assignment.employee_id.id),
                ('vehicle_id', '=', assignment.vehicle_id.id),
                ('date_start', '<=', assignment.date_end or '9999-12-31'),
                '|',
                ('date_end', '=', False),
                ('date_end', '>=', assignment.date_start),
            ])

            if overlapping:
                raise ValidationError(_(
                    'This driver already has an overlapping assignment for this vehicle '
                    'during the specified period.'
                ))

    @api.constrains('odometer_start', 'odometer_end')
    def _check_odometer(self):
        """Validate odometer readings"""
        for assignment in self:
            if assignment.odometer_start and assignment.odometer_start < 0:
                raise ValidationError(_('Starting odometer cannot be negative'))
            if assignment.odometer_end and assignment.odometer_end < 0:
                raise ValidationError(_('Ending odometer cannot be negative'))
            if assignment.odometer_end and assignment.odometer_start:
                if assignment.odometer_end < assignment.odometer_start:
                    raise ValidationError(_('Ending odometer cannot be less than starting odometer'))

    def action_end_assignment(self):
        """End the current assignment"""
        self.ensure_one()
        if not self.date_end:
            self.write({
                'date_end': fields.Date.today(),
                'odometer_end': self.vehicle_id.odometer,
            })
        return True
