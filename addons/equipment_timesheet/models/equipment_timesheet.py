# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError


class EquipmentTimesheet(models.Model):
    _name = 'equipment.timesheet'
    _description = 'Equipment Field Timesheet'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date desc, id desc'

    name = fields.Char(
        string='Reference',
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
        tracking=True,
    )

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        required=True,
        tracking=True,
        index=True,
        default=lambda self: self.env.context.get('default_project_id', False),
    )

    date = fields.Date(
        string='Date',
        required=True,
        default=fields.Date.context_today,
        tracking=True,
        index=True,
    )

    user_id = fields.Many2one(
        'res.users',
        string='Reported By',
        required=True,
        default=lambda self: self.env.user,
        readonly=True,
        tracking=True,
        index=True,
    )

    # --- Equipment Lines (Same as product lines on order) ---
    line_ids = fields.One2many(
        'equipment.timesheet.line',
        'timesheet_id',
        string='Equipment Lines',
        copy=True,
    )

    # --- Totals Computed from Lines ---
    day_total_hours = fields.Float(
        string='Day (Morning) Total Hours',
        compute='_compute_totals',
        store=True,
        digits=(12, 2),
    )
    night_total_hours = fields.Float(
        string='Night (Afternoon) Total Hours',
        compute='_compute_totals',
        store=True,
        digits=(12, 2),
    )
    total_hours = fields.Float(
        string='Grand Total Hours',
        compute='_compute_totals',
        store=True,
        digits=(12, 2),
        tracking=True,
    )

    total_idle_time = fields.Float(
        string='Total Idle Time',
        compute='_compute_totals',
        digits=(12, 2),
    )

    total_fuel_refueled = fields.Float(
        string='Total Fuel Refueled (L)',
        compute='_compute_totals',
        store=True,
        digits=(12, 2),
    )
    total_fuel_left = fields.Float(
        string='Total Fuel Left (L)',
        compute='_compute_totals',
        store=True,
        digits=(12, 2),
    )
    total_fuel_consumed = fields.Float(
        string='Grand Total Fuel Consumed (L)',
        compute='_compute_totals',
        store=True,
        digits=(12, 2),
        tracking=True,
    )

    equipment_count = fields.Integer(
        string='Equipments Working',
        compute='_compute_totals',
        store=True,
    )

    # --- Workflow State ---
    state = fields.Selection([
        ('draft', 'Draft'),
        ('submitted', 'Submitted'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ], string='Status', default='draft', required=True, tracking=True, copy=False)

    description = fields.Text(string='General Notes / Remarks')

    approved_by_id = fields.Many2one(
        'res.users',
        string='Approved By',
        readonly=True,
        copy=False,
        tracking=True,
    )
    approved_date = fields.Datetime(
        string='Approved On',
        readonly=True,
        copy=False,
        tracking=True,
    )
    rejection_reason = fields.Text(
        string='Rejection Reason',
        readonly=True,
        copy=False,
        tracking=True,
    )

    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True,
    )

    is_manager = fields.Boolean(
        string='Is Project Manager',
        compute='_compute_is_manager',
    )

    def _compute_is_manager(self):
        has_group = self.env.user.has_group('equipment_timesheet.group_equipment_timesheet_manager')
        for record in self:
            record.is_manager = has_group

    @api.model
    def _register_hook(self):
        super()._register_hook()
        menu = self.env.ref('hr_timesheet.timesheet_menu_root', raise_if_not_found=False)
        if menu and menu.active:
            menu.sudo().write({'active': False})

    @api.depends('line_ids.total_hours', 'line_ids.shift_type', 'line_ids.idle_time',
                 'line_ids.fuel_refueled', 'line_ids.fuel_left', 'line_ids.fuel_consumed')
    def _compute_totals(self):
        for record in self:
            record.day_total_hours = sum(record.line_ids.filtered(lambda l: l.shift_type == 'day').mapped('total_hours'))
            record.night_total_hours = sum(record.line_ids.filtered(lambda l: l.shift_type == 'night').mapped('total_hours'))
            record.total_hours = sum(record.line_ids.mapped('total_hours'))
            record.total_idle_time = sum(record.line_ids.mapped('idle_time'))
            record.total_fuel_refueled = sum(record.line_ids.mapped('fuel_refueled'))
            record.total_fuel_left = sum(record.line_ids.mapped('fuel_left'))
            record.total_fuel_consumed = sum(record.line_ids.mapped('fuel_consumed'))
            record.equipment_count = len(record.line_ids)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if vals.get('name', _('New')) == _('New'):
                vals['name'] = self.env['ir.sequence'].next_by_code('equipment.timesheet') or _('New')
            # Always ensure date is today if not provided
            if not vals.get('date'):
                vals['date'] = fields.Date.context_today(self)
            # Always ensure user_id is current user if not provided
            if not vals.get('user_id'):
                vals['user_id'] = self.env.user.id
            # Default project_id from context if available
            if not vals.get('project_id') and self.env.context.get('default_project_id'):
                vals['project_id'] = self.env.context.get('default_project_id')
        return super().create(vals_list)

    def write(self, vals):
        if not self.env.user.has_group('equipment_timesheet.group_equipment_timesheet_manager'):
            for record in self:
                if record.state in ('submitted', 'approved'):
                    allowed_fields = {'message_ids', 'activity_ids', 'message_follower_ids'}
                    if not set(vals.keys()).issubset(allowed_fields):
                        raise UserError(_("You cannot modify a timesheet that is submitted or approved."))
        return super().write(vals)

    def unlink(self):
        for record in self:
            if record.state != 'draft' and not self.env.user.has_group('equipment_timesheet.group_equipment_timesheet_manager'):
                raise UserError(_("You can only delete draft timesheets."))
        return super().unlink()

    # --- Notification & Activity Helpers ---
    def _get_project_managers(self):
        """Retrieve managers responsible for approving this timesheet"""
        managers = self.env['res.users'].sudo()
        if self.project_id.user_id:
            managers |= self.project_id.user_id
        else:
            group = self.env.ref('equipment_timesheet.group_equipment_timesheet_manager', raise_if_not_found=False)
            if group:
                managers |= group.users
        managers = managers.filtered(lambda u: u.active)
        other_managers = managers.filtered(lambda u: u.id != self.env.uid)
        return other_managers if other_managers else managers

    def _send_odoo_notification(self, users, title, message, notif_type='info'):
        """Send standard Odoo chatter notification and real-time web client toast via bus"""
        partners = users.mapped('partner_id').filtered(lambda p: bool(p.id))
        if not partners:
            return
        # Post in chatter notifying the target partners
        self.message_post(
            body=message,
            subject=title,
            partner_ids=partners.ids,
            message_type='notification',
            subtype_xmlid='mail.mt_comment',
        )
        # Real-time web client toast
        for partner in partners:
            self.env['bus.bus'].sudo()._sendone(
                partner,
                'simple_notification',
                {
                    'type': notif_type,
                    'title': title,
                    'message': message,
                    'sticky': notif_type in ('danger', 'warning'),
                }
            )

    def _schedule_approval_activity(self, managers):
        """Schedule an activity in Odoo's native activity systray (clock icon) for the approvers"""
        for manager in managers:
            existing = self.env['mail.activity'].sudo().search([
                ('res_model', '=', self._name),
                ('res_id', '=', self.id),
                ('user_id', '=', manager.id),
            ])
            if not existing:
                self.activity_schedule(
                    act_type_xmlid='mail.mail_activity_data_todo',
                    summary=_("Approve Equipment Timesheet: %s") % self.name,
                    note=_("Timesheet %s for project '%s' submitted by %s requires your approval.") % (
                        self.name, self.project_id.name, self.user_id.name
                    ),
                    user_id=manager.id,
                )

    def _close_approval_activities(self, feedback):
        """Mark approval activities as completed"""
        self.activity_feedback(['mail.mail_activity_data_todo'], feedback=feedback)

    # --- Actions / Approval Workflow ---
    def action_save(self):
        """Explicit save action for mobile view and user convenience."""
        self.ensure_one()
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": _("Saved"),
                "message": _("Equipment timesheet saved successfully."),
                "type": "success",
                "sticky": False,
            },
        }

    def action_submit(self):
        for record in self:
            if record.state != 'draft':
                raise UserError(_("Only draft timesheets can be submitted."))
            if not record.project_id:
                raise UserError(_("Please specify a project before submitting."))
            if not record.line_ids:
                raise UserError(_("Please add at least one equipment line before submitting."))
            record.write({'state': 'submitted'})
            
            managers = record._get_project_managers()
            title = _("New Equipment Timesheet Submitted: %s") % record.name
            msg = _("Timesheet %s for project '%s' has been submitted by %s for approval.") % (
                record.name, record.project_id.name, record.user_id.name
            )
            
    def action_approve(self):
        if not self.env.user.has_group('equipment_timesheet.group_equipment_timesheet_manager'):
            raise UserError(_("Only Project Managers can approve equipment timesheets."))
        for record in self:
            if record.state != 'submitted':
                raise UserError(_("Only submitted timesheets can be approved."))
            record.write({
                'state': 'approved',
                'approved_by_id': self.env.user.id,
                'approved_date': fields.Datetime.now(),
            })
            
            # Close pending approval activities
            record._close_approval_activities(_("Approved by %s") % self.env.user.name)
            
            reporter = record.user_id
            title = _("Equipment Timesheet Approved: %s") % record.name
            msg = _("Your equipment timesheet %s for project '%s' has been approved by Project Manager %s.") % (
                record.name, record.project_id.name, self.env.user.name
            )
            
    def action_reject(self):
        if not self.env.user.has_group('equipment_timesheet.group_equipment_timesheet_manager'):
            raise UserError(_("Only Project Managers can reject equipment timesheets."))
        for record in self:
            if record.state != 'submitted':
                raise UserError(_("Only submitted timesheets can be rejected."))
            record.write({'state': 'rejected'})
            
            # Close pending approval activities
            record._close_approval_activities(_("Rejected by %s") % self.env.user.name)
            
            reporter = record.user_id
            title = _("Equipment Timesheet Rejected: %s") % record.name
            msg = _("Your equipment timesheet %s for project '%s' has been rejected by Project Manager %s.") % (
                record.name, record.project_id.name, self.env.user.name
            )
            
    def action_reset_draft(self):
        if not self.env.user.has_group('equipment_timesheet.group_equipment_timesheet_manager'):
            raise UserError(_("Only Project Managers can reset timesheets to draft."))
        for record in self:
            record.write({
                'state': 'draft',
                'approved_by_id': False,
                'approved_date': False,
            })
            
            # Close pending approval activities
            record._close_approval_activities(_("Reset to draft by %s") % self.env.user.name)
            
            reporter = record.user_id
            title = _("Equipment Timesheet Reset to Draft: %s") % record.name
            msg = _("Timesheet %s for project '%s' has been reset to draft by %s.") % (
                record.name, record.project_id.name, self.env.user.name
            )
            
    def action_open_export_wizard(self):
        self.ensure_one()
        return {
            'name': _('Export Timesheet Lines - %s') % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'equipment.timesheet.export.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_export_scope': 'timesheet',
                'default_timesheet_id': self.id,
                'default_project_id': self.project_id.id,
            },
        }


class EquipmentTimesheetLine(models.Model):
    _name = 'equipment.timesheet.line'
    _description = 'Equipment Timesheet Line'
    _order = 'id asc'

    timesheet_id = fields.Many2one(
        'equipment.timesheet',
        string='Timesheet',
        required=True,
        ondelete='cascade',
        index=True,
    )

    project_id = fields.Many2one(
        'project.project',
        string='Project',
        related='timesheet_id.project_id',
        store=True,
        readonly=True,
        index=True,
    )

    date = fields.Date(
        string='Date',
        related='timesheet_id.date',
        store=True,
        readonly=True,
        index=True,
    )

    user_id = fields.Many2one(
        'res.users',
        string='Reported By',
        related='timesheet_id.user_id',
        store=True,
        readonly=True,
        index=True,
    )

    state = fields.Selection(
        string='Status',
        related='timesheet_id.state',
        store=True,
        readonly=True,
    )

    # --- Equipment from Maintenance Equipment Registration ---
    equipment_id = fields.Many2one(
        'maintenance.equipment',
        string='Equipment',
        required=True,
        index=True,
    )

    equipment_category_id = fields.Many2one(
        'maintenance.equipment.category',
        string='Equipment Type / Category',
        related='equipment_id.category_id',
        store=True,
        readonly=True,
    )

    equipment_model = fields.Char(
        string='Model',
        related='equipment_id.model',
        readonly=True,
    )

    equipment_serial = fields.Char(
        string='Serial / Plate No.',
        related='equipment_id.serial_no',
        readonly=True,
    )

    # --- Shift Selection: Day or Night ---
    shift_type = fields.Selection([
        ('day', 'Day'),
        ('night', 'Night'),
    ], string='Shift', required=True, default='day', index=True)

    # --- Working Hours: Morning & Afternoon ---
    day_start_time = fields.Float(
        string='Morning Start',
        digits=(12, 2),
        help="Format in hours (e.g., 8.00 for 08:00 AM, 8.50 for 08:30 AM)",
    )
    day_end_time = fields.Float(
        string='Morning End',
        digits=(12, 2),
        help="Format in hours (e.g., 12.00 for 12:00 PM, 13.00 for 01:00 PM)",
    )
    night_start_time = fields.Float(
        string='Afternoon Start',
        digits=(12, 2),
        help="Format in hours (e.g., 13.00 for 01:00 PM, 14.00 for 02:00 PM)",
    )
    night_end_time = fields.Float(
        string='Afternoon End',
        digits=(12, 2),
        help="Format in hours (e.g., 17.00 for 05:00 PM, 04.00 for 04:00 AM next day)",
    )

    # Computed shift hours (kept for internal totals & DB schema compatibility)
    day_total_hours = fields.Float(string='Morning Hours', compute='_compute_hours', store=True, digits=(12, 2))
    night_total_hours = fields.Float(string='Afternoon Hours', compute='_compute_hours', store=True, digits=(12, 2))

    # Single Total Hours adding from Morning Start to Afternoon End
    total_hours = fields.Float(
        string='Total',
        compute='_compute_hours',
        store=True,
        digits=(12, 2),
    )

    # --- Idle Tracking ---
    idle_time = fields.Float(
        string='Idle Time',
        digits=(12, 2),
        help="Idle time in hours (e.g., 1.50 for 1h 30m).",
    )
    idle_reason = fields.Char(
        string='Idle Reason',
        help="Reason for equipment idleness (e.g., Weather, Waiting for Material, Breakdown, Standby).",
    )

    # Legacy fields
    start_time = fields.Float(string='Start Time', digits=(12, 2))
    end_time = fields.Float(string='End Time', digits=(12, 2))

    # --- Fuel Tracking ---
    fuel_opening = fields.Float(
        string='Starting Fuel (L)',
        digits=(12, 2),
        help="Fuel at beginning of shift. Auto-filled from previous closing fuel for this equipment on this project, or entered manually.",
    )
    fuel_refueled = fields.Float(
        string='Fuel Refueled (L)',
        digits=(12, 2),
        help="Fuel refueled in Liters during shift.",
    )
    fuel_left = fields.Float(
        string='Fuel Left (Closing) (L)',
        digits=(12, 2),
        help="Remaining fuel in Liters at end of shift (from gauge or dipstick).",
    )
    fuel_consumed = fields.Float(
        string='Fuel Consumed (L)',
        compute='_compute_fuel_consumed',
        store=True,
        digits=(12, 2),
        help="Auto-calculated: Starting Fuel + Refueled - Fuel Left.",
    )

    description = fields.Char(string='Remarks / Notes')

    @api.onchange('equipment_id')
    def _onchange_equipment_id_fuel(self):
        """Auto-fill Starting Fuel from the previous shift's closing fuel (fuel_left) for this exact equipment on this project."""
        for record in self:
            if not record.equipment_id:
                continue

            # Project context
            project_id = record.project_id.id or (record.timesheet_id and record.timesheet_id.project_id.id) or self.env.context.get('default_project_id')

            # 1. First check if a preceding line in the current timesheet exists for the same equipment
            found_previous = False
            if record.timesheet_id and record.timesheet_id.line_ids:
                for sibling in record.timesheet_id.line_ids:
                    if sibling == record or (record._origin and sibling._origin == record._origin):
                        break
                    if sibling.equipment_id.id == record.equipment_id.id:
                        record.fuel_opening = sibling.fuel_left or 0.0
                        found_previous = True

            # 2. If not found in current timesheet, search the most recent previous line for this equipment & project
            if not found_previous:
                domain = [('equipment_id', '=', record.equipment_id.id)]
                if record._origin and record._origin.id:
                    domain.append(('id', '!=', record._origin.id))
                if project_id:
                    domain.append(('project_id', '=', project_id))

                prev_line = self.env['equipment.timesheet.line'].search(
                    domain,
                    order='date desc, id desc',
                    limit=1,
                )
                if prev_line:
                    record.fuel_opening = prev_line.fuel_left or 0.0
                else:
                    record.fuel_opening = 0.0

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if 'fuel_opening' not in vals or vals.get('fuel_opening') is None:
                eq_id = vals.get('equipment_id')
                ts_id = vals.get('timesheet_id')
                if eq_id:
                    project_id = False
                    if ts_id:
                        ts = self.env['equipment.timesheet'].browse(ts_id)
                        project_id = ts.project_id.id
                    domain = [('equipment_id', '=', eq_id)]
                    if project_id:
                        domain.append(('project_id', '=', project_id))
                    prev_line = self.search(domain, order='date desc, id desc', limit=1)
                    vals['fuel_opening'] = prev_line.fuel_left if prev_line else 0.0
        return super().create(vals_list)

    @api.depends('day_start_time', 'day_end_time', 'night_start_time', 'night_end_time', 'start_time', 'end_time')
    def _compute_hours(self):
        for record in self:
            m_start = record.day_start_time
            m_end = record.day_end_time
            a_start = record.night_start_time
            a_end = record.night_end_time

            # If user filled directly Morning Start and Afternoon End (continuous span)
            if m_start and a_end and not m_end and not a_start:
                if a_end >= m_start:
                    total = a_end - m_start
                else:
                    total = (24.0 - m_start) + a_end
                record.day_total_hours = total
                record.night_total_hours = 0.0
                record.total_hours = total
                continue

            morning_hours = 0.0
            if m_start or m_end:
                if m_end >= m_start:
                    morning_hours = m_end - m_start
                else:
                    morning_hours = (24.0 - m_start) + m_end

            afternoon_hours = 0.0
            if a_start or a_end:
                if a_end >= a_start:
                    afternoon_hours = a_end - a_start
                else:
                    afternoon_hours = (24.0 - a_start) + a_end

            total = morning_hours + afternoon_hours

            # Fallback if start_time / end_time were set
            if not total and (record.start_time or record.end_time):
                st = record.start_time
                et = record.end_time
                if et >= st:
                    total = et - st
                else:
                    total = (24.0 - st) + et

            record.day_total_hours = morning_hours
            record.night_total_hours = afternoon_hours
            record.total_hours = total

    @api.depends('fuel_opening', 'fuel_refueled', 'fuel_left')
    def _compute_fuel_consumed(self):
        for record in self:
            opening = record.fuel_opening or 0.0
            refueled = record.fuel_refueled or 0.0
            left = record.fuel_left or 0.0
            record.fuel_consumed = opening + refueled - left

    @api.constrains('start_time', 'end_time', 'day_start_time', 'day_end_time', 'night_start_time', 'night_end_time', 'idle_time')
    def _check_time_bounds(self):
        for record in self:
            for field_name in ['start_time', 'end_time', 'day_start_time', 'day_end_time', 'night_start_time', 'night_end_time', 'idle_time']:
                val = getattr(record, field_name, 0.0)
                if val and (val < 0.0 or val > 24.0):
                    raise ValidationError(_("Time values must be between 00:00 and 24:00."))

    @api.constrains('fuel_opening', 'fuel_refueled', 'fuel_left')
    def _check_fuel_values(self):
        for record in self:
            if record.fuel_opening < 0.0 or record.fuel_refueled < 0.0 or record.fuel_left < 0.0:
                raise ValidationError(_("Fuel values cannot be negative numbers."))
