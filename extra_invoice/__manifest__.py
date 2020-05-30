# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Extra Invoice',
    'version': '1.0',
    'category': 'Extra Invoice',
    'sequence': 15,
    'summary': 'Extra Invoice',
    'description': """Extra Invoice""",
    'website': 'https://www.odoo.com/page/crm',
    'depends': ['account', 'sale', 'stock_account'],
    'data': [
        'views/account_invoice_view.xml',
        'views/res_currency_view.xml',
    ],
    'demo': [],
    'css': ['static/src/css/sale.css'],
    'installable': True,
    'auto_install': False,
    'application': True,
}
