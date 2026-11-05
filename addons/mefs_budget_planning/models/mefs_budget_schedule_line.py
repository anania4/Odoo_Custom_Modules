from datetime import timedelta

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class MefsBudgetScheduleLine(models.Model):
    _name = 'mefs.budget.schedule.line'
    _description = 'Project Schedule Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    plan_id = fields.Many2one(
        'mefs.budget.plan', string='Budget Plan', required=True, ondelete='cascade')

    boq_line_id = fields.Many2one(
        'mefs.boq.line', string='Item No', required=True,
        domain="[('boq_id', '=', parent.boq_id), ('display_type', '!=', 'line_note'), ('is_subtotal', '=', False)]")
    task = fields.Char(related='boq_line_id.name', string='Task')
    quantity = fields.Float(string='Quantity')
    uom_id = fields.Many2one(related='boq_line_id.uom_id', string='Unit')
    progress = fields.Float(string='Progress (%)')
    date_start = fields.Date(string='Start')
    duration_days = fields.Integer(string='Duration (Days)')
    applied_duration_days = fields.Integer(
        string='Applied Duration', copy=False,
        help='Technical: last duration already reflected in the following tasks. '
             'Used to shift the following tasks when the duration changes.')
    date_end = fields.Date(
        string='End', compute='_compute_date_end', store=True,
        help='Start + Duration - 1: a 1-day task starts and ends on the same day.')

    @api.depends('date_start', 'duration_days')
    def _compute_date_end(self):
        for line in self:
            if line.date_start and line.duration_days > 0:
                line.date_end = line.date_start + timedelta(days=line.duration_days - 1)
            else:
                line.date_end = False

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.setdefault('applied_duration_days', vals.get('duration_days', 0))
        return super().create(vals_list)

    def write(self, vals):
        # Writes outside the form (imports, code) take the new duration as-is.
        if 'duration_days' in vals and 'applied_duration_days' not in vals:
            vals = dict(vals, applied_duration_days=vals['duration_days'])
        return super().write(vals)

    @api.constrains('progress')
    def _check_progress(self):
        for line in self:
            if not 0 <= line.progress <= 100:
                raise ValidationError(_('Progress must be between 0 and 100 %.'))

    @api.constrains('duration_days')
    def _check_duration(self):
        for line in self:
            if line.duration_days < 0:
                raise ValidationError(_('Duration cannot be negative.'))
