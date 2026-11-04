# -*- coding: utf-8 -*-
from odoo import models, fields, api


class ProductCategory(models.Model):
    _inherit = 'product.category'

    adk_family_ids = fields.One2many(
        'adk.product.family', 'product_category_id', string="Familles ADK liées")
    adk_family_count = fields.Integer(compute='_compute_adk_family_count', string="Nb. familles ADK")

    @api.depends('adk_family_ids')
    def _compute_adk_family_count(self):
        for rec in self:
            rec.adk_family_count = len(rec.adk_family_ids)

    def action_view_adk_families(self):
        self.ensure_one()
        return {
            'name': "Familles ADK",
            'type': 'ir.actions.act_window',
            'res_model': 'adk.product.family',
            'view_mode': 'list,form',
            'domain': [('product_category_id', '=', self.id)],
            'context': {'default_product_category_id': self.id},
        }
