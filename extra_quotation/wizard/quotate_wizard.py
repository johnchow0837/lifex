# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class QuotateWizard(models.TransientModel):
    _name = 'quotate.wizard'
    _description = u'报价导航窗口'

    request_quotation_line_id = fields.Many2one('sale.request.quotation.line', string=u'询价明细', required=True, readonly=True)
    solve_type = fields.Selection(selection=[('modify', u'修改商品'), ('sku', u'指定商品'), ('new', u'新建商品')], string=u'处理方式', required=True, default='sku')

    # 商品信息
    m_cat_no = fields.Char(string=u'产品货号', readonly=True)
    m_product_name = fields.Char(string=u'产品名称', readonly=True)
    m_comment_desc = fields.Char(string=u'产品描述', readonly=True)
    m_cas_code = fields.Char(string=u'化学品CAS号', readonly=True)
    m_product_category_name = fields.Char(string=u'产品分类', help=u'产品大类', readonly=True)
    m_product_brand_name = fields.Char(string=u'品牌名称', help=u'模糊匹配系统存有的品牌', readonly=True)
    m_package_name = fields.Char(string=u'包装', help=u'包装单位', readonly=True)
    m_product_uom_name = fields.Char(string=u'单位', readonly=True)
    m_product_uom_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0, readonly=True)
    m_suggest_vendor = fields.Char(string=u'建议供应商', readonly=True)
    m_required_date = fields.Date(string=u'希望到货日期', readonly=True)
    m_sale_comment = fields.Char(string=u'销售备注', readonly=True)

    # 修改商品信息字段
    modify_cat_no = fields.Char(string=u'产品货号')
    modify_product_name = fields.Char(string=u'产品名称')
    modify_comment_desc = fields.Char(string=u'产品描述')
    modify_cas_code = fields.Char(string=u'化学品CAS号')
    modify_product_category_name = fields.Char(string=u'产品分类', help=u'产品大类')
    modify_product_brand_name = fields.Char(string=u'品牌名称', help=u'模糊匹配系统存有的品牌')
    modify_package_name = fields.Char(string=u'包装', help=u'包装单位')
    modify_product_uom_name = fields.Char(string=u'单位')
    modify_product_uom_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), default=1.0)
    suggest_vendor = fields.Char(string=u'建议供应商', readonly=True)
    required_date = fields.Date(string=u'希望到货日期', readonly=True)

    # 指定SKU
    product_id = fields.Many2one('product.product', string=u'指定产品')

    vendor_type = fields.Selection(selection=[('special', u'指定供应商'), ('new', u'添加供应商')], default='special', string=u'供应商处理方式')
    vendor_id = fields.Many2one('res.partner', string=u'供应商')
    sku_new_vendor_id = fields.Many2one('res.partner', string=u'供应商')

    default_code = fields.Char(string=u'系统编号', readonly=True, related="product_id.default_code")
    cat_no = fields.Char(string=u'产品编号', readonly=True, related="product_id.cat_no")
    comment_desc_cn = fields.Char(string=u'产品中文描述', readonly=True, related="product_id.comment_desc_cn")
    comment_desc_en = fields.Char(string=u'产品英文描述', readonly=True, related="product_id.comment_desc_en")
    cas_code = fields.Char(string=u'化学品CAS号', readonly=True, related="product_id.cas_code")
    vendor_code = fields.Char(string=u'供应商编码', readonly=True, related="vendor_id.supplier_guid")
    sku_new_vendor_code = fields.Char(string=u'供应商编码', readonly=True, related="sku_new_vendor_id.supplier_guid")
    vendor_name = fields.Char(string=u'供应商名称', readonly=True, related="vendor_id.name")
    sku_new_vendor_name = fields.Char(string=u'供应商名称', readonly=True, related="sku_new_vendor_id.name")
    vendor_cat_no = fields.Char(string=u'供应商目录号', readonly=True, related="vendor_id.supplier_cat_no")
    sku_new_vendor_cat_no = fields.Char(string=u'供应商目录号', readonly=True, related="sku_new_vendor_id.supplier_cat_no")
    product_brand_name = fields.Char(string=u'产品品牌', readonly=True, related="product_id.brand_id.name")
    package_name = fields.Char(string=u'包装', readonly=True, related="product_id.package_name")
    product_uom_name = fields.Char(string=u'单位', readonly=True, related="product_id.uom_id.name")
    product_category_name = fields.Char(string=u'产品分类', readonly=True, related="product_id.categ_id.name")
    product_list_price_cny = fields.Float(string=u'产品牌价(人民币)', readonly=True, related="product_id.list_price")
    product_list_price_for = fields.Float(string=u'产品牌价(FOR)', readonly=True)
    product_purchase_price_cny = fields.Float(string=u'采购成本(人民币)', default=0)
    sku_new_product_purchase_price_cny = fields.Float(string=u'采购成本(人民币)', default=0)


    product_purchase_price_for = fields.Float(string=u'采购成本(FOR)', default=0)
    sku_new_product_purchase_price_for = fields.Float(string=u'采购成本(FOR)', default=0)



    product_purchase_currency = fields.Many2one('res.currency', string=u'采购币种')
    sku_new_product_purchase_currency = fields.Many2one('res.currency', string=u'采购币种')


    currency_exchange_rate = fields.Float(string=u'汇率', default=1)
    sku_new_currency_exchange_rate = fields.Float(string=u'汇率', default=1)

    price_expired_date = fields.Date(string=u'价格有效期')
    sku_new_price_expired_date = fields.Date(string=u'价格有效期')

    vendor_lead_time = fields.Float(string=u'供应商货期', readonly=False)
    sku_new_vendor_lead_time = fields.Float(string=u'供应商货期', readonly=False)


    vendor_lead_time_desc = fields.Char(string=u'供应商货期描述')
    sku_new_vendor_lead_time_desc = fields.Char(string=u'供应商货期描述')

    storage_condition = fields.Selection(selection=[('normal', u'常温'), ('2-8', u'2-8摄氏度'), ('0-4', u'0-4摄氏度'), ('-20', u'零下20摄氏度'), ('-80', u'零下80摄氏度')], 
        string=u'储存条件', readonly=True, related="product_id.storage_condition")

    counting_weight = fields.Float(string=u'毛重', readonly=True, related="product_id.counting_weight")
    net_weight = fields.Float(string=u'净重' , readonly=True, related="product_id.net_weight")
    duty_rate = fields.Float(string=u'关税税率', readonly=True, related="product_id.duty_rate")
    vendor_term = fields.Selection(selection=[('DDP', 'DDP'), ('CIP', 'CIP'), ('CIF', 'CIF'), ('EXW', 'EXW'), ('FOB', 'FOB')], 
        string=u'供应商贸易方式', readonly=False, default='DDP')
    sku_new_vendor_term = fields.Selection(selection=[('DDP', 'DDP'), ('CIP', 'CIP'), ('CIF', 'CIF'), ('EXW', 'EXW'), ('FOB', 'FOB')], 
        string=u'供应商贸易方式', readonly=False, default='DDP')

    vendor_shipment = fields.Selection(selection=[('land', u'陆运'), ('air', u'空运'), ('ocean', u'海运')],
        string=u'供应商运输方式', readonly=False)

    sku_new_vendor_shipment = fields.Selection(selection=[('land', u'陆运'), ('air', u'空运'), ('ocean', u'海运')],
        string=u'供应商运输方式', readonly=False)

    vendor_payment = fields.Many2one(relation="account.payment.term", string=u'供应商付款条件', readonly=True, related="vendor_id.property_supplier_payment_term_id")
    sku_new_vendor_payment = fields.Many2one(relation="account.payment.term", string=u'供应商付款条件', readonly=True, related="sku_new_vendor_id.property_supplier_payment_term_id")

    is_discontinued = fields.Boolean(string=u'是否停产', readonly=True, related="product_id.is_discontinued")
    sale_currency = fields.Many2one('res.currency', string=u'销售币种')
    external_comments = fields.Char(string=u'外部备注')
    internal_comments = fields.Char(string=u'内部备注')
    purchase_comment = fields.Char(string=u'采购备注')
    product_manager_name = fields.Char(string=u'产品经理', readonly=True, related="product_id.product_manager_name")
    is_stockitem = fields.Boolean(string=u'是否库存产品', readonly=True, related="product_id.is_stockitem")
    min_order_qty = fields.Float(string=u'最小起定量', readonly=False, default=0)
    sku_new_min_order_qty = fields.Float(string=u'最小起定量', readonly=False, default=0)

    vendor_contact_id = fields.Many2one('res.partner', string=u'供应商联系人', readonly=False, domain="[('type', '=', 'contact'), ('parent_id', '=', vendor_id)]")
    sku_new_vendor_contact_id = fields.Many2one('res.partner', string=u'供应商联系人', readonly=False, domain="[('type', '=', 'contact'), ('parent_id', '=', sku_new_vendor_id)]")

    vendor_contact_info = fields.Char(string=u'联系人名称', readonly=True, related="vendor_contact_id.name")
    sku_new_vendor_contact_info = fields.Char(string=u'联系人名称', readonly=True, related="sku_new_vendor_contact_id.name")

    concat = fields.Char(string=u'联系电话', readonly=True, related="vendor_contact_id.phone")
    sku_new_concat = fields.Char(string=u'联系电话', readonly=True, related="sku_new_vendor_contact_id.phone")

    email = fields.Char(string=u'联系邮箱', readonly=True, related="vendor_contact_id.email")
    sku_new_email = fields.Char(string=u'联系邮箱', readonly=True, related="sku_new_vendor_contact_id.email")

    product_status = fields.Char(string=u'产品状态', readonly=True, related="product_id.product_status")
    product_supplierinfo = fields.Many2one('product.supplierinfo', string="产品供应商信息")
    match_status = fields.Selection(selection=[('perfect', u'完美匹配'), ('partial', u'推荐替换')], string=u'匹配状态', default='perfect')


    # 新建SKU
    new_product_name = fields.Char(string=u'产品名称')
    new_cas_code = fields.Char(string=u'化学品CAS号')
    new_brand_id = fields.Many2one('product.brand', string=u'产品品牌')
    new_package_name = fields.Char(string=u'包装')
    new_cat_no = fields.Char(string=u'原厂货号')
    new_comment_desc_cn = fields.Char(string=u'产品中文描述')
    new_comment_desc_en = fields.Char(string=u'产品英文描述')

    new_storage_condition = fields.Selection(selection=[('normal', u'常温'), ('2-8', u'2-8摄氏度'), ('0-4', u'0-4摄氏度'), ('-20', u'零下20摄氏度'), ('-80', u'零下80摄氏度')], 
        string=u'储存条件', default='normal')

    new_counting_weight = fields.Float(string=u'毛重')
    new_net_weight = fields.Float(string=u'净重')
    new_is_discontinued = fields.Boolean(string=u'是否停产', default=False)
    new_product_manager_name = fields.Char(string=u"产品经理", readonly=True, default=lambda s: s.env.user.name)
    new_is_stockitem = fields.Boolean(string=u"是否库存产品")
    new_min_orderqty = fields.Float(string="最小库存量")
    new_product_status = fields.Char(string=u"产品状态")
    new_product_model = fields.Char(string=u"规格型号")
    new_uom_id = fields.Many2one('product.uom', string=u'单位')

    new_vendor_id = fields.Many2one('res.partner', string=u'供应商')
    new_vendor_contact_id = fields.Many2one('res.partner', string=u'供应商联系人', readonly=False, domain="[('type', '=', 'contact'), ('parent_id', '=', new_vendor_id)]")
    new_vendor_contact_info = fields.Char(string=u'供应商联系人', readonly=True, related="new_vendor_contact_id.name")
    new_concat = fields.Char(string=u'联系电话', readonly=True, related="new_vendor_contact_id.phone")
    new_email = fields.Char(string=u'联系邮箱', readonly=True, related="new_vendor_contact_id.email")

    new_min_order_qty = fields.Float(string=u"最小起定量", default=0)

    new_default_code = fields.Char(string=u"系统编号")
    new_categ_id = fields.Many2one('product.category', string=u'产品分类')

    new_product_list_price_cny = fields.Float(string=u'产品牌价(人民币)')
    new_product_list_price_for = fields.Float(string=u'产品牌价(FOR)')
    new_supplier_taxes_id = fields.Many2one('account.tax', string=u'进项税', domain="[('type_tax_use', '=', 'purchase')]")
    new_product_purchase_price_cny = fields.Float(string=u'采购成本(人民币)')
    new_product_purchase_price_for = fields.Float(string=u'采购成本(FOR)')
    new_product_purchase_currency = fields.Many2one('res.currency', string=u'采购币种')
    new_currency_exchange_rate = fields.Float(string=u'汇率', default=1)
    new_price_expired_date = fields.Date(string=u'价格有效期')
    new_vendor_lead_time = fields.Float(string=u'供应商货期')
    new_vendor_lead_time_desc = fields.Char(string=u'供应商货期描述')
    new_duty_rate = fields.Float(string=u'关税税率')

    new_vendor_term = fields.Selection(selection=[('DDP', 'DDP'), ('CIP', 'CIP'), ('CIF', 'CIF'), ('EXW', 'EXW'), ('FOB', 'FOB')], 
        string=u'供应商贸易方式', default='DDP')


    new_vendor_shipment = fields.Selection(selection=[('land', u'陆运'), ('air', u'空运'), ('ocean', u'海运')],
        string=u'供应商运输方式', default='land')


    new_vendor_payment = fields.Many2one('account.payment.term', string=u'供应商付款条件', readonly=True, related="new_vendor_id.property_supplier_payment_term_id")
    new_sale_currency = fields.Many2one('res.currency', string=u'销售币种')
    new_external_comments = fields.Char(string=u'外部备注')
    new_internal_comments = fields.Char(string=u'内部备注')

    new_purchase_comment = fields.Char(string=u'采购备注')

    new_match_status = fields.Selection(selection=[('perfect', u'完美匹配'), ('partial', u'推荐替换')], string=u'匹配状态', default='perfect')

    @api.onchange('product_purchase_currency')
    def _onchange_product_purchase_currency(self):
        self.currency_exchange_rate = self.product_purchase_currency.manu_rate or 0

    @api.onchange('sku_new_product_purchase_currency')
    def _onchange_product_purchase_currency(self):
        self.sku_new_currency_exchange_rate = self.sku_new_product_purchase_currency.manu_rate or 0

    @api.onchange('request_quotation_line_id')
    def _onchange_request_quotation_line_id(self):
        domain = []
        if self.request_quotation_line_id:
            match_product_ids = self.request_quotation_line_id.action_match_product()[self.request_quotation_line_id]
            self.product_id = match_product_ids['perfect'].id
            domain += [('id', 'in', match_product_ids['perfect'].ids + match_product_ids['partial'].ids)]
        return {'domain': {'product_id': domain}}

    @api.onchange('sale_currency')
    def _onchange_sale_currency(self):
        if not self.sale_currency:
            self.product_list_price_for = 0
        else:
            if self.product_id:
                self.product_list_price_for = self.product_id.pricelist_currency_ids.filtered(lambda s: s.currency_id == self.sale_currency).price
            else:
                self.product_list_price_for = 0

    @api.onchange('product_id')
    def _onchange_product_id(self):
        domain = []
        if self.product_id:
            domain += [('id', 'in', self.product_id.mapped('seller_ids.name').ids)]
            if self.sale_currency:
                self.product_list_price_for = self.product_id.pricelist_currency_ids.filtered(lambda s: s.currency_id == self.sale_currency).price
        else:
            self.product_list_price_for = 0
            domain += [(0, '=', 1)]

        self.vendor_id = False
        self.vendor_contact_id = False
        return {'domain': {'vendor_id': domain}}

    @api.onchange('vendor_id')
    def _onchange_vendor_id(self):
        product_purchase_price_cny = 0
        price_expired_date = False
        vendor_lead_time = 0
        vendor_term = ''
        vendor_shipment = ''
        warning = {}
        product_supplierinfo = False

        product_purchase_currency = False
        product_purchase_price_for = 0

        if self.vendor_id and self.product_id:
            supplier_info = self.product_id.seller_ids.filtered(lambda s: s.name.id == self.vendor_id.id)
            if not supplier_info:
                warning = {'title': u'错误', 'message': u'%s不是所属于%s的供应商，请重新选择'%(self.vendor_id.name, self.product_id.default_code, )}
                self.vendor_id = False
            else:
                now_date = datetime.now().strftime('%Y-%m-%d')
                valid_supplier_info = supplier_info.filtered(lambda s: s.date_start <= now_date and s.date_end >= now_date)
                if not valid_supplier_info:
                    product_supplierinfo = supplier_info[-1].id
                    vendor_lead_time = supplier_info[-1].delay
                    vendor_term = supplier_info[-1].vendor_term
                    vendor_shipment = supplier_info[-1].vendor_shipment

                    product_purchase_price_cny = supplier_info[-1].price
                    price_expired_date = supplier_info[-1].date_end

                    product_purchase_currency = supplier_info[-1].currency_id.id
                    product_purchase_price_for = supplier_info[-1].for_price

                    warning = {'title': u'警告', 'message': u'供应商%s采购价已过期，请手动修改！'%self.vendor_id.name}
                else:
                    product_supplierinfo = valid_supplier_info[0].id
                    vendor_lead_time = valid_supplier_info[0].delay
                    vendor_term = valid_supplier_info[0].vendor_term
                    vendor_shipment = valid_supplier_info[0].vendor_shipment
                    product_purchase_price_cny = valid_supplier_info[0].price
                    price_expired_date = valid_supplier_info[0].date_end

                    product_purchase_currency = valid_supplier_info[0].currency_id.id
                    product_purchase_price_for = valid_supplier_info[0].for_price

        self.product_supplierinfo = product_supplierinfo
        self.product_purchase_price_cny = product_purchase_price_cny
        self.price_expired_date = price_expired_date
        self.vendor_lead_time = vendor_lead_time
        self.vendor_term = vendor_term
        self.vendor_shipment = vendor_shipment
        return {'warning': warning}

    @api.multi
    def _prepare_modify_val(self):
        val = {
            'cat_no': self.modify_cat_no,
            'product_name': self.modify_product_name,
            'comment_desc': self.modify_comment_desc,
            'cas_code': self.modify_cas_code,
            'product_category_name': self.modify_product_category_name,
            'product_brand_name': self.modify_product_brand_name,
            'package_name': self.modify_package_name,
            'product_uom_name': self.modify_product_uom_name,
            'product_uom_qty': self.modify_product_uom_qty,
            'suggest_vendor': self.suggest_vendor,
            'required_date': self.required_date,
        }
        return val

    @api.multi
    def _prepare_supplierinfo_val(self):
        val = {
            'name': self.new_vendor_id.id,
            'product_name': self.new_product_name,
            # 'product_code': self.new_default_code,
            'vendor_term': self.new_vendor_term,
            'vendor_shipment': self.new_vendor_shipment,
            'delay': self.new_vendor_lead_time,
            'min_qty': self.new_min_order_qty,
            'price': self.new_product_purchase_price_cny,
            'date_start': datetime.now(),
            'date_end': self.new_price_expired_date,
            'currency_id': self.new_product_purchase_currency.id,
            'for_price': self.new_product_purchase_price_for,
        }
        return val

    @api.multi
    def _prepare_pricelist_currency_val(self):
        val = {}
        if self.new_sale_currency.name != 'CNY':
            val.update({
                    'currency_id': self.new_sale_currency.id,
                    'price': self.new_product_list_price_for,
                })
        return val

    @api.multi
    def _prepare_create_product_val(self):
        cny_currency_id = self.env['res.currency'].search([('name', '=', 'CNY'), ('active', '=', True)], limit=1)
        cny_price_val = [(0, 0, {'currency_id': cny_currency_id.id, 'price': self.new_product_list_price_cny})] if cny_currency_id else []
        pricelist_val = self._prepare_pricelist_currency_val()
        val = {
            'name': self.new_product_name,
            'type': 'product',
            'duty_rate': self.new_duty_rate,
            'cas_code': self.new_cas_code,
            'brand_id': self.new_brand_id.id,
            'package_name': self.new_package_name,
            'cat_no': self.new_cat_no,
            'comment_desc_cn': self.new_comment_desc_cn,
            'comment_desc_en': self.new_comment_desc_en,
            'storage_condition': self.new_storage_condition,
            'counting_weight': self.new_counting_weight,
            'net_weight': self.new_net_weight,
            'is_discontinued': self.new_is_discontinued,
            'product_manager_name': self.new_product_manager_name,
            'is_stockitem': self.new_is_stockitem,
            'min_orderqty': self.new_min_orderqty,
            'product_status': self.new_product_status,
            'product_model': self.new_product_model,
            'uom_id': self.new_uom_id.id,
            'uom_po_id': self.new_uom_id.id,
            'categ_id': self.new_categ_id.id,
            # 'default_code': self.new_default_code,
            'list_price': self.new_product_list_price_cny,
            'supplier_taxes_id': [(6, 0, self.new_supplier_taxes_id.ids)],
            'seller_ids': [(0, 0, self._prepare_supplierinfo_val())],
            'pricelist_currency_ids': [(0, 0, pricelist_val)] if pricelist_val else [] + cny_price_val,
        }

        return val

    @api.multi
    def _prepare_special_quotation_val(self):
        supplier_info_val = {}
        if self.vendor_type == 'special':
            supplier_info_val = {
                'vendor_code': self.vendor_code,
                'vendor_name': self.vendor_name,
                'vendor_id': self.vendor_id.id,
                'vendor_cat_no': self.vendor_cat_no,
                'currency_exchange_rate': self.currency_exchange_rate,
                'vendor_lead_time_desc': self.vendor_lead_time_desc,
                'vendor_payment': self.vendor_payment.name,
                'vendor_contact_info': self.vendor_contact_info,
                'concat': self.concat,
                'email': self.email,
            }
        else:
            supplier_info_val = {
                'vendor_code': self.sku_new_vendor_code,
                'vendor_name': self.sku_new_vendor_name,
                'vendor_id': self.sku_new_vendor_id.id,
                'vendor_cat_no': self.sku_new_vendor_cat_no,
                'currency_exchange_rate': self.sku_new_currency_exchange_rate,
                'vendor_lead_time_desc': self.sku_new_vendor_lead_time_desc,
                'vendor_payment': self.sku_new_vendor_payment.name,
                'vendor_contact_info': self.sku_new_vendor_contact_info,
                'concat': self.sku_new_concat,
                'email': self.sku_new_email,
            }

        val = {
            'product_id': self.product_id.id,
            'default_code': self.default_code,
            'cat_no': self.cat_no,
            'comment_desc_cn': self.comment_desc_cn,
            'comment_desc_en': self.comment_desc_en,
            'cas_code': self.cas_code,
            'product_brand_name': self.product_brand_name,
            'purchase_comment': self.purchase_comment,
            'package_name': self.package_name,
            'product_uom_name': self.product_uom_name,
            'product_category_name': self.product_category_name,
            'product_list_price_cny': self.product_list_price_cny,
            'product_list_price_for': self.product_list_price_for,
            'product_purchase_price_cny': self.product_supplierinfo.price,
            'product_purchase_price_for': self.product_supplierinfo.for_price,
            'product_purchase_currency': self.product_supplierinfo.currency_id.id,
            'price_expired_date': self.product_supplierinfo.date_end,
            'vendor_lead_time': self.product_supplierinfo.delay,
            'storage_condition': self.storage_condition,
            'counting_weight': self.counting_weight,
            'net_weight': self.net_weight,
            'duty_rate': self.duty_rate,
            'vendor_term': self.product_supplierinfo.vendor_term,
            'vendor_shipment': self.product_supplierinfo.vendor_shipment,
            'is_discontinued': self.is_discontinued,
            'sale_currency': self.sale_currency.id,
            'external_comments': self.external_comments,
            'internal_comments': self.internal_comments,
            'product_manager_name': self.product_manager_name,
            'is_stockitem': self.is_stockitem,
            'min_order_qty': self.product_supplierinfo.min_qty,
            'product_status': self.product_status,
            'match_status': self.match_status,
            'request_quotation_line_id': self.request_quotation_line_id.id,
        }

        val.update(supplier_info_val)
        return val

    @api.multi
    def _prepare_new_quotation_val(self, product_id):
        val = {
            'product_id': product_id.id,
            'default_code': product_id.default_code,
            'cat_no': product_id.cat_no,
            'comment_desc_cn': product_id.comment_desc_cn,
            'comment_desc_en': product_id.comment_desc_en,
            'cas_code': product_id.cas_code,
            'vendor_id': self.new_vendor_id.id,
            'vendor_code': product_id.seller_ids.name.supplier_guid,
            'vendor_name': product_id.seller_ids.name.name,
            'vendor_cat_no': product_id.seller_ids.name.supplier_cat_no,
            'product_brand_name': product_id.brand_id.name,
            'package_name': product_id.package_name,
            'purchase_comment': self.new_purchase_comment,
            'product_uom_name': product_id.uom_id.name,
            'product_category_name': product_id.categ_id.name,
            'product_list_price_cny': product_id.list_price,
            'product_list_price_for': self.new_product_list_price_for,
            'product_purchase_price_cny': product_id.seller_ids.price,
            'product_purchase_price_for': self.new_product_purchase_price_for,
            'product_purchase_currency': self.new_product_purchase_currency.id,
            'currency_exchange_rate': self.new_currency_exchange_rate,
            'price_expired_date': product_id.seller_ids.date_end,
            'vendor_lead_time': product_id.seller_ids.delay,
            'vendor_lead_time_desc': self.new_vendor_lead_time_desc,
            'storage_condition': product_id.storage_condition,
            'counting_weight': product_id.counting_weight,
            'net_weight': product_id.net_weight,
            'duty_rate': self.new_duty_rate,
            'vendor_term': product_id.seller_ids.vendor_term,
            'vendor_shipment': product_id.seller_ids.vendor_shipment,
            'vendor_payment': self.new_vendor_payment.name,
            'is_discontinued': product_id.is_discontinued,
            'sale_currency': self.new_sale_currency.id,
            'external_comments': self.new_external_comments,
            'internal_comments': self.new_internal_comments,
            'product_manager_name': product_id.product_manager_name,
            'is_stockitem': product_id.is_stockitem,
            'min_order_qty': product_id.seller_ids.min_qty,
            'vendor_contact_info': self.new_vendor_contact_info,
            'concat': self.new_concat,
            'email': self.new_email,
            'product_status': product_id.product_status,
            'match_status': self.new_match_status,
            'request_quotation_line_id': self.request_quotation_line_id.id,
        }
        return val

    @api.multi
    def action_modify(self):
        val = self._prepare_modify_val()
        self.request_quotation_line_id.write(val)
        return True

    @api.multi
    def _prepare_special_supplierinfo_val(self):
        val = {
            'currency_id': self.product_purchase_currency.id,
            'price': self.product_purchase_price_cny,
            'for_price': self.product_purchase_price_for,
            'date_end': self.price_expired_date,
            'date_start': datetime.now(),
            'delay': self.vendor_lead_time,
            'vendor_term': self.vendor_term,
            'vendor_shipment': self.vendor_shipment,
            'min_qty': self.min_order_qty,
        }
        return val

    @api.multi
    def _prepare_special_sku_new_supplierinfo_val(self):
        val = {
            'name': self.sku_new_vendor_id.id,
            'currency_id': self.sku_new_product_purchase_currency.id,
            'price': self.sku_new_product_purchase_price_cny,
            'for_price': self.sku_new_product_purchase_price_for,
            'date_end': self.sku_new_price_expired_date,
            'date_start': datetime.now(),
            'delay': self.sku_new_vendor_lead_time,
            'product_id': self.product_id.id,
            'product_tmpl_id': self.product_id.product_tmpl_id.id,
            'vendor_term': self.sku_new_vendor_term,
            'vendor_shipment': self.sku_new_vendor_shipment,
            'product_name': self.product_id.name,
            'min_qty': self.sku_new_min_order_qty,
        }
        return val

    @api.multi
    def quotation_special_validate(self):
        if self.vendor_type == 'new':
            if self.sku_new_vendor_contact_id.id not in self.sku_new_vendor_id.child_ids.filtered(lambda s: s.type == 'contact').ids:
                raise UserError(u'找不到供应商联系人信息，请重新选择供应商联系人！')

            if self.sku_new_vendor_id.id in self.product_id.seller_ids.mapped('name').ids:
                raise UserError(u'添加的供应商已经配置，请选择供应商处理方式为“指定供应商”！')
        else:
            if self.vendor_contact_id.id not in self.vendor_id.child_ids.filtered(lambda s: s.type == 'contact').ids:
                raise UserError(u'找不到供应商联系人信息，请重新选择供应商联系人！')

            if not self.product_supplierinfo:
                raise UserError(u'找不到供应商信息，请重新选择供应商！')
            if self.product_supplierinfo.id not in self.product_id.seller_ids.ids:
                raise UserError(u'找不到供应商信息，请重新选择供应商！')

        return True

    @api.multi
    def action_special(self):
        quotation_model = self.env['sale.quotation']
        self.quotation_special_validate()

        if self.vendor_type == 'special':
            val = self._prepare_special_supplierinfo_val()

            self.product_supplierinfo.write(val)
        else:
            create_val = self._prepare_special_sku_new_supplierinfo_val()
            new_product_supplierinfo = self.env['product.supplierinfo'].create(create_val)
            self.product_supplierinfo = new_product_supplierinfo.id

        quotation_val = self._prepare_special_quotation_val()
        quotation_model.create(quotation_val)
        return True

    @api.multi
    def action_new_create(self):
        quotation_model = self.env['sale.quotation']
        val = self._prepare_create_product_val()
        product_id = self.env['product.product'].create(val)
        quotation_val = self._prepare_new_quotation_val(product_id)
        quotation_model.create(quotation_val)
        return True

# class ExcelQuotateWizard(models.TransientModel):
#     _name = 'excel.quotate.wizard'
#     _description = u'Excel导入报价'

#     @api.one
#     @api.depends('import_procurement_lines')
#     def _get_import_quotation_count(self):
#         self.import_procurement_count = len(self.import_procurement_lines) or 0

#     import_quotation_binary = fields.Binary(string=u'选择导入文件', help='Excel格式', required=True)
#     import_quotation_count = fields.Integer(readonly=True, compute='_get_import_quotation_count', string=u'导入报价数')
#     import_quotation_lines = fields.One2many('ehsy.import.quotation.wizard.line', 'wizard_id', string=u'导入预览')

#     @api.onchange('import_quotation_binary')
#     def onchange_import_quotation_binary(self):
#         if self.import_quotation_binary:
#             excel = xlrd.open_workbook(file_contents=base64.decodestring(self.import_quotation_binary))
#             sh = excel.sheet_by_index(0)
            

#             lines = self.make_data_from_sheet(sh)
#             self.import_procurement_lines = lines
#         else:
#             self.import_procurement_lines = []

#TODO

