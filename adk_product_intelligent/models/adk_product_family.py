# -*- coding: utf-8 -*-
import re
import unicodedata

from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AdkProductFamily(models.Model):
    """Famille d'articles intelligente.

    Une famille ADK est toujours reliée à une catégorie produit native
    (product.category). Ainsi, toute configuration faite ici (type, comptes,
    seuils par défaut...) reste 100% visible et cohérente avec le module
    Inventaire natif, sans aucune duplication de données.
    """
    _name = 'adk.product.family'
    _description = "Famille d'Articles Intelligente (ADK)"
    _order = 'sequence, name'

    name = fields.Char(string="Nom de la famille", required=True, translate=True)
    code = fields.Char(
        string="Code", copy=False, size=6, required=True,
        help="Code court (2 à 6 caractères) qui préfixe les codes articles : ELEC → ELEC-0001.")
    sequence = fields.Integer(default=10)
    active = fields.Boolean(default=True)
    color = fields.Integer(string="Couleur")
    company_id = fields.Many2one('res.company', string="Société", default=lambda self: self.env.company)

    product_category_id = fields.Many2one(
        'product.category', string="Catégorie Inventaire liée",
        help="Catégorie produit native Odoo associée à cette famille. "
             "Garantit la synchronisation totale avec le module Inventaire.")

    type = fields.Selection([
        ('consu', 'Bien (stockable / consommable)'),
        ('service', 'Service'),
        ('combo', 'Combo'),
    ], string="Type d'article", default='consu', required=True)

    is_storable = fields.Boolean(
        string="Suivi en stock", default=True,
        help="Si coché, les articles de cette famille sont suivis en inventaire "
             "(quantités, emplacements, seuils de sécurité).")

    # ------------------------------------------------------------------
    # Seuils de sécurité par défaut (proposés lors de l'application en lot)
    # ------------------------------------------------------------------
    default_seuil_min = fields.Float(string="Seuil sécurité Min. par défaut")
    default_seuil_max = fields.Float(string="Seuil sécurité Max. par défaut")
    default_qty_multiple = fields.Float(string="Multiple de quantité", default=1.0)
    reordering_trigger = fields.Selection([
        ('auto', 'Automatique'),
        ('manual', 'Manuel'),
    ], default='auto', string="Déclenchement réappro.")
    default_warehouse_id = fields.Many2one('stock.warehouse', string="Entrepôt par défaut")

    # ------------------------------------------------------------------
    # Comptabilité / Immobilisations
    # ------------------------------------------------------------------
    is_immobilisation = fields.Boolean(string="Famille d'immobilisations")
    compte_achat_id = fields.Many2one('account.account', string="Compte d'achat / charge")
    compte_vente_id = fields.Many2one('account.account', string="Compte de vente / produit")
    compte_immobilisation_id = fields.Many2one('account.account', string="Compte d'immobilisation")

    # ------------------------------------------------------------------
    # Codification
    # ------------------------------------------------------------------
    sequence_id = fields.Many2one('ir.sequence', string="Séquence code article", copy=False, readonly=True)
    use_code_as_reference = fields.Boolean(
        string="Utiliser le code ADK comme Référence interne", default=True,
        help="Si coché, le code ADK généré est aussi reporté dans le champ natif "
             "« Référence interne » (default_code) visible dans l'onglet Informations "
             "générales de l'article, et donc utilisable partout dans Odoo (achats, "
             "ventes, code-barres composé, imports...).")

    product_ids = fields.One2many('product.template', 'adk_family_id', string="Articles de la famille")
    product_count = fields.Integer(compute='_compute_product_count', string="Nb. articles")

    notes = fields.Html(string="Notes")

    _sql_constraints = [
        ('code_uniq', 'unique(code, company_id)', "Le code de famille doit être unique par société !"),
    ]

    @api.depends('product_ids')
    def _compute_product_count(self):
        for rec in self:
            rec.product_count = len(rec.product_ids)

    @api.onchange('name')
    def _onchange_name_suggest_code(self):
        if self.name and not self.code:
            self.code = self._suggest_code(self.name)

    @api.model
    def _suggest_code(self, name, company=None):
        """Code court en majuscules (3 à 5 lettres) tiré du nom, rendu unique si besoin."""
        letters = re.sub(r'[^A-Z0-9]', '', unicodedata.normalize('NFKD', name or '').encode('ascii', 'ignore').decode().upper())
        base = (letters[:4] or 'FAM')
        company = company or self.env.company
        code, n = base, 1
        while self.with_context(active_test=False).search_count([('code', '=', code), ('company_id', '=', company.id)]):
            n += 1
            code = '%s%d' % (base[:5 if n < 10 else 4], n)
        return code

    @api.constrains('code')
    def _check_code_format(self):
        for rec in self:
            if not re.fullmatch(r'[A-Z0-9]{2,6}', rec.code or ''):
                raise ValidationError(_("Le code doit contenir 2 à 6 lettres ou chiffres, sans espace (ex : ELEC)."))

    @api.model_create_multi
    def create(self, vals_list):
        Category = self.env['product.category']
        for vals in vals_list:
            company = self.env['res.company'].browse(vals['company_id']) if vals.get('company_id') else self.env.company
            vals['code'] = (vals.get('code') or '').strip().upper() or self._suggest_code(vals.get('name'), company)
            if not vals.get('product_category_id'):
                categ = Category.search([('name', '=', vals.get('name'))], limit=1)
                vals['product_category_id'] = (categ or Category.create({'name': vals.get('name')})).id
        families = super().create(vals_list)
        for family in families:
            family.sequence_id = self.env['ir.sequence'].sudo().create({
                'name': _("Articles %s", family.code),
                'code': 'adk.product.family.articles.%s' % family.id,
                'prefix': family.code + '-',
                'padding': 4,
                'number_increment': 1,
                'company_id': family.company_id.id,
            })
        return families

    def write(self, vals):
        if vals.get('code'):
            vals['code'] = vals['code'].strip().upper()
        res = super().write(vals)
        if 'code' in vals:
            for family in self.filtered('sequence_id'):
                family.sequence_id.sudo().prefix = family.code + '-'
        return res

    def action_view_products(self):
        self.ensure_one()
        return {
            'name': _("Articles de la famille %s") % self.name,
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'list,form,kanban',
            'domain': [('adk_family_id', '=', self.id)],
            'context': {
                'default_adk_family_id': self.id,
                'default_categ_id': self.product_category_id.id,
                'default_type': self.type,
            },
        }

    def action_generate_next_code(self):
        """Retourne le prochain code disponible pour cette famille sans le consommer réellement."""
        self.ensure_one()
        if not self.sequence_id:
            raise ValidationError(_("Aucune séquence de codification n'est définie pour cette famille."))
        return self.sequence_id.next_by_id()
