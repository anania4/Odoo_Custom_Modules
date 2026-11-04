from odoo import api, fields, models


class MefsBudgetEstimateLine(models.Model):
    _name = 'mefs.budget.estimate.line'
    _description = 'Project Estimated Cost Line'
    _order = 'sequence, id'

    sequence = fields.Integer(default=10)
    plan_id = fields.Many2one(
        'mefs.budget.plan', string='Budget Plan', required=True, ondelete='cascade')
    currency_id = fields.Many2one(related='plan_id.currency_id')

    # --- Work item (from BOQ) ---
    boq_line_id = fields.Many2one(
        'mefs.boq.line', string='Item No', required=True,
        domain="[('boq_id', '=', parent.boq_id), ('display_type', '!=', 'line_note'), ('is_subtotal', '=', False)]")
    work_item = fields.Char(related='boq_line_id.name', string='Work Item')
    work_duration_days = fields.Float(string='Duration of Work (Days)')
    work_quantity = fields.Float(string='Quantity of Work')
    work_uom_id = fields.Many2one(related='boq_line_id.uom_id', string='Unit')

    # --- Material ---
    material_product_id = fields.Many2one('product.product', string='Material Type')
    material_uom_id = fields.Many2one(
        related='material_product_id.uom_id', string='Material Unit')
    material_consumption = fields.Float(
        string='Material Consumption per Unit', digits='Product Unit of Measure')
    material_unit_price = fields.Monetary(
        string='Unit Price of Material', compute='_compute_material_unit_price',
        store=True, readonly=False)
    material_price_per_work_unit = fields.Monetary(
        string='Price per Unit Work', compute='_compute_costs', store=True)
    total_material_cost = fields.Monetary(
        string='Total Material Cost', compute='_compute_costs', store=True)
    material_categ_id = fields.Many2one(
        'product.category', string='Material Class')

    # --- Equipment ---
    equipment_product_id = fields.Many2one('product.product', string='Equipment Type')
    equipment_count = fields.Integer(string='No of Equipment Deployed')
    equipment_output = fields.Float(string='Equipment Output')
    equipment_rate_hour = fields.Monetary(string='Equipment Rental Cost per Hr')
    equipment_rental_hours = fields.Float(string='Duration of Rental (Hr)')
    total_equipment_cost = fields.Monetary(
        string='Total Equipment Cost', compute='_compute_costs', store=True)
    equipment_categ_id = fields.Many2one(
        'product.category', string='Equipment Class')

    # --- Manpower ---
    manpower_product_id = fields.Many2one('product.product', string='Manpower Type')
    manpower_count = fields.Integer(string='No of Manpower Deployed')
    manpower_price_day = fields.Monetary(string='Price per Day')
    total_manpower_cost = fields.Monetary(
        string='Total Manpower Cost', compute='_compute_costs', store=True)
    labour_categ_id = fields.Many2one(
        'product.category', string='Labour Class')

    # --- Subcontractor ---
    subcontract_cost_unit = fields.Monetary(string='Subcontractor Cost per Unit')
    total_subcontractor_cost = fields.Monetary(
        string='Total Subcontractor Cost', compute='_compute_costs', store=True)
    subcontract_categ_id = fields.Many2one(
        'product.category', string='Subcontracting Class')

    @api.depends('material_product_id')
    def _compute_material_unit_price(self):
        for line in self:
            line.material_unit_price = line.material_product_id.standard_price

    @api.depends(
        'work_quantity', 'work_duration_days',
        'material_consumption', 'material_unit_price',
        'equipment_rate_hour', 'equipment_rental_hours', 'equipment_count',
        'manpower_count', 'manpower_price_day',
        'subcontract_cost_unit')
    def _compute_costs(self):
        for line in self:
            line.material_price_per_work_unit = line.material_consumption * line.material_unit_price
            line.total_material_cost = line.material_price_per_work_unit * line.work_quantity
            line.total_equipment_cost = (
                line.equipment_rate_hour * line.equipment_rental_hours * line.equipment_count)
            line.total_manpower_cost = (
                line.work_duration_days * line.manpower_count * line.manpower_price_day)
            line.total_subcontractor_cost = line.subcontract_cost_unit * line.work_quantity

    def action_add_material_row(self):
        """Insert another row for the same work item to add one more material."""
        self.ensure_one()
        self.copy({
            'plan_id': self.plan_id.id,
            'sequence': self.sequence,
            'boq_line_id': self.boq_line_id.id,
            'work_duration_days': self.work_duration_days,
            'work_quantity': self.work_quantity,
            'material_product_id': False,
            'material_consumption': 0.0,
            'material_unit_price': 0.0,
            'equipment_product_id': False,
            'equipment_count': 0,
            'equipment_output': 0.0,
            'equipment_rate_hour': 0.0,
            'equipment_rental_hours': 0.0,
            'manpower_product_id': False,
            'manpower_count': 0,
            'manpower_price_day': 0.0,
            'subcontract_cost_unit': 0.0,
            'subcontract_categ_id': False,
            'material_categ_id': False,
            'equipment_categ_id': False,
            'labour_categ_id': False,
        })
        return True

    def _compute_display_name(self):
        for line in self:
            line.display_name = line.boq_line_id.display_name or ''
