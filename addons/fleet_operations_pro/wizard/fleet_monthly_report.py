# -*- coding: utf-8 -*-

import base64

import io
from collections import Counter

from odoo import api, fields, models, _
from odoo.exceptions import UserError

try:
    import xlsxwriter
except ImportError:  # pragma: no cover
    xlsxwriter = None



# (key, header, Excel width, kind) - kind drives number formatting and totals
COLUMNS = [
    ('plate', 'Plate No', 12, 'text'),
    ('name', 'Car Name', 16, 'text'),
    ('driver', 'Current Driver', 18, 'text'),
    ('odometer_start', 'Odometer Start (km)', 12, 'km'),
    ('odometer_end', 'Odometer End (km)', 12, 'km'),
    ('km_driven', 'Km Driven', 10, 'km_total'),
    ('trips', 'Total Trips', 8, 'int_total'),
    ('fuel_liters', 'Fuel (L)', 9, 'num_total'),
    ('fuel_cost', 'Fuel Cost', 11, 'money_total'),
    ('service_count', 'No. of Services', 9, 'int_total'),
    ('service_types', 'Service Types Done', 24, 'text'),
    ('service_cost', 'Service Cost', 11, 'money_total'),
    ('contracts', 'Vehicle Agreements', 30, 'text'),
    ('contract_cost', 'Vehicle Agreement Cost', 11, 'money_total'),
    ('total_cost', 'Total Cost', 12, 'money_total'),
    ('remark', 'Remark', 30, 'text'),
]


class FleetMonthlyReport(models.TransientModel):
    _name = 'fleet.monthly.report'
    _description = 'Fleet Report (date range)'

    date_from = fields.Date(
        string='From', required=True,
        default=lambda self: fields.Date.context_today(self).replace(day=1),
    )
    date_to = fields.Date(
        string='To', required=True,
        default=lambda self: fields.Date.context_today(self),
    )
    vehicle_ids = fields.Many2many(
        'fleet.vehicle', string='Vehicles',
        help='Leave empty to include all vehicles',
    )
    company_id = fields.Many2one(
        'res.company', string='Company', required=True,
        default=lambda self: self.env.company,
    )
    file_data = fields.Binary(string='File', readonly=True, attachment=False)

    # ------------------------------------------------------------------
    # Period helpers
    # ------------------------------------------------------------------
    def _period(self):
        self.ensure_one()
        if self.date_to < self.date_from:
            raise UserError(_('The "To" date cannot be before the "From" date.'))
        return self.date_from, self.date_to

    def get_period_label(self):
        return f"{self.date_from.strftime('%d-%m-%Y')} to {self.date_to.strftime('%d-%m-%Y')}"

    def _get_vehicles(self):
        self.ensure_one()
        if self.vehicle_ids:
            return self.vehicle_ids.sorted('license_plate')
        return self.env['fleet.vehicle'].search(
            [('company_id', '=', self.company_id.id)], order='license_plate')

    # ------------------------------------------------------------------
    # Data
    # ------------------------------------------------------------------
    def _odometer_readings(self, vehicle, end):
        """All dated odometer readings of the vehicle up to the end of the period"""
        readings = []

        def add(records, date_field, km_field):
            for rec in records:
                rec_date, km = rec[date_field], rec[km_field]
                if rec_date and km:
                    readings.append((rec_date, km))

        domain = [('vehicle_id', '=', vehicle.id)]
        add(self.env['fleet.fuel.log'].search(domain + [('date', '<=', end)]), 'date', 'odometer')
        add(self.env['fleet.trip'].search(domain + [('date', '<=', end)]), 'date', 'end_odometer')
        add(self.env['fleet.maintenance'].search(domain + [('date', '<=', end)]), 'date', 'odometer')
        add(self.env['fleet.toll.record'].search(domain + [('date', '<=', end)]), 'date', 'odometer')
        for service in self.env['fleet.service'].search(domain + [('state', '=', 'done')]):
            service_date = service.end_date or service.date
            if service_date and service_date <= end and service.odometer:
                readings.append((service_date, service.odometer))
        if vehicle.odometer and vehicle.odometer_date and vehicle.odometer_date <= end:
            readings.append((vehicle.odometer_date, vehicle.odometer))
        return sorted(readings)

    def _contract_period_cost(self, contract, start, end):
        """The contract cost counts in the period containing its start date"""
        return contract.cost if start <= contract.start_date <= end else 0.0

    def _contract_status(self, contract, end):
        type_name = contract.contract_type_id.name or _('Vehicle Agreement')
        return f"{type_name}: {contract.name}"

    def _get_report_lines(self):
        """One dict per vehicle with all report columns, plus a totals dict"""
        self.ensure_one()
        start, end = self._period()
        today = fields.Date.context_today(self)
        lines = []
        for vehicle in self._get_vehicles():
            domain = [('vehicle_id', '=', vehicle.id)]

            # Odometer
            readings = self._odometer_readings(vehicle, end)
            before = [km for d, km in readings if d < start]
            in_month = [km for d, km in readings if start <= d <= end]
            odo_start = before[-1] if before else (min(in_month) if in_month else None)
            odo_end = max(before[-1:] + in_month) if (before or in_month) else None
            km_driven = (odo_end - odo_start) if odo_start is not None and odo_end is not None else None

            # Trips & fuel
            trips = self.env['fleet.trip'].search_count(domain + [('date', '>=', start), ('date', '<=', end)])
            fuel_logs = self.env['fleet.fuel.log'].search(domain + [('date', '>=', start), ('date', '<=', end)])
            fuel_liters = sum(fuel_logs.mapped('quantity'))
            fuel_cost = sum(fuel_logs.mapped('total_cost'))

            # Services completed in the month
            services = self.env['fleet.service'].search(domain + [('state', '=', 'done')]).filtered(
                lambda s: start <= (s.end_date or s.date) <= end)
            type_counts = Counter(services.mapped('service_type_id.name'))
            service_types = ', '.join(
                f"{name} x{count}" if count > 1 else name for name, count in sorted(type_counts.items()))
            service_cost = sum(services.mapped('cost'))

            # Vehicle Agreements running during the month
            contracts = self.env['fleet.contract'].search(domain + [
                ('state', 'in', ('running', 'expired')),
                ('start_date', '<=', end),
                ('end_date', '>=', start),
            ], order='end_date')
            contract_text = '\n'.join(self._contract_status(c, end) for c in contracts)
            contract_cost = sum(self._contract_period_cost(c, start, end) for c in contracts)

            # Automatic remark
            remarks = []
            for contract in contracts:
                if contract.end_date < today and contract.state in ('running', 'expired'):
                    remarks.append(_('%s expired') % (contract.contract_type_id.name or contract.name))
            last_done = self.env['fleet.service'].search(
                domain + [('state', '=', 'done'), ('next_service_odometer', '>', 0)],
                order='end_date desc, id desc', limit=1)
            if last_done and vehicle.odometer >= last_done.next_service_odometer:
                remarks.append(_('Service overdue (%s)') % last_done.service_type_id.name)
            if not in_month:
                remarks.append(_('No odometer reading in this period'))

            lines.append({
                'plate': vehicle.license_plate or '',
                'name': vehicle.name or '',
                'driver': vehicle.driver_id.name or '',
                'odometer_start': odo_start,
                'odometer_end': odo_end,
                'km_driven': km_driven,
                'trips': trips,
                'fuel_liters': fuel_liters,
                'fuel_cost': fuel_cost,
                'service_count': len(services),
                'service_types': service_types,
                'service_cost': service_cost,
                'contracts': contract_text,
                'contract_cost': contract_cost,
                'total_cost': fuel_cost + service_cost + contract_cost,
                'remark': '; '.join(remarks),
            })

        totals = {}
        for key, _header, _width, kind in COLUMNS:
            if kind.endswith('_total'):
                totals[key] = sum(line[key] or 0 for line in lines)
        return lines, totals

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def action_export_xlsx(self):
        self.ensure_one()
        if not xlsxwriter:
            raise UserError(_('The Python library xlsxwriter is not installed on the server.'))
        lines, totals = self._get_report_lines()
        self.file_data = base64.b64encode(self._build_xlsx(lines, totals))
        filename = f"Fleet_Report_{self.date_from}_{self.date_to}.xlsx"
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content?model={self._name}&id={self.id}&field=file_data&download=true&filename={filename}',
            'target': 'self',
        }

    def _build_xlsx(self, lines, totals):
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory': True})
        sheet = workbook.add_worksheet(_('Fleet Report'))
        currency = self.company_id.currency_id

        title_fmt = workbook.add_format({'bold': True, 'font_size': 14})
        info_fmt = workbook.add_format({'font_size': 9, 'italic': True})
        header_fmt = workbook.add_format({
            'bold': True, 'font_size': 9, 'bg_color': '#D9E1F2', 'border': 1,
            'text_wrap': True, 'valign': 'vcenter', 'align': 'center'})
        text_fmt = workbook.add_format({'font_size': 9, 'border': 1, 'text_wrap': True, 'valign': 'top'})
        plate_fmt = workbook.add_format({'font_size': 9, 'border': 1, 'bold': True, 'valign': 'top'})
        int_fmt = workbook.add_format({'font_size': 9, 'border': 1, 'num_format': '#,##0', 'valign': 'top'})
        num_fmt = workbook.add_format({'font_size': 9, 'border': 1, 'num_format': '#,##0.00', 'valign': 'top'})
        total_label_fmt = workbook.add_format({'bold': True, 'font_size': 9, 'border': 1, 'bg_color': '#F2F2F2'})
        total_int_fmt = workbook.add_format({
            'bold': True, 'font_size': 9, 'border': 1, 'bg_color': '#F2F2F2', 'num_format': '#,##0'})
        total_num_fmt = workbook.add_format({
            'bold': True, 'font_size': 9, 'border': 1, 'bg_color': '#F2F2F2', 'num_format': '#,##0.00'})

        # Header block
        sheet.write(0, 0, self.company_id.name, title_fmt)
        sheet.write(1, 0, _('Fleet Report: %s') % self.get_period_label(), title_fmt)
        sheet.write(2, 0, _('Printed %(date)s by %(user)s  ·  Amounts in %(currency)s') % {
            'date': fields.Datetime.context_timestamp(self, fields.Datetime.now()).strftime('%d/%m/%Y %H:%M'),
            'user': self.env.user.name,
            'currency': currency.name,
        }, info_fmt)

        header_row = 4
        for col, (_key, header, width, _kind) in enumerate(COLUMNS):
            sheet.set_column(col, col, width)
            sheet.write(header_row, col, header, header_fmt)
        sheet.set_row(header_row, 30)

        row = header_row + 1
        for line in lines:
            for col, (key, _header, _width, kind) in enumerate(COLUMNS):
                value = line[key]
                if kind == 'text':
                    sheet.write(row, col, value or '', plate_fmt if key == 'plate' else text_fmt)
                elif value is None:
                    sheet.write(row, col, '-', text_fmt)
                elif kind in ('km', 'km_total', 'int_total'):
                    sheet.write_number(row, col, value, int_fmt)
                else:
                    sheet.write_number(row, col, value, num_fmt)
            row += 1

        # Totals row
        sheet.write(row, 0, _('TOTAL'), total_label_fmt)
        for col, (key, _header, _width, kind) in enumerate(COLUMNS[1:], start=1):
            if key in totals:
                fmt = total_int_fmt if kind in ('km_total', 'int_total') else total_num_fmt
                sheet.write_number(row, col, totals[key], fmt)
            else:
                sheet.write(row, col, '', total_label_fmt)

        # Print layout: landscape A4, one page wide, header row repeated on every page
        sheet.set_landscape()
        sheet.set_paper(9)
        sheet.fit_to_pages(1, 0)
        sheet.set_margins(left=0.3, right=0.3, top=0.5, bottom=0.5)
        sheet.repeat_rows(header_row)
        sheet.freeze_panes(header_row + 1, 1)
        sheet.set_footer('&L&8%s&R&8Page &P of &N' % self.get_period_label())

        workbook.close()
        return output.getvalue()
