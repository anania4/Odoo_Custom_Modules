# -*- coding: utf-8 -*-

from odoo import api, fields, models, _


class ProjectProject(models.Model):
    _inherit = 'project.project'

    equipment_timesheet_ids = fields.One2many(
        'equipment.timesheet',
        'project_id',
        string='Equipment Timesheets',
    )
    equipment_timesheet_line_ids = fields.One2many(
        'equipment.timesheet.line',
        'project_id',
        string='Equipment Timesheet Lines',
    )
    equipment_timesheet_count = fields.Integer(
        string='Total Equipment Timesheets',
        compute='_compute_equipment_timesheet_stats',
    )
    equipment_timesheet_pending_count = fields.Integer(
        string='Pending Approvals',
        compute='_compute_equipment_timesheet_stats',
    )
    equipment_timesheet_approved_count = fields.Integer(
        string='Approved Timesheets',
        compute='_compute_equipment_timesheet_stats',
    )
    equipment_total_hours = fields.Float(
        string='Total Equipment Hours',
        compute='_compute_equipment_timesheet_stats',
        digits=(12, 2),
    )
    equipment_total_fuel_consumed = fields.Float(
        string='Total Fuel Consumed (L)',
        compute='_compute_equipment_timesheet_stats',
        digits=(12, 2),
    )
    equipment_count_distinct = fields.Integer(
        string='Equipments Used',
        compute='_compute_equipment_timesheet_stats',
    )
    equipment_types_display = fields.Char(
        string='Equipment Types',
        compute='_compute_equipment_timesheet_stats',
    )

    def _compute_equipment_timesheet_stats(self):
        for project in self:
            timesheets = project.equipment_timesheet_ids
            project.equipment_timesheet_count = len(timesheets)
            project.equipment_timesheet_pending_count = len(timesheets.filtered(lambda t: t.state == 'submitted'))
            project.equipment_timesheet_approved_count = len(timesheets.filtered(lambda t: t.state == 'approved'))
            project.equipment_total_hours = sum(timesheets.mapped('total_hours'))
            project.equipment_total_fuel_consumed = sum(timesheets.mapped('total_fuel_consumed'))
            project.equipment_count_distinct = len(set(project.equipment_timesheet_line_ids.mapped('equipment_id.id')))
            
            # Extract unique equipment types / categories used on this project
            types = []
            for line in project.equipment_timesheet_line_ids:
                if line.equipment_id:
                    t_name = line.equipment_category_id.name or line.equipment_id.category_id.name or line.equipment_id.name
                    if t_name and t_name not in types:
                        types.append(t_name)
            project.equipment_types_display = ", ".join(types) if types else _("None")

    def action_view_equipment_timesheets(self):
        self.ensure_one()
        return {
            'name': _('Equipment Timesheets - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'equipment.timesheet',
            'view_mode': 'list,kanban,form',
            'domain': [('project_id', '=', self.id)],
            'context': {
                'default_project_id': self.id,
                'search_default_project_id': self.id,
            },
        }

    def action_create_equipment_timesheet(self):
        self.ensure_one()
        return {
            'name': _('New Equipment Timesheet - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'equipment.timesheet',
            'view_mode': 'form',
            'target': 'current',
            'context': {
                'default_project_id': self.id,
            },
        }

    def action_open_export_wizard(self):
        self.ensure_one()
        return {
            'name': _('Export Report - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'equipment.timesheet.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_export_scope': 'project',
                'default_project_id': self.id,
            },
        }

    def action_open_export_wizard_all(self):
        return {
            'name': _('Export Report - All Projects'),
            'type': 'ir.actions.act_window',
            'res_model': 'equipment.timesheet.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_export_scope': 'all',
            },
        }
