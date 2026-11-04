# -*- coding: utf-8 -*-
{
    'name': "ADK Familles & Codes Articles",
    'version': '18.0.2.0.0',
    'category': 'Inventory/Inventory',
    'summary': "Gestion intelligente des familles d'articles, codes, catégories et seuils de sécurité — 100% synchronisé avec l'Inventaire et la Comptabilité",
    'description': """
ADK - Module Produits Intelligent
==================================

Ce module ajoute une couche de gestion intelligente au-dessus des Articles (product.template) d'Odoo :

Fonctionnalités principales
----------------------------
* Définition de **Familles d'articles** (Biens, Services, Combos) reliées directement aux
  Catégories produit natives d'Odoo -> tout ce qui est configuré ici apparaît immédiatement
  dans le module Inventaire (aucune duplication de données).
* Attribution des familles, codes et catégories **un par un** (fiche article) ou
  **en lot** via un assistant de configuration massive avec filtres avancés
  (type d'article : bien / service / combo, catégorie, famille, nom...).
* Génération automatique de **codes articles courts** (CODE-0001) via une séquence par famille.
* Définition des **seuils de sécurité** (stock min / stock max / multiple de commande),
  individuellement ou en lot, avec **synchronisation automatique et bidirectionnelle**
  vers les **Règles de réapprovisionnement** natives du module Inventaire
  (stock.warehouse.orderpoint) : dès qu'un seuil est modifié ici, il est immédiatement
  visible dans Inventaire > Réapprovisionnement, et inversement rien n'est dupliqué.
* Gestion des **immobilisations** : marquage d'un article ou d'une famille entière comme
  immobilisation, avec comptes d'achat / vente / immobilisation dédiés, synchronisés avec
  les comptes comptables natifs de l'article (property_account_expense_id /
  property_account_income_id) utilisés par les modules Achat / Vente / Comptabilité.
* Tableau de bord des familles avec compteur d'articles, statut de synchronisation
  inventaire et accès direct aux règles de réapprovisionnement générées.
* Codes courts et lisibles : famille « ELEC » → articles ELEC-0001, ELEC-0002…

Aucune donnée n'est dupliquée : le module travaille directement sur les modèles natifs
product.template, product.category, stock.warehouse.orderpoint et account.account, ce qui
garantit une synchronisation totale et instantanée avec le module Inventaire natif.
    """,
    'author': 'Kambeu Henang Ange Duval',
    'website': '',
    'license': 'LGPL-3',
    'depends': ['product', 'stock', 'account'],
    'data': [
        'security/ir.model.access.csv',
        'views/adk_family_views.xml',
        'views/product_category_views.xml',
        'views/product_template_views.xml',
        'wizard/adk_bulk_config_wizard_views.xml',
        'views/adk_menus.xml',
    ],
    'images': ['static/description/banner.png'],
    'installable': True,
    'application': True,
    'auto_install': False,
}
