# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from openerp.tools import config

from datetime import datetime, timedelta
import logging, time, hashlib, requests, json
import xmlrpclib

_logger = logging.getLogger(__name__)

AUTHKEY = config.options.get('authkey', '')
APPTYPE = config.options.get('apptype', '')
BASEURL = config.options.get('baseurl', '')

#----------------------------------------------------------
# Extra Api
#----------------------------------------------------------
class ExtraApi(models.Model):
    _name = 'extra.api'
    _description = u'odoo同步接口'

    api_type = fields.Selection([('brand_update', u'品牌更新'), ('brand_delete', u'品牌删除'), 
        ('categ_update', u'分类更新'), ('categ_delete', u'分类删除'),
        ('product_update', u'产品更新'), ('product_delete', u'产品删除'), 
        ('order_send', u'发货状态同步'), ('order_update', u'销售单更新'), 
        ('product_update_odoo', u'产品更新(子系统)'), ('product_delete', u'产品删除(子系统)'),
        ('categ_update_odoo', u'分类更新(子系统)'), ('brand_update_odoo', u'分类更新(子系统)'),
        ], index=True, readonly=True, required=True)

    http_method = fields.Selection([('post', 'POST'), ('get', 'GET')], string=u'提交方法', readonly=True, required=True)
    data_model = fields.Char(u'数据类型', index=True, readonly=True, required=True)

    key_value = fields.Integer(u'Key值', index=True, readonly=True, required=True)
    data = fields.Char(u'数据内容')
    state = fields.Selection([('new', u'写入'), ('done', u'完成'),
                                   ('fail', u'失败'), ('invalid', u'无效')], u'状态', default='new', index=True, required=True, readonly=True)

    url = fields.Char(u'接口地址', readonly=True)
    information = fields.Text(u'操作信息')
    times = fields.Integer(u'重试次数', default=0, index=True)
    return_info = fields.Char(u'返回结果', readonly=True)

    @api.model
    def get_headers(self):
        version = '1.0.0'
        timestring = str(int(time.time()))
        sign = APPTYPE + timestring
        m = hashlib.md5()
        m.update(sign)
        psw = m.hexdigest()

        sign2 = psw + AUTHKEY
        m2 = hashlib.md5()
        m2.update(sign2)

        token = m2.hexdigest()
        headers = {'M-API-VERSION': version, 'M-API-TOKEN': token, 'M-API-APPTYPE': APPTYPE, 'M-API-TIME': timestring}

        return headers

    @api.multi
    def action_send_to_odoo(self):
        interface_info = config.options.get(self.url, '')
        _logger.info(interface_info)
        if not interface_info:
            return {}
        interface_info = eval(interface_info)
        dbname = interface_info.get('dbname')
        usr = interface_info.get('usr')
        pwd = interface_info.get('pwd')
        oe_ip = interface_info.get('oe_ip')
        sock_common = xmlrpclib.ServerProxy('https://' + oe_ip + '/xmlrpc/common')
        uid = sock_common.login(dbname, usr, pwd)
        sock = xmlrpclib.ServerProxy('https://' + oe_ip + '/xmlrpc/object')
        respd = sock.execute(dbname, uid, pwd, self.data_model, self.api_type, eval(self.data))
        return respd

    @api.multi
    def action_send(self):
        url = BASEURL + self.url
        headers = self.get_headers()
        # headers.update({'Content-Type': 'application/json'})
        try:
            respd = {}
            if not self.api_type.endswith('odoo'):
                val = {}
                if self.http_method == 'get':
                    val = {'params': eval(self.data)}
                elif self.http_method == 'post':
                    val = {'data': eval(self.data)}

                resp = getattr(requests, self.http_method)(url, headers=headers, **val)

                # resp = requests.request(self.http_method.upper(), url, data=eval(self.data), headers=headers)
                respd = resp.json()
            else:
                respd = self.action_send_to_odoo()
            result = respd.get('result')
            if result == '0':
                self.write({'state': 'done', 'return_info': respd.get('message', ''), 'information': respd})
            else:
                self.write({'state': 'fail', 'return_info': respd.get('message', ''), 'information': respd, 'times': self.times + 1})
        except Exception as e:
            self.env.cr.rollback()
            _logger.exception(e.message)
            self.write({'state': 'fail', 'return_info': u'发生异常', 'information': e.message, 'times': self.times + 1})

        return True

    @api.model
    def auto_send(self, times=5):
        sync_ids = self.search([('state', 'in', ('new', 'fail')), ('times', '<', times)])
        for sync_id in sync_ids:
            if sync_id.state in ('new', 'fail'):
                sync_id.action_send()
                if sync_id.state == 'done':
                    sync_ids.filtered(
                            lambda s: s.data_model == sync_id.data_model and s.key_value == sync_id.key_value and s.api_type == sync_id.api_type and s.state in ('new', 'fail')
                            and s.create_date <= sync_id.create_date
                        ).write({
                            'state': 'invalid',
                        })

        return True