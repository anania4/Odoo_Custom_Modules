from odoo import models, fields


class MefsBoqWorkType(models.Model):
    _name = 'mefs.boq.work.type'
    _description = 'BOQ Work Type'
    _order = 'sequence, name'

    name = fields.Char(string='Work Type', required=True)
    code = fields.Char(string='Code', required=True, help='Code used in work item code prefix, e.g. ANCHOR, PILE, GROUT')
    sequence = fields.Integer(string='Sequence', default=10)
    description = fields.Text(string='Description')
    active = fields.Boolean(string='Active', default=True)
