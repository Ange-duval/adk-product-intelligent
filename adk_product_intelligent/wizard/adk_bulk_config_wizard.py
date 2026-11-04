# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import ValidationError


class AdkBulkConfigWizard(models.TransientModel):
    """Assistant permettant de configurer une famille, une catégorie, un code
    et des seuils de sécurité sur un lot d'articles filtrés (bien / service /
    catégorie / famille / nom), ou sur une sélection explicite faite depuis la
    vue liste des articles.
    """
    _name = 'adk.bulk.config.wizard'
    _description = "ADK - Configuration en lot des articles"

    # ------------------------------------------------------------------
    # Filtres de recherche
    # ------------------------------------------------------------------
    filter_type = fields.Selection([
        ('all', 'Tous les types'),
        ('consu', 'Biens'),
        ('service', 'Services'),
        ('combo', 'Combos'),
    ], default='all', string="Filtrer par type")
    filter_category_id = fields.Many2one('product.category', string="Filtrer par catégorie")
    filter_family_id = fields.Many2one('adk.product.family', string="Filtrer par famille")
    filter_no_family = fields.Boolean(string="Uniquement les articles sans famille")
    filter_name = fields.Char(string="Le nom contient")
    filter_active_only = fields.Boolean(default=True, string="Uniquement les articles actifs")

    product_ids = fields.Many2many('product.template', string="Articles concernés")
    product_count = fields.Integer(compute='_compute_product_count', string="Nb. articles sélectionnés")

    # ------------------------------------------------------------------
    # Valeurs à appliquer en lot
    # ------------------------------------------------------------------
    apply_family = fields.Boolean(string="Appliquer une famille")
    family_id = fields.Many2one('adk.product.family', string="Famille à appliquer")

    apply_category = fields.Boolean(string="Appliquer une catégorie")
    category_id = fields.Many2one('product.category', string="Catégorie à appliquer")

    apply_code = fields.Boolean(string="Générer les codes articles")
    use_as_reference = fields.Boolean(
        string="Reporter le code comme Référence interne", default=True,
        help="Le code généré est aussi écrit dans le champ natif « Référence interne » "
             "(default_code) de chaque article.")

    apply_seuils = fields.Boolean(string="Appliquer les seuils de sécurité")
    seuil_min = fields.Float(string="Seuil sécurité Min.")
    seuil_max = fields.Float(string="Seuil sécurité Max.")
    qty_multiple = fields.Float(string="Multiple de quantité", default=1.0)
    reordering_trigger = fields.Selection([
        ('auto', 'Automatique'), ('manual', 'Manuel'),
    ], default='auto', string="Déclenchement réappro.")
    warehouse_id = fields.Many2one('stock.warehouse', string="Entrepôt")

    apply_immobilisation = fields.Boolean(string="Appliquer le statut immobilisation")
    is_immobilisation = fields.Boolean(string="Marquer comme immobilisation")

    apply_comptes = fields.Boolean(string="Appliquer des comptes comptables")
    compte_achat_id = fields.Many2one('account.account', string="Compte d'achat")
    compte_vente_id = fields.Many2one('account.account', string="Compte de vente")
    compte_immobilisation_id = fields.Many2one('account.account', string="Compte immobilisation")

    result_message = fields.Html(string="Résultat", readonly=True)
    state = fields.Selection([('filter', 'Filtrer'), ('done', 'Terminé')], default='filter')

    @api.depends('product_ids')
    def _compute_product_count(self):
        for rec in self:
            rec.product_count = len(rec.product_ids)

    # ==================================================================
    # Actions
    # ==================================================================
    def action_search(self):
        self.ensure_one()
        domain = []
        if self.filter_type != 'all':
            domain.append(('type', '=', self.filter_type))
        if self.filter_category_id:
            domain.append(('categ_id', '=', self.filter_category_id.id))
        if self.filter_family_id:
            domain.append(('adk_family_id', '=', self.filter_family_id.id))
        if self.filter_no_family:
            domain.append(('adk_family_id', '=', False))
        if self.filter_name:
            domain.append(('name', 'ilike', self.filter_name))
        if not self.filter_active_only:
            domain.append(('active', 'in', [True, False]))

        products = self.env['product.template'].search(domain)
        self.product_ids = products
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'adk.bulk.config.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_apply(self):
        self.ensure_one()
        products = self.product_ids
        if not products:
            raise ValidationError(_(
                "Aucun article sélectionné. Utilisez le bouton « Rechercher » ou "
                "sélectionnez des articles depuis la vue liste avant de lancer cet assistant."))

        vals = {}
        if self.apply_family and self.family_id:
            vals['adk_family_id'] = self.family_id.id
        if self.apply_category and self.category_id:
            vals['categ_id'] = self.category_id.id
        if self.apply_seuils:
            vals.update({
                'adk_seuil_min': self.seuil_min,
                'adk_seuil_max': self.seuil_max,
                'adk_qty_multiple': self.qty_multiple or 1.0,
                'adk_reordering_trigger': self.reordering_trigger,
            })
            if self.warehouse_id:
                vals['adk_warehouse_id'] = self.warehouse_id.id
        if self.apply_immobilisation:
            vals['adk_is_immobilisation'] = self.is_immobilisation
        if self.apply_comptes:
            if self.compte_achat_id:
                vals['adk_compte_achat_id'] = self.compte_achat_id.id
            if self.compte_vente_id:
                vals['adk_compte_vente_id'] = self.compte_vente_id.id
            if self.compte_immobilisation_id:
                vals['adk_compte_immobilisation_id'] = self.compte_immobilisation_id.id

        if vals:
            products.write(vals)

        generated_codes = 0
        if self.apply_code:
            for product in products.sorted('id'):
                product.adk_use_as_reference = self.use_as_reference
                if product.adk_family_id and product.adk_family_id.sequence_id:
                    product.adk_code = product.adk_family_id.sequence_id.next_by_id()
                    generated_codes += 1

        # Force une synchronisation explicite (déjà déclenchée par write, mais on
        # s'assure ici que même les articles sans changement de champ suivi soient à jour).
        products._adk_sync_inventory()

        self.result_message = _(
            "<b>%s article(s)</b> mis à jour avec succès et synchronisés avec le module "
            "Inventaire.<br/>%s code(s) article généré(s)."
        ) % (len(products), generated_codes)
        self.state = 'done'

        return {
            'type': 'ir.actions.act_window',
            'res_model': 'adk.bulk.config.wizard',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
            'context': self.env.context,
        }

    def action_view_result_products(self):
        self.ensure_one()
        return {
            'name': _("Articles configurés"),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'list,form,kanban',
            'domain': [('id', 'in', self.product_ids.ids)],
        }
