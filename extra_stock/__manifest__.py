# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Extra Stock',
    'version': '1.0',
    'category': 'Extra Stock',
    'sequence': 15,
    'summary': 'Extra Stock',
    'description': """Extra Stock""",
    'website': 'https://www.odoo.com',
    'depends': ['stock', 'extra_sale'],
    'data': [
        'views/stock_view.xml',
        'report/stock_report.xml',
        'ir.model.access.csv',
    ],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
