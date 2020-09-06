# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Extra Product Model',
    'version': '1.0',
    'category': 'Extra Product',
    'sequence': 15,
    'summary': 'Extra Product',
    'description': """Extra Product Model, Help User Have A Better Handle On Product Manager""",
    'website': 'https://www.odoo.com',
    'depends': ['sale', 'purchase', 'extra_api', 'product'],
    'data': [
        'data/groups.xml',
        'views/product_view.xml',
        'ir.model.access.csv',
    ],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
