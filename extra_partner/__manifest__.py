# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Extra Partner',
    'version': '1.0',
    'category': 'Extra Partner',
    'sequence': 15,
    'summary': 'Extra Partner',
    'description': """Extra Partner Model, Help User Have A Better Handle On Partner Manager""",
    'website': 'https://www.odoo.com',
    'depends': ['sale', 'purchase', 'account'],
    'data': [
        'views/partner_view.xml',
        'data/ir_sequence_data.xml',
    ],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
