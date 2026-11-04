from odoo.tests import TransactionCase, tagged
from odoo.exceptions import ValidationError


@tagged('post_install', '-at_install')
class TestFamily(TransactionCase):
    def test_short_codes(self):
        fam = self.env['adk.product.family'].create({'name': 'Électricité'})
        self.assertEqual(fam.code, 'ELEC')
        self.assertTrue(fam.product_category_id)
        fam2 = self.env['adk.product.family'].create({'name': 'Electrique'})
        self.assertEqual(fam2.code, 'ELEC2')
        p = self.env['product.template'].create({'name': 'Câble', 'adk_family_id': fam.id})
        p2 = self.env['product.template'].create({'name': 'Prise', 'adk_family_id': fam.id})
        self.assertEqual(p.adk_code, 'ELEC-0001')
        self.assertEqual(p2.adk_code, 'ELEC-0002')
        self.assertEqual(p.default_code, 'ELEC-0001')
        self.assertEqual(p.categ_id, fam.product_category_id)

    def test_code_rename_and_assign(self):
        fam = self.env['adk.product.family'].create({'name': 'Outils', 'code': 'out'})
        self.assertEqual(fam.code, 'OUT')
        fam.code = 'tool'
        p = self.env['product.template'].create({'name': 'Marteau'})
        p.adk_family_id = fam
        self.assertEqual(p.adk_code, 'TOOL-0001')
        with self.assertRaises(ValidationError):
            fam.code = 'bad code!'

    def test_thresholds_sync(self):
        fam = self.env['adk.product.family'].create({'name': 'Bureau'})
        p = self.env['product.template'].create({'name': 'Stylo', 'adk_family_id': fam.id, 'is_storable': True,
                                                 'adk_seuil_min': 5, 'adk_seuil_max': 20})
        op = self.env['stock.warehouse.orderpoint'].search([('product_id', '=', p.product_variant_id.id)])
        self.assertEqual((op.product_min_qty, op.product_max_qty), (5, 20))
