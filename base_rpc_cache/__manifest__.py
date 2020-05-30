# -*- coding: utf-8 -*-
{
    'name': "base_rpc_cache",
    'summary': """
        timeout<300ms>时间内，如果请求的参数一样，直接返回cache中的结果，不发送请求""",
    'description': """
        目前，主要是为了list view中，如果有个字段是many2many，那么每一行都会去调用name_get
        如： sale order form view中的 sale.order.line 的 税率字段
    """,

    'author': "Todd",
    'category': 'Tools',
    'version': '0.1',
    'data': [
        'views/templates.xml',
    ],
    'qweb': ['static/src/*.xml'],
    'depends': ['web'],
}
