# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Extra Quotation',
    'version': '1.0',
    'category': 'Quotation',
    'sequence': 15,
    'summary': 'Quotation',
    'description': """Extra Quotation""",
    'website': 'https://www.odoo.com',
    'depends': ['sale', 'extra_invoice', 'extra_product', 'extra_partner', 'purchase'],
    'data': [
        'data/ir_sequence_data.xml',
        'views/sale_view.xml',
        'views/quotate_wizard_view.xml',
        'views/quotation_view.xml',
        'views/quotation_create_sale_wizard_view.xml',
    ],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
