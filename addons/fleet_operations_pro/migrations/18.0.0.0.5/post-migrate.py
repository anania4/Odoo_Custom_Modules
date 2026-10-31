# -*- coding: utf-8 -*-
"""Toll locations were removed: drop the model, its table and the columns on toll records."""

from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    if not version:
        return
    env = api.Environment(cr, SUPERUSER_ID, {})
    cr.execute("ALTER TABLE fleet_toll_record DROP COLUMN IF EXISTS toll_location_id")
    cr.execute("ALTER TABLE fleet_toll_record DROP COLUMN IF EXISTS location_description")
    env['ir.model.fields'].search([
        ('model', '=', 'fleet.toll.record'),
        ('name', 'in', ('toll_location_id', 'location_description')),
    ]).with_context(_force_unlink=True).unlink()
    env['ir.model'].search([('model', '=', 'fleet.toll.location')]).with_context(_force_unlink=True).unlink()
    cr.execute("DROP TABLE IF EXISTS fleet_toll_location CASCADE")
