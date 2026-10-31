# Copyright 2019 Creu Blanca
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import api, fields, models

SEQUENCE_PREFIX = "%(range_year)s"


class MaintenanceTeam(models.Model):
    _inherit = "maintenance.team"

    code_prefix = fields.Char(
        string="Prefix for Team Reference",
        help="Prefix used to generate the internal reference for re "
        "created with this category. If blank the "
        "default sequence will be used.",
    )
    sequence_id = fields.Many2one(
        comodel_name="ir.sequence",
        string="Team Sequence",
        copy=False,
        readonly=True,
    )

    @api.model
    def _get_sequence_prefix(self, prefix):
        """Build the sequence prefix from the team prefix.

        The year is appended automatically so references look like
        ``PREFIX/2026/00001`` and restart every year, like standard Odoo
        sequences.
        """
        return "%s/%s/" % ((prefix or "").strip().rstrip("/"), SEQUENCE_PREFIX)

    @api.model
    def _prepare_ir_sequence(self, prefix):
        """Prepare the vals for creating the sequence
        :param prefix: a string with the prefix of the sequence.
        :return: a dict with the values.
        """
        code_prefix = (prefix or "").strip().rstrip("/")
        vals = {
            "name": "Maintenance Request " + code_prefix,
            "code": "maintenance.request - " + code_prefix,
            "padding": 5,
            "prefix": self._get_sequence_prefix(code_prefix),
            "use_date_range": True,
            "implementation": "standard",
            "company_id": False,
        }
        return vals

    def write(self, vals):
        prefix = vals.get("code_prefix")
        if prefix:
            for rec in self:
                if rec.sequence_id:
                    rec.sudo().sequence_id.write(
                        {
                            "prefix": self._get_sequence_prefix(prefix),
                            "use_date_range": True,
                        }
                    )
                else:
                    seq_vals = self._prepare_ir_sequence(prefix)
                    rec.sequence_id = self.env["ir.sequence"].create(seq_vals)
        return super().write(vals)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            prefix = vals.get("code_prefix")
            if prefix:
                seq_vals = self._prepare_ir_sequence(prefix)
                sequence = self.env["ir.sequence"].create(seq_vals)
                vals["sequence_id"] = sequence.id
        return super().create(vals_list)
