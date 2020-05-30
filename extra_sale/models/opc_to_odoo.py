# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging, json
import base64
import xlwt
from cStringIO import StringIO

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Sale Order
#----------------------------------------------------------
class SaleOrder(models.Model):
    _inherit = "sale.order"
    _description = u"销售单"

    saler_user_id = fields.Char(string=u'销售ID', readonly=True, states={'draft': [('readonly', False)]}) 
    saler_user_name = fields.Char(string=u'销售员名称', readonly=True, states={'draft': [('readonly', False)]})
    pay_time = fields.Datetime(string=u'支付时间', readonly=True, states={'draft': [('readonly', False)]})
    pay_way_name = fields.Char(string=u'支付类型名称', readonly=True, states={'draft': [('readonly', False)]})
    pay_transaction_no = fields.Char(string=u'支付交易号(仅线上支付有效)', readonly=True, states={'draft': [('readonly', False)]})
    bank_account_name = fields.Char(string=u'开户行(仅线下支付有效)', readonly=True, states={'draft': [('readonly', False)]})


    pay_type = fields.Selection(selection=[('0', u'预付'), ('1', u'账期付款')], string=u'付款类型', readonly=True, states={'draft': [('readonly', False)]})
    pay_way = fields.Selection(selection=[('0', u'线下转账'), ('1', u'支付宝'), ('2', u'微信')], readonly=True, string=u'付款方式', states={'draft': [('readonly', False)]})
    pay_status = fields.Selection(selection=[('0', u'未付款'), ('1', u'已付款'), ('2', u'付款审核中')], readonly=True, string=u'付款状态', states={'draft': [('readonly', False)]})
    delivery_time_type = fields.Selection(selection=[('0', u'任意时间'), ('1', u'工作日'), ('2', u'非工作日')], readonly=True, string=u'交付时间类型', states={'draft': [('readonly', False)]})
    receipt_type = fields.Selection(selection=[('0', u'不开票'), ('1', u'普票'), ('2', u'增值税发票')], string=u'发票类型', readonly=True, states={'draft': [('readonly', False)]})
    order_type = fields.Selection(selection=[('1', u'线上'), ('3', u'寄售'), ('4', u'样品')], string=u'订单类型', readonly=True, states={'draft': [('readonly', False)]})
    remark = fields.Char(string=u'客户留言', readonly=True, states={'draft': [('readonly', False)]})
    # saler_remark 销售备注 # odoo已有相关字段，且网站不能输入销售备注
    # logistical_remark: 物流备注 # odoo已有相关字段，且网站不能输入销售备注
    # supply_chain_remark: 供应链备注 # odoo已有相关字段，且网站不能输入销售备注
    # financial_remark: 财务备注 # odoo已有相关字段，且网站不能输入销售备注
    carrier = fields.Char(string=u'承运商', readonly=True, states={'draft': [('readonly', False)]})

    discount_amount = fields.Float(string=u'订单折扣金额', readonly=True, states={'draft': [('readonly', False)]})
    transfer_amount = fields.Float(string=u'订单运费', readonly=True, states={'draft': [('readonly', False)]})
    total_amount = fields.Float(string=u'订单总金额', readonly=True, states={'draft': [('readonly', False)]})
    pay_amount = fields.Float(string=u'订单实际支付金额', readonly=True, states={'draft': [('readonly', False)]})
    create_time = fields.Datetime(string=u'生成时间', readonly=True)

    # 收货人地址信息
    address_info_name = fields.Char(string=u'收货人姓名', readonly=True, states={'draft': [('readonly', False)]})
    address_info_company_name = fields.Char(string=u'收货人公司名称', readonly=True, states={'draft': [('readonly', False)]})
    address_info_mobile = fields.Char(string=u'收货人手机号', readonly=True, states={'draft': [('readonly', False)]})
    address_info_telephone = fields.Char(string=u'收货人电话', readonly=True, states={'draft': [('readonly', False)]})
    address_info_address = fields.Char(string=u'收货人详细地址', readonly=True, states={'draft': [('readonly', False)]})
    address_info_postcode = fields.Char(string=u'收货人邮编', readonly=True, states={'draft': [('readonly', False)]})

    # 发票信息
    receipt_info_receipt_sub_type = fields.Selection(selection=[('1', u'个人'), ('2', u'公司')], 
        string=u'普票类型', readonly=True, states={'draft': [('readonly', False)]})
    receipt_info_receipt_com_name = fields.Char(string=u'发票抬头', readonly=True, states={'draft': [('readonly', False)]})
    receipt_info_receipt_tax_no = fields.Char(string=u'增值税发票税号', readonly=True, states={'draft': [('readonly', False)]})
    receipt_info_receipt_com_addr = fields.Char(string=u'增值税发票营业地址', readonly=True, states={'draft': [('readonly', False)]})
    receipt_info_receipt_account = fields.Char(string=u'增值税发票开户行账号', readonly=True, states={'draft': [('readonly', False)]})
    receipt_info_receipt_tel = fields.Char(string=u'增值税发票营业电话', readonly=True, states={'draft': [('readonly', False)]})
    receipt_info_receipt_bank_name = fields.Char(string=u'增值税发票开户行', readonly=True, states={'draft': [('readonly', False)]})

    # 发票寄送地址信息
    receipt_address_info_name = fields.Char(string=u'发票寄送姓名', readonly=True, states={'draft': [('readonly', False)]})
    receipt_address_info_mobile = fields.Char(string=u'发票寄送手机号', readonly=True, states={'draft': [('readonly', False)]})
    receipt_address_info_telephone = fields.Char(string=u'发票寄送电话', readonly=True, states={'draft': [('readonly', False)]})
    receipt_address_info_address = fields.Char(string=u'发票寄送详细地址', readonly=True, states={'draft': [('readonly', False)]})
    receipt_address_info_postcode = fields.Char(string=u'发票寄送邮编', readonly=True, states={'draft': [('readonly', False)]})

    _sql_constraints = [
        ('name_uniq', 'unique(name)', u'销售单号不能重复'),
    ]

    @api.model
    def sync_so_modify(self, val):
        '''销售单创建接口'''
        _logger.info('sync_so_modify===========%s', val)
        if isinstance(val, str):
            val = json.loads(val)

        order_val = {}
        name = val.get('order_id', '')
        try:
            if not name:
                return json.dumps({'result': '1', 'message': u'销售单号不能为空'})
            sale_id = self.search([('name', '=', name)], limit=1)
            if sale_id:
                return json.dumps({'result': '1', 'message': u'销售单%s已存在'%name})
            order_val.update({'name': name})
            contract_num = val.get('contract_no', '')
            order_val.update({'contract_num': contract_num})
            saler_user_id = val.get('saler_user_id', '')
            order_val.update({'saler_user_id': saler_user_id})
            saler_user_name = val.get('saler_user_name', '')
            order_val.update({'saler_user_name': saler_user_name})
            saler_user_email = val.get('saler_user_email', '')
            if saler_user_email:
                user_id = self.env['res.users'].search([('email', '=', saler_user_email)], limit=1)
                if user_id:
                    order_val.update({'user_id': user_id.id})

            pay_type = order_val.get('pay_type', False)
            if pay_type:
                if pay_type not in ('0', '1'):
                    return json.dumps({'result': '1', 'message': u'销售单%s付款类型值错误:%s'%(name, pay_type, )})
            order_val.update({'pay_type': pay_type})
            pay_way = order_val.get('pay_way', False)
            if pay_way:
                if pay_way not in ('0', '1', '2'):
                    return json.dumps({'result': '1', 'message': u'销售单%s付款方式值错误:%s'%(name, pay_way, )})
            order_val.update({'pay_way': pay_way})

            # pay_status = order_val.get('pay_way', False)
            # if pay_status:
            #     if pay_status not in ('0', '1', '2'):
            #         return json.dumps({'result': '1', 'message': u'销售单%s付款状态值错误:%s'%(name, pay_status, )})
            # order_val.update({'pay_status': pay_status})

            delivery_time_type = val.get('delivery_time_type', False)
            if delivery_time_type:
                if delivery_time_type not in ('0', '1', '2'):
                    return json.dumps({'result': '1', 'message': u'销售单%s交付时间值错误:%s'%(name, delivery_time_type, )})
            order_val.update({'delivery_time_type': delivery_time_type})

            receipt_type = val.get('receipt_type', False)
            if receipt_type:
                if receipt_type not in ('0', '1', '2'):
                    return json.dumps({'result': '1', 'message': u'销售单%s发票类型值错误:%s'%(name, receipt_type, )})
            order_val.update({'receipt_type': receipt_type})


            order_type = val.get('order_type', False)
            if order_type:
                if order_type not in ('1', '3', '4'):
                    return json.dumps({'result': '1', 'message': u'销售单%s订单类型值错误:%s'%(name, order_type, )})
            order_val.update({'order_type': order_type})

            carrier = val.get('carrier', '')
            order_val.update({'carrier': carrier})

            discount_amount = val.get('discount_amount', '')
            order_val.update({'discount_amount': discount_amount})

            transfer_amount = val.get('transfer_amount', 0)
            order_val.update({'transfer_amount': transfer_amount})

            total_amount = val.get('total_amount', 0)
            order_val.update({'total_amount': total_amount})

            pay_amount = val.get('pay_amount', 0)
            order_val.update({'pay_amount': pay_amount})

            create_time = val.get('create_time', False)
            if create_time:
                create_time = (datetime.strptime(create_time, '%Y-%m-%d %H:%M:%S') - timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S')
            order_val.update({'create_time': create_time})

            user_info = val.get('user_info', {})
            partner_id = self.solve_user_info(user_info)
            if not partner_id:
                return json.dumps({'result': '1', 'message': u'销售单%s找不到对应的客户:%s'%(name, str(user_info), )})

            _logger.info('=======111111111111111')
            order_val.update({
                'partner_id': partner_id.id, 
                'partner_shipping_id': partner_id.id, 
                'partner_invoice_id': partner_id.id,
                'partner_contact_id': partner_id.id,
                })

            # 收货地址
            address_info = val.get('address_info', {})
            for k, v in address_info.items():
                order_val.update({'address_info_' + k: v})

            _logger.info('=======44444444444444444444')
            # 发票信息
            receipt_info = val.get('receipt_info', {})
            for k, v in receipt_info.items():
                if k == 'receipt_sub_type' and v and v not in ('1', '2'):
                    return json.dumps({'result': '1', 'message': u'销售单%s普票类型值错误:%s'%(name, v, )})
                order_val.update({'receipt_info_' + k: v})

            _logger.info('=======333333333333333333333')
            # 发票寄送信息
            receipt_address_info = val.get('receipt_address_info', {})
            for k, v in receipt_address_info.items():
                order_val.update({'receipt_address_info_' + k: v})

            # 产品明细
            products = val.get('products', [])
            order_line, error_msg = self.solve_products(products)
            if error_msg:
                return json.dumps({'result': '1', 'message': u'销售单%s创建失败:%s'%(name, error_msg, )})
            order_val.update({'order_line': order_line})
            _logger.info('=======22222222222222222222')
            sale_id = self.create(order_val)
            return json.dumps({'result': '0', 'message': ''})
        except Exception as e:
            self.env.cr.rollback()
            _logger.exception(e)
            return json.dumps({'result': '1', 'message': u'销售单%s创建失败:%s'%(name, e.message, )})

    @api.model
    def solve_user_info(self, user_info):
        user_id = user_info.get('user_id', False)
        partner_id = self.env['res.partner'].search([('customer_guid', '=', user_id), ('customer', '=', True)], limit=1)
        return partner_id

    @api.model
    def solve_products(self, products):
        order_line = []
        error_msg = ''
        product_model = self.env['product.product']
        for product in products:
            sku_code = product.get('sku_code', 'nullbysys')
            product_id = product_model.search([('default_code', '=', sku_code), ('active', '=', True)], limit=1)
            if not product_id:
                return order_line, u'找不到商品:%s'%sku_code
            # warning 单位不处理
            order_line.append((0, 0, {
                    'product_id': product_id.id,
                    'user_product_no': product.get('user_product_no', ''),
                    'original_items_amount': product.get('original_items_amount', 0),
                    'sub_total_amount': product.get('sub_total_amount', 0),
                    'product_uom': product_id.uom_id.id,
                    'price_unit': product.get('sale_price', 0),
                    'product_uom_qty': product.get('quantity', 0),
                }))
        return order_line, ''

    @api.model
    def sync_so_cancel(self, val):
        '''销售单取消接口（未支付前）'''
        _logger.info('sync_so_cancel===========%s', val)
        if isinstance(val, str):
            val = json.loads(val)

        name = val.get('order_id', '')
        try:
            if not name:
                return json.dumps({'result': '1', 'message': u'销售单号不能为空'})
            sale_id = self.search([('name', '=', name)], limit=1)
            if not sale_id:
                return json.dumps({'result': '1', 'message': u'销售单号%s找不到'%name})
            sale_id.action_cancel()
            return json.dumps({'result': '0', 'message': ''})
        except Exception as e:
            self.env.cr.rollback()
            _logger.exception(e)
            return json.dumps({'result': '1', 'message': u'销售单%s取消失败:%s'%(name, e.message, )})

    @api.model
    def sync_so_pay(self, val):
        _logger.info('sync_so_pay===========%s', val)
        '''销售单支付接口'''
        if isinstance(val, str):
            val = json.loads(val)

        name = val.get('order_id', '')
        try:
            if not name:
                return json.dumps({'result': '1', 'message': u'销售单号不能为空'})
            sale_id = self.search([('name', '=', name)], limit=1)
            if not sale_id:
                return json.dumps({'result': '1', 'message': u'销售单号%s找不到'%name})
            sale_id.write({
                    'pay_way': val.get('pay_way', False), 
                    'pay_way_name': val.get('pay_way_name', ''), 
                    'pay_time': val.get('pay_time', False),
                    # 'pay_status': '1',
                    'pay_transaction_no': val.get('pay_transaction_no', ''),
                    'bank_account_name': val.get('bank_account_name', ''),
                })
            return json.dumps({'result': '0', 'message': ''})
        except Exception as e:
            self.env.cr.rollback()
            _logger.exception(e)
            return json.dumps({'result': '1', 'message': u'销售单%s支付失败:%s'%(name, e.message, )})



#----------------------------------------------------------
# Sale Order
#----------------------------------------------------------
class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    _description = u"销售单明细"

    user_product_no = fields.Char(string=u'客户商品编码')
    original_items_amount = fields.Float(string=u'原行小计')
    sub_total_amount = fields.Float(string=u'行项目小计')