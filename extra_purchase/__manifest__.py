# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Extra Purchase',
    'version': '1.0',
    'category': 'Purchase',
    'sequence': 15,
    'summary': 'Extra Purchase',
    'description': """Extra Purchase""",
    'website': 'https://www.odoo.com/page',
    'depends': ['purchase', 'extra_product', 'extra_partner', 'extra_invoice', 'stock', 'procurement', 'extra_sale'],
    'data': [
        'data/groups.xml',
        'views/set_partner_wizard_view.xml',
        'views/purchase_delivery_wizard_view.xml',
        'views/procurement_rule_view.xml',
        'views/make_po_wizard_view.xml',
        'views/purchase_view.xml',
        'data/stock_data.xml',
        'report/purchase_report.xml',
    ],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
