# -*- coding: utf-8 -*-
from odoo import models, fields, api, _
from odoo.exceptions import UserError

ADK_SYNC_FIELDS = [
    'adk_family_id', 'adk_seuil_min', 'adk_seuil_max', 'adk_qty_multiple',
    'adk_reordering_trigger', 'adk_warehouse_id', 'adk_location_id',
    'adk_is_immobilisation', 'adk_compte_achat_id', 'adk_compte_vente_id',
    'adk_compte_immobilisation_id', 'type', 'adk_code', 'adk_use_as_reference',
]


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    # ------------------------------------------------------------------
    # Famille / Codification
    # ------------------------------------------------------------------
    adk_family_id = fields.Many2one(
        'adk.product.family', string="Famille ADK",
        help="Famille d'articles intelligente. Détermine la catégorie, le type, "
             "les comptes et les seuils de sécurité par défaut.")
    adk_code = fields.Char(string="Code article ADK", copy=False)
    adk_use_as_reference = fields.Boolean(
        string="Utiliser comme Référence interne", default=True,
        help="Reporte automatiquement le code ADK dans le champ natif « Référence interne » "
             "(default_code), visible dans l'onglet Informations générales de l'article.")

    # ------------------------------------------------------------------
    # Seuils de sécurité (synchronisés avec stock.warehouse.orderpoint)
    # ------------------------------------------------------------------
    adk_seuil_min = fields.Float(
        string="Seuil sécurité Min.",
        help="Quantité minimale avant déclenchement du réapprovisionnement. "
             "Synchronisé automatiquement avec les Règles de réapprovisionnement du module Inventaire.")
    adk_seuil_max = fields.Float(string="Seuil sécurité Max.")
    adk_qty_multiple = fields.Float(string="Multiple de quantité", default=1.0)
    adk_reordering_trigger = fields.Selection([
        ('auto', 'Automatique'),
        ('manual', 'Manuel'),
    ], default='auto', string="Déclenchement réappro.")
    adk_warehouse_id = fields.Many2one(
        'stock.warehouse', string="Entrepôt (seuils)",
        default=lambda self: self.env['stock.warehouse'].search(
            [('company_id', '=', self.env.company.id)], limit=1))
    adk_location_id = fields.Many2one('stock.location', string="Emplacement (seuils)")

    adk_orderpoint_ids = fields.Many2many(
        'stock.warehouse.orderpoint', compute='_compute_adk_orderpoint_ids',
        string="Règles de réapprovisionnement liées")
    adk_orderpoint_count = fields.Integer(compute='_compute_adk_orderpoint_ids', string="Nb. règles réappro.")

    # ------------------------------------------------------------------
    # Alerte visuelle de seuil (liste / kanban, Inventaire & ADK)
    # ------------------------------------------------------------------
    adk_stock_alert = fields.Boolean(
        string="Alerte seuil atteint", compute='_compute_adk_stock_alert', search='_search_adk_stock_alert',
        help="Vrai si la quantité disponible est inférieure ou égale au seuil de sécurité Min.")
    adk_stock_alert_label = fields.Char(string="Libellé alerte stock", compute='_compute_adk_stock_alert')

    # ------------------------------------------------------------------
    # Comptabilité / Immobilisations
    # ------------------------------------------------------------------
    adk_is_immobilisation = fields.Boolean(string="Immobilisation")
    adk_compte_achat_id = fields.Many2one('account.account', string="Compte d'achat / charge")
    adk_compte_vente_id = fields.Many2one('account.account', string="Compte de vente / produit")
    adk_compte_immobilisation_id = fields.Many2one('account.account', string="Compte d'immobilisation")

    adk_sync_state = fields.Selection([
        ('synced', 'Synchronisé avec Inventaire'),
        ('pending', 'En attente de synchronisation'),
        ('error', 'Erreur de synchronisation'),
    ], string="État synchro ADK", default='pending', copy=False)
    adk_last_sync = fields.Datetime(string="Dernière synchro", copy=False)

    # ==================================================================
    # Compute
    # ==================================================================
    def _compute_adk_orderpoint_ids(self):
        Orderpoint = self.env['stock.warehouse.orderpoint']
        for tmpl in self:
            variant_ids = tmpl.product_variant_ids.ids
            orderpoints = Orderpoint.search([('product_id', 'in', variant_ids)]) if variant_ids else Orderpoint
            tmpl.adk_orderpoint_ids = orderpoints
            tmpl.adk_orderpoint_count = len(orderpoints)

    @api.depends('qty_available', 'adk_seuil_min', 'type')
    def _compute_adk_stock_alert(self):
        for tmpl in self:
            is_storable_type = tmpl.type == 'consu' and getattr(tmpl, 'is_storable', True)
            qty = tmpl.qty_available if is_storable_type else 0.0
            if is_storable_type and tmpl.adk_seuil_min and qty <= tmpl.adk_seuil_min:
                tmpl.adk_stock_alert = True
                tmpl.adk_stock_alert_label = _("⚠ Seuil min. atteint (%s en stock)") % qty
            else:
                tmpl.adk_stock_alert = False
                tmpl.adk_stock_alert_label = False

    @api.model
    def _search_adk_stock_alert(self, operator, value):
        want_true = (operator == '=' and value) or (operator == '!=' and not value)
        candidates = self.search([('adk_seuil_min', '>', 0), ('type', '=', 'consu')])
        alert_ids = candidates.filtered(lambda p: p.adk_stock_alert).ids
        return [('id', 'in' if want_true else 'not in', alert_ids)]

    @api.model
    def action_view_adk_stock_alerts(self):
        """Retourne la liste (kanban/liste) de tous les articles actuellement en alerte
        de seuil de sécurité, tous types confondus. Utilisée par le menu ADK dédié."""
        candidates = self.search([('adk_seuil_min', '>', 0)])
        alert_products = candidates.filtered(lambda p: p.adk_stock_alert)
        return {
            'name': _("Alertes de seuil de stock"),
            'type': 'ir.actions.act_window',
            'res_model': 'product.template',
            'view_mode': 'list,kanban,form',
            'domain': [('id', 'in', alert_products.ids)],
            'context': dict(self.env.context, search_default_adk_filter_alert=1),
        }

    # ==================================================================
    # Onchange
    # ==================================================================
    @api.onchange('adk_family_id')
    def _onchange_adk_family_id(self):
        for tmpl in self:
            family = tmpl.adk_family_id
            if not family:
                continue
            tmpl.categ_id = family.product_category_id
            tmpl.type = family.type
            if hasattr(tmpl, 'is_storable'):
                tmpl.is_storable = family.is_storable and family.type == 'consu'
            if not tmpl.adk_seuil_min:
                tmpl.adk_seuil_min = family.default_seuil_min
            if not tmpl.adk_seuil_max:
                tmpl.adk_seuil_max = family.default_seuil_max
            tmpl.adk_qty_multiple = family.default_qty_multiple or 1.0
            tmpl.adk_reordering_trigger = family.reordering_trigger
            tmpl.adk_use_as_reference = family.use_code_as_reference
            if family.default_warehouse_id:
                tmpl.adk_warehouse_id = family.default_warehouse_id
            tmpl.adk_is_immobilisation = family.is_immobilisation
            if family.compte_achat_id:
                tmpl.adk_compte_achat_id = family.compte_achat_id
            if family.compte_vente_id:
                tmpl.adk_compte_vente_id = family.compte_vente_id
            if family.compte_immobilisation_id:
                tmpl.adk_compte_immobilisation_id = family.compte_immobilisation_id

    # ==================================================================
    # CRUD
    # ==================================================================
    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            family = None
            if vals.get('adk_family_id'):
                family = self.env['adk.product.family'].browse(vals['adk_family_id'])
            if family and family.sequence_id and not vals.get('adk_code'):
                vals['adk_code'] = family.sequence_id.next_by_id()
        templates = super().create(vals_list)
        templates.filtered(lambda t: t.adk_family_id or t.adk_seuil_min or t.adk_seuil_max)._adk_sync_inventory()
        return templates

    def write(self, vals):
        res = super().write(vals)
        if vals.get('adk_family_id') and 'adk_code' not in vals:
            for tmpl in self.filtered(lambda t: not t.adk_code and t.adk_family_id.sequence_id):
                tmpl.adk_code = tmpl.adk_family_id.sequence_id.next_by_id()
        if any(f in vals for f in ADK_SYNC_FIELDS):
            self._adk_sync_inventory()
        return res

    # ==================================================================
    # Synchronisation Inventaire / Comptabilité
    # ==================================================================
    def _adk_sync_inventory(self):
        """Synchronise famille / seuils / comptes avec les modèles natifs
        product.category, stock.warehouse.orderpoint et les comptes de l'article.
        Aucune donnée n'est dupliquée : on écrit directement sur les modèles Odoo natifs
        afin que le module Inventaire affiche instantanément la configuration faite ici.
        """
        Orderpoint = self.env['stock.warehouse.orderpoint']
        for tmpl in self:
            try:
                family = tmpl.adk_family_id

                # 1) Cohérence catégorie / type avec la famille
                if family and tmpl.categ_id != family.product_category_id:
                    tmpl.categ_id = family.product_category_id

                # 1bis) Code ADK reporté sur le champ natif "Référence interne" (default_code),
                #      visible dans l'onglet Informations générales : un champ renseigné dans
                #      ADK doit se refléter sur les autres onglets natifs concernés.
                if tmpl.adk_use_as_reference and tmpl.adk_code and tmpl.default_code != tmpl.adk_code:
                    tmpl.default_code = tmpl.adk_code

                # 2) Comptes comptables (achat / vente) répercutés sur les comptes natifs
                compte_achat = tmpl.adk_compte_achat_id or (family.compte_achat_id if family else False)
                compte_vente = tmpl.adk_compte_vente_id or (family.compte_vente_id if family else False)
                if compte_achat and hasattr(tmpl, 'property_account_expense_id'):
                    tmpl.property_account_expense_id = compte_achat
                if compte_vente and hasattr(tmpl, 'property_account_income_id'):
                    tmpl.property_account_income_id = compte_vente

                # 3) Immobilisation : si activée, le compte d'immobilisation prime sur le
                #    compte de charge classique pour le débit à l'achat.
                is_immo = tmpl.adk_is_immobilisation or (family.is_immobilisation if family else False)
                compte_immo = tmpl.adk_compte_immobilisation_id or (family.compte_immobilisation_id if family else False)
                if is_immo and compte_immo and hasattr(tmpl, 'property_account_expense_id'):
                    tmpl.property_account_expense_id = compte_immo

                # 4) Seuils de sécurité -> Règles de réapprovisionnement natives
                is_storable_type = tmpl.type == 'consu' and getattr(tmpl, 'is_storable', True)
                if is_storable_type and (tmpl.adk_seuil_min or tmpl.adk_seuil_max):
                    warehouse = tmpl.adk_warehouse_id or self.env['stock.warehouse'].search(
                        [('company_id', '=', tmpl.company_id.id or self.env.company.id)], limit=1)
                    location = tmpl.adk_location_id or (warehouse.lot_stock_id if warehouse else False)
                    for variant in tmpl.product_variant_ids:
                        domain = [('product_id', '=', variant.id)]
                        if warehouse:
                            domain.append(('warehouse_id', '=', warehouse.id))
                        orderpoint = Orderpoint.search(domain, limit=1)
                        op_vals = {
                            'product_min_qty': tmpl.adk_seuil_min,
                            'product_max_qty': tmpl.adk_seuil_max,
                            'qty_multiple': tmpl.adk_qty_multiple or 1.0,
                            'trigger': tmpl.adk_reordering_trigger or 'auto',
                        }
                        if orderpoint:
                            orderpoint.write(op_vals)
                        else:
                            op_vals.update({
                                'name': _("Seuil ADK - %s") % (tmpl.adk_code or tmpl.name),
                                'product_id': variant.id,
                                'warehouse_id': warehouse.id if warehouse else False,
                                'location_id': location.id if location else False,
                                'company_id': tmpl.company_id.id or self.env.company.id,
                            })
                            Orderpoint.create(op_vals)

                tmpl.adk_sync_state = 'synced'
                tmpl.adk_last_sync = fields.Datetime.now()
            except Exception as exc:  # noqa: BLE001 - on trace l'erreur sans bloquer l'utilisateur
                tmpl.adk_sync_state = 'error'
                tmpl.message_post(body=_("Erreur de synchronisation ADK : %s") % exc)

    def action_adk_sync_inventory(self):
        self._adk_sync_inventory()
        return True

    def action_view_adk_orderpoints(self):
        self.ensure_one()
        return {
            'name': _("Règles de réapprovisionnement"),
            'type': 'ir.actions.act_window',
            'res_model': 'stock.warehouse.orderpoint',
            'view_mode': 'list,form',
            'domain': [('id', 'in', self.adk_orderpoint_ids.ids)],
        }

    def action_adk_generate_code(self):
        for tmpl in self:
            if not tmpl.adk_family_id:
                raise UserError(_("Veuillez d'abord définir une famille ADK pour générer un code."))
            if not tmpl.adk_family_id.sequence_id:
                raise UserError(_("La famille sélectionnée n'a pas de séquence de codification."))
            tmpl.adk_code = tmpl.adk_family_id.sequence_id.next_by_id()
        return True
