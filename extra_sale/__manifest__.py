# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'Extra Sale',
    'version': '1.0',
    'category': 'Extra Sale',
    'sequence': 15,
    'summary': 'Extra Sale',
    'description': """Extra Sale""",
    'website': 'https://www.odoo.com/page/crm',
    'depends': ['extra_quotation', 'sale', 'stock', 'account', 'extra_api'],
    'data': [
        'data/groups.xml',
        'views/sale_view.xml',
        'data/stock_data.xml',
        'report/sale_report.xml',
        'ir.model.access.csv'
    ],
    'demo': [],
    'css': [],
    'installable': True,
    'auto_install': False,
    'application': True,
}
