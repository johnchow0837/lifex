# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Extra Account',
    'version': '1.0',
    'category': 'Extra Account',
    'sequence': 15,
    'summary': 'Extra Account',
    'description': """Extra Account""",
    'website': 'https://www.odoo.com',
    'depends': [
        'stock_account', 'account_cancel',
        'sale', 'purchase',
    ],
    'data': [
        'data/groups.xml',
        'views/account.xml',
    ],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
