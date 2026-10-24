# -*- coding: utf-8 -*-

import io
import base64
import csv
from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:
    xlsxwriter = None


class EquipmentTimesheetExportWizard(models.TransientModel):
    _name = 'equipment.timesheet.export.wizard'
    _description = 'Equipment Timesheet Export Wizard'

    export_scope = fields.Selection([
        ('all', 'All Projects'),
        ('project', 'Selected Project'),
        ('timesheet', 'Selected Timesheet'),
    ], string='Export Scope', required=True, default='all')

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        help="Specific project to export timesheets for.",
    )

    timesheet_id = fields.Many2one(
        'equipment.timesheet',
        string='Timesheet',
        help="Specific timesheet to export.",
    )

    scope_display = fields.Char(
        string='Scope',
        compute='_compute_scope_display',
    )

    @api.depends('export_scope', 'project_id', 'timesheet_id')
    def _compute_scope_display(self):
        for rec in self:
            if rec.export_scope == 'timesheet' and rec.timesheet_id:
                rec.scope_display = _("Timesheet: %s (Project: %s)") % (
                    rec.timesheet_id.name,
                    rec.timesheet_id.project_id.name or _("N/A")
                )
            elif rec.export_scope == 'project' and rec.project_id:
                rec.scope_display = _("Project: %s") % rec.project_id.name
            else:
                rec.scope_display = _("All Projects")

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        active_model = self.env.context.get('active_model')
        active_id = self.env.context.get('active_id')
        active_ids = self.env.context.get('active_ids', [])

        if active_model == 'equipment.timesheet' and active_id:
            res['export_scope'] = 'timesheet'
            res['timesheet_id'] = active_id
            ts = self.env['equipment.timesheet'].browse(active_id)
            if ts.exists():
                res['project_id'] = ts.project_id.id
        elif active_model == 'project.project':
            if active_id and len(active_ids) == 1 and self.env.context.get('default_export_scope') != 'all':
                res['export_scope'] = 'project'
                res['project_id'] = active_id
            else:
                res['export_scope'] = 'all'

        if 'default_export_scope' in self.env.context:
            res['export_scope'] = self.env.context.get('default_export_scope')
        if 'default_project_id' in self.env.context:
            res['project_id'] = self.env.context.get('default_project_id')
        if 'default_timesheet_id' in self.env.context:
            res['timesheet_id'] = self.env.context.get('default_timesheet_id')

        return res

    filter_shift = fields.Selection([
        ('all', 'All Shifts (Day & Night)'),
        ('day', 'Day Shift Only'),
        ('night', 'Night Shift Only'),
    ], string='Filter by Shift', required=True, default='all')

    equipment_ids = fields.Many2many(
        'maintenance.equipment',
        'equipment_timesheet_export_equipment_rel',
        'wizard_id',
        'equipment_id',
        string='Filter by Equipment',
        help="Leave empty to export all equipments, or pick specific equipment(s).",
    )

    date_from = fields.Date(
        string='From Date',
        help="Optional start date filter.",
    )

    date_to = fields.Date(
        string='To Date',
        help="Optional end date filter.",
    )

    export_format = fields.Selection([
        ('xlsx', 'Excel Spreadsheet (.xlsx)'),
        ('csv', 'CSV File (.csv)'),
    ], string='Format', required=True, default='xlsx')

    file_data = fields.Binary(
        string='Export File',
        readonly=True,
    )

    file_name = fields.Char(
        string='File Name',
        readonly=True,
    )

    state = fields.Selection([
        ('choose', 'Choose Filters'),
        ('get', 'Download File'),
    ], default='choose')

    @api.onchange('export_scope')
    def _onchange_export_scope(self):
        if self.export_scope == 'all':
            self.project_id = False
            self.timesheet_id = False
        elif self.export_scope == 'project':
            self.timesheet_id = False

    def _get_export_lines(self):
        domain = []
        if self.export_scope == 'timesheet' and self.timesheet_id:
            domain.append(('timesheet_id', '=', self.timesheet_id.id))
        elif self.export_scope == 'project' and self.project_id:
            domain.append(('project_id', '=', self.project_id.id))

        if self.filter_shift in ('day', 'night'):
            domain.append(('shift_type', '=', self.filter_shift))

        if self.equipment_ids:
            domain.append(('equipment_id', 'in', self.equipment_ids.ids))

        if self.date_from:
            domain.append(('date', '>=', self.date_from))

        if self.date_to:
            domain.append(('date', '<=', self.date_to))

        lines = self.env['equipment.timesheet.line'].search(
            domain,
            order='date desc, timesheet_id desc, id asc',
        )
        return lines

    def _format_time_val(self, val):
        if not val and val != 0.0:
            return ""
        hours = int(val)
        mins = int(round((val - hours) * 60))
        return f"{hours:02d}:{mins:02d}"

    def action_export(self):
        self.ensure_one()
        lines = self._get_export_lines()
        if not lines:
            raise UserError(_("No equipment timesheet records found matching your selected filters."))

        # Determine file name prefix
        scope_prefix = "All_Projects"
        if self.export_scope == 'timesheet' and self.timesheet_id:
            clean_ts = "".join(c for c in self.timesheet_id.name if c.isalnum() or c in ('_', '-'))
            scope_prefix = f"Timesheet_{clean_ts}"
        elif self.export_scope == 'project' and self.project_id:
            clean_proj = "".join(c for c in self.project_id.name if c.isalnum() or c in ('_', '-'))
            scope_prefix = f"Project_{clean_proj}"

        date_suffix = fields.Date.today().strftime('%Y%m%d')

        if self.export_format == 'xlsx' and xlsxwriter:
            file_name = f"Equipment_Timesheets_{scope_prefix}_{date_suffix}.xlsx"
            file_bytes = self._generate_xlsx(lines)
        else:
            file_name = f"Equipment_Timesheets_{scope_prefix}_{date_suffix}.csv"
            file_bytes = self._generate_csv(lines)

        self.write({
            'state': 'get',
            'file_name': file_name,
            'file_data': base64.b64encode(file_bytes),
        })

        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=file_data&download=true&filename={file_name}',
            'close': True,
        }

    def _generate_xlsx(self, lines):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        worksheet = workbook.add_worksheet('Equipment Timesheets')

        # Styles
        title_fmt = workbook.add_format({
            'bold': True,
            'font_size': 14,
            'font_color': '#1e3a8a',
            'align': 'left',
            'valign': 'vcenter',
        })
        info_fmt = workbook.add_format({
            'font_size': 9,
            'font_color': '#64748b',
            'italic': True,
        })
        header_fmt = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'font_color': '#ffffff',
            'bg_color': '#1e3a8a',
            'border': 1,
            'border_color': '#cbd5e1',
            'align': 'center',
            'valign': 'vcenter',
            'text_wrap': True,
        })
        cell_fmt = workbook.add_format({
            'font_size': 10,
            'border': 1,
            'border_color': '#e2e8f0',
            'valign': 'vcenter',
        })
        cell_center = workbook.add_format({
            'font_size': 10,
            'border': 1,
            'border_color': '#e2e8f0',
            'align': 'center',
            'valign': 'vcenter',
        })
        cell_num = workbook.add_format({
            'font_size': 10,
            'border': 1,
            'border_color': '#e2e8f0',
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
        })
        total_label_fmt = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'bg_color': '#f1f5f9',
            'border': 1,
            'border_color': '#cbd5e1',
            'align': 'right',
            'valign': 'vcenter',
        })
        total_num_fmt = workbook.add_format({
            'bold': True,
            'font_size': 10,
            'bg_color': '#f1f5f9',
            'border': 1,
            'border_color': '#cbd5e1',
            'align': 'right',
            'valign': 'vcenter',
            'num_format': '#,##0.00',
        })

        # Headers
        headers = [
            'Reference',
            'Date',
            'Project',
            'Customer',
            'Reported By',
            'Status',
            'Equipment',
            'Equipment Type',
            'Model',
            'Serial / Plate No.',
            'Shift',
            'Morning Start',
            'Morning End',
            'Afternoon Start',
            'Afternoon End',
            'Total Hours',
            'Idle Time (h)',
            'Idle Reason',
            'Starting Fuel (L)',
            'Fuel Refueled (L)',
            'Fuel Left (Closing) (L)',
            'Fuel Consumed (L)',
            'Remarks / Notes',
        ]

        # Title Row
        worksheet.write(0, 0, 'Equipment Timesheet Operations Report', title_fmt)
        worksheet.write(1, 0, f"Exported on: {fields.Datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Scope: {dict(self._fields['export_scope'].selection).get(self.export_scope)}", info_fmt)

        row = 3
        worksheet.set_row(row, 28)
        for col, h in enumerate(headers):
            worksheet.write(row, col, h, header_fmt)

        start_data_row = row + 1
        for line in lines:
            row += 1
            worksheet.set_row(row, 20)

            # Values
            ts_ref = line.timesheet_id.name or ''
            date_str = line.date.strftime('%Y-%m-%d') if line.date else ''
            project_name = line.project_id.name or ''
            partner_name = line.project_id.partner_id.name or ''
            reporter = line.user_id.name or ''
            state_label = dict(line.timesheet_id._fields['state'].selection).get(line.timesheet_id.state, '')
            eq_name = line.equipment_id.name or ''
            eq_type = line.equipment_category_id.name or (line.equipment_id.category_id.name if line.equipment_id.category_id else '')
            eq_model = line.equipment_model or line.equipment_id.model or ''
            eq_serial = line.equipment_serial or line.equipment_id.serial_no or ''
            shift_label = dict(line._fields['shift_type'].selection).get(line.shift_type, '')
            m_start = self._format_time_val(line.day_start_time)
            m_end = self._format_time_val(line.day_end_time)
            a_start = self._format_time_val(line.night_start_time)
            a_end = self._format_time_val(line.night_end_time)
            tot_hours = line.total_hours or 0.0
            idle_h = line.idle_time or 0.0
            idle_r = line.idle_reason or ''
            fuel_open = line.fuel_opening or 0.0
            fuel_ref = line.fuel_refueled or 0.0
            fuel_lft = line.fuel_left or 0.0
            fuel_cons = line.fuel_consumed or 0.0
            remarks = line.description or ''

            worksheet.write(row, 0, ts_ref, cell_center)
            worksheet.write(row, 1, date_str, cell_center)
            worksheet.write(row, 2, project_name, cell_fmt)
            worksheet.write(row, 3, partner_name, cell_fmt)
            worksheet.write(row, 4, reporter, cell_fmt)
            worksheet.write(row, 5, state_label, cell_center)
            worksheet.write(row, 6, eq_name, cell_fmt)
            worksheet.write(row, 7, eq_type, cell_fmt)
            worksheet.write(row, 8, eq_model, cell_fmt)
            worksheet.write(row, 9, eq_serial, cell_fmt)
            worksheet.write(row, 10, shift_label, cell_center)
            worksheet.write(row, 11, m_start, cell_center)
            worksheet.write(row, 12, m_end, cell_center)
            worksheet.write(row, 13, a_start, cell_center)
            worksheet.write(row, 14, a_end, cell_center)
            worksheet.write(row, 15, tot_hours, cell_num)
            worksheet.write(row, 16, idle_h, cell_num)
            worksheet.write(row, 17, idle_r, cell_fmt)
            worksheet.write(row, 18, fuel_open, cell_num)
            worksheet.write(row, 19, fuel_ref, cell_num)
            worksheet.write(row, 20, fuel_lft, cell_num)
            worksheet.write(row, 21, fuel_cons, cell_num)
            worksheet.write(row, 22, remarks, cell_fmt)

        # Summary Row (Rows in Excel are 1-based, header is at row 4, first data row is 5)
        first_data_row_excel = 5
        last_data_row_excel = 4 + len(lines)

        tot_sum_hours = sum(l.total_hours or 0.0 for l in lines)
        tot_sum_idle = sum(l.idle_time or 0.0 for l in lines)
        tot_sum_refueled = sum(l.fuel_refueled or 0.0 for l in lines)
        tot_sum_consumed = sum(l.fuel_consumed or 0.0 for l in lines)

        row += 1
        worksheet.set_row(row, 22)
        worksheet.merge_range(row, 0, row, 14, 'Grand Total:', total_label_fmt)
        worksheet.write_formula(row, 15, f"=SUM(P{first_data_row_excel}:P{last_data_row_excel})", total_num_fmt, value=tot_sum_hours)
        worksheet.write_formula(row, 16, f"=SUM(Q{first_data_row_excel}:Q{last_data_row_excel})", total_num_fmt, value=tot_sum_idle)
        worksheet.write(row, 17, '', total_label_fmt)
        worksheet.write(row, 18, '', total_label_fmt)
        worksheet.write_formula(row, 19, f"=SUM(T{first_data_row_excel}:T{last_data_row_excel})", total_num_fmt, value=tot_sum_refueled)
        worksheet.write(row, 20, '', total_label_fmt)
        worksheet.write_formula(row, 21, f"=SUM(V{first_data_row_excel}:V{last_data_row_excel})", total_num_fmt, value=tot_sum_consumed)
        worksheet.write(row, 22, '', total_label_fmt)

        # Auto-adjust column widths
        col_widths = [15, 12, 22, 20, 16, 12, 22, 18, 14, 18, 10, 14, 14, 15, 15, 14, 14, 20, 16, 16, 20, 17, 24]
        for col_idx, width in enumerate(col_widths):
            worksheet.set_column(col_idx, col_idx, width)

        workbook.close()
        return output.getvalue()

    def _generate_csv(self, lines):
        output = io.StringIO()
        writer = csv.writer(output, delimiter=',', quotechar='"', quoting=csv.QUOTE_MINIMAL)

        # Headers
        headers = [
            'Reference',
            'Date',
            'Project',
            'Customer',
            'Reported By',
            'Status',
            'Equipment',
            'Equipment Type',
            'Model',
            'Serial / Plate No.',
            'Shift',
            'Morning Start',
            'Morning End',
            'Afternoon Start',
            'Afternoon End',
            'Total Hours',
            'Idle Time',
            'Idle Reason',
            'Starting Fuel (L)',
            'Fuel Refueled (L)',
            'Fuel Left (Closing) (L)',
            'Fuel Consumed (L)',
            'Remarks / Notes',
        ]
        writer.writerow(headers)

        for line in lines:
            ts_ref = line.timesheet_id.name or ''
            date_str = line.date.strftime('%Y-%m-%d') if line.date else ''
            project_name = line.project_id.name or ''
            partner_name = line.project_id.partner_id.name or ''
            reporter = line.user_id.name or ''
            state_label = dict(line.timesheet_id._fields['state'].selection).get(line.timesheet_id.state, '')
            eq_name = line.equipment_id.name or ''
            eq_type = line.equipment_category_id.name or (line.equipment_id.category_id.name if line.equipment_id.category_id else '')
            eq_model = line.equipment_model or line.equipment_id.model or ''
            eq_serial = line.equipment_serial or line.equipment_id.serial_no or ''
            shift_label = dict(line._fields['shift_type'].selection).get(line.shift_type, '')
            m_start = self._format_time_val(line.day_start_time)
            m_end = self._format_time_val(line.day_end_time)
            a_start = self._format_time_val(line.night_start_time)
            a_end = self._format_time_val(line.night_end_time)
            tot_hours = f"{line.total_hours:.2f}"
            idle_h = f"{line.idle_time:.2f}"
            idle_r = line.idle_reason or ''
            fuel_open = f"{line.fuel_opening:.2f}"
            fuel_ref = f"{line.fuel_refueled:.2f}"
            fuel_lft = f"{line.fuel_left:.2f}"
            fuel_cons = f"{line.fuel_consumed:.2f}"
            remarks = line.description or ''

            writer.writerow([
                ts_ref, date_str, project_name, partner_name, reporter, state_label,
                eq_name, eq_type, eq_model, eq_serial, shift_label,
                m_start, m_end, a_start, a_end, tot_hours, idle_h, idle_r,
                fuel_open, fuel_ref, fuel_lft, fuel_cons, remarks
            ])

        # UTF-8 BOM for Excel compatibility
        return ('\ufeff' + output.getvalue()).encode('utf-8')
