# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging
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

    @api.depends('order_line', 'order_line.cost_price', 'amount_total')
    def get_predict_margin_rate(self):
        for order in self:
            cost_total = sum([line.cost_price * line.product_uom_qty for line in order.order_line])
            if order.amount_total > 0:
                order.predict_margin_rate = round(1 - cost_total / order.amount_total, 4)
            else:
                order.predict_margin_rate = 0

    @api.depends('name')
    def _get_last_sync_time(self):
        if self.ids:
            self.env.cr.execute(
                '''select 
                    key_value,
                    max(create_date) as create_date 
                   from 
                    extra_api
                   where
                    api_type = 'order_update'
                    and
                    key_value in %s 
                   group by 
                    key_value
                   ''',
                (tuple(self.ids), )
            )
            res = self.env.cr.dictfetchall()
            for r in res:
                self.filtered(lambda s: s.id == r['key_value']).last_sync_time = r['create_date']

    @api.model
    def _get_default_required_currency(self):
        default_currency = self.env['res.currency'].search([('name', '=', 'CNY')], limit=1)
        return default_currency.id

    state = fields.Selection(selection_add=[('to_approve', u'待经理审批'), ('to_validate', u'待老板审批'), ('to_salesup_confirm', u'待销售助理确认'), ('to_confirm', u'确认发货方式')])
    shipment_method = fields.Selection(selection=[('customer', u'直发'), ('warehouse', u'中转')], string=u'发货方式', readonly=True, 
        states={'to_confirm': [('readonly', False)]}, default='warehouse')
    required_currency = fields.Many2one('res.currency', string=u'报价币种', required=True, readonly=True, states={'draft': [('readonly', False)]}, default=_get_default_required_currency)
    request_quotation_id = fields.Many2one('sale.request.quotation', string=u'客户询价单关联', ondelete='set null', index=True, copy=False, readonly=True)
    approve_reason = fields.Char(string=u'审核意见', readonly=True, states={'to_validate': [('readonly', False)], 'to_approve': [('readonly', False)]}, track_visibility='onchange')
    contract_num = fields.Char(string=u'合同号', readonly=True, states={'to_confirm': [('readonly', False)]}, track_visibility='onchange', default='')

    predict_margin_rate = fields.Float(compute="get_predict_margin_rate", string=u'预估毛利率', track_visibility='onchange', store=True)

    purchase_comment = fields.Char(string=u'采购备注', track_visibility='onchange', readonly=True, help=u'此备注将会被带入需求!', 
        states={'to_confirm': [('readonly', False)], 'draft': [('readonly', False)], 'sale': [('readonly', False)]})

    internal_comment = fields.Char(string=u'内部备注', track_visibility='onchange', readonly=True, help=u'此备注将会带入仓库、发票', 
        states={'to_confirm': [('readonly', False)], 'draft': [('readonly', False)], 'sale': [('readonly', False)]})

    partner_contact_id = fields.Many2one('res.partner', string=u'联系人地址', readonly=True, required=False, states={'draft': [('readonly', False)], 'sent': [('readonly', False)]}, help="contact address for current sales order.")


    partner_contact_phone = fields.Char(related='partner_contact_id.phone', string=u'联系人电话', readonly=True, required=False)
    partner_contact_address = fields.Char(related='partner_contact_id.street', string=u'联系人详细地址', readonly=True, required=False)

    last_sync_time = fields.Datetime(compute='_get_last_sync_time', store=False, readonly=True, string=u'最后同步时间')

    @api.multi
    def sync_so_update(self):
        '''so update:odoo to opc'''
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for so in self:
            data = {
                'sale_order_id': so.name,
                'update_user': so.write_uid.name,
                'update_time': (datetime.strptime(so.write_date, '%Y-%m-%d %H:%M:%S') + timedelta(hours=8)).strftime('%Y-%m-%d %H:%M:%S'),
                'discount_amount': so.discount_amount,
                'transfer_amount': so.transfer_amount,
                'total_amount': so.total_amount,
            }
            product_list = []
            for line in so.order_line:
                product_list.append({
                        'sku_code': line.product_id.default_code,
                        'sale_price': line.price_unit,
                        'quantity': line.product_uom_qty,
                        'unit': line.product_uom.name,
                        'sub_total_amount': line.price_total,
                        'user_product_no': line.user_product_no,
                    })
            data.update({'product_list': json.dumps(product_list)})
            api_val = {
                'api_type': 'order_update',
                'http_method': 'post',
                'data_model': 'sale.order',
                'key_value': so.id,
                'data': data,
                'url': '?route=rest/sale/order/edit',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

    @api.model
    def create(self, vals):
        if any(f not in vals for f in ['partner_invoice_id', 'partner_shipping_id', 'pricelist_id', 'partner_contact_id']):
            partner = self.env['res.partner'].browse(vals.get('partner_id'))
            # addr = partner.address_get(['delivery', 'invoice'])
            # vals['partner_invoice_id'] = vals.setdefault('partner_invoice_id', addr['invoice'])
            # vals['partner_shipping_id'] = vals.setdefault('partner_shipping_id', addr['delivery'])
            # vals['partner_contact_id'] = vals.setdefault('partner_contact_id', addr['contact'])
            vals['pricelist_id'] = vals.setdefault('pricelist_id', partner.property_product_pricelist and partner.property_product_pricelist.id)
        result = super(SaleOrder, self).create(vals)
        return result

    # @api.onchange('partner_id')
    # def onchange_partner_id_warning(self):
    #     partner = self.partner_id
    #     if partner:
    #         if partner.sale_warn == 'no-message' and partner.parent_id:
    #             partner = partner.parent_id
    #         if partner.sale_warn != 'no-message':
    #             # Block if partner only has warning but parent company is blocked
    #             if partner.sale_warn != 'block' and partner.parent_id and partner.parent_id.sale_warn == 'block':
    #                 partner = partner.parent_id
    #             if partner.sale_warn == 'block':
    #                 self.update({'partner_contact_id': False})
    #     return super(SaleOrder, self).onchange_partner_id_warning()

    @api.multi
    @api.onchange('partner_id')
    def onchange_partner_id(self):
        # if not self.partner_id:
        #     self.update({'partner_contact_id': False})
        # else:
        #     addr = self.partner_id.address_get(['delivery', 'invoice'])
        #     self.update({'partner_contact_id': addr['contact']})
        res = super(SaleOrder, self).onchange_partner_id()
        self.partner_invoice_id = False
        self.partner_shipping_id = False
        return res

    @api.multi
    @api.onchange('partner_shipping_id')
    def onchange_partner_shipping_id(self):
        if self.partner_shipping_id:
            self.address_info_name = self.partner_shipping_id.name
            self.address_info_company_name = self.partner_shipping_id.parent_id.name
            self.address_info_mobile = self.partner_shipping_id.mobile
            self.address_info_telephone = self.partner_shipping_id.phone
            self.address_info_address = self.partner_shipping_id.street
            self.address_info_postcode = self.partner_shipping_id.zip
        else:
            self.address_info_name = ''
            self.address_info_company_name = ''
            self.address_info_mobile = ''
            self.address_info_telephone = ''
            self.address_info_address = ''
            self.address_info_postcode = ''

    @api.multi
    @api.onchange('partner_invoice_id')
    def onchange_partner_invoice_id(self):
        if self.partner_invoice_id:
            self.receipt_address_info_name = self.partner_invoice_id.name
            self.receipt_address_info_mobile = self.partner_invoice_id.mobile
            self.receipt_address_info_telephone = self.partner_invoice_id.phone
            self.receipt_address_info_address = self.partner_invoice_id.street
            self.receipt_address_info_postcode = self.partner_invoice_id.zip
        else:
            self.receipt_address_info_name = ''
            self.receipt_address_info_mobile = ''
            self.receipt_address_info_telephone = ''
            self.receipt_address_info_address = ''
            self.receipt_address_info_postcode = ''

    @api.multi
    def action_commit(self):
        records = self.filtered(lambda s: s.state == 'draft')
        records.filtered(lambda s: s.predict_margin_rate > 0.17).write({'state': 'to_salesup_confirm'})
        records.filtered(lambda s: s.predict_margin_rate <= 0.17).write({'state': 'to_approve'})
        
        return True

    @api.multi
    def action_approve(self):
        records = self.filtered(lambda s: s.state == 'to_approve')
        records.filtered(lambda s: s.predict_margin_rate > 0.05).write({'state': 'to_salesup_confirm'})
        records.filtered(lambda s: s.predict_margin_rate <= 0.05).write({'state': 'to_validate'})

        return True

    @api.multi
    def action_not_approve(self):
        records = self.filtered(lambda s: not s.approve_reason)
        if records:
            raise UserError(u'审核不通过时，必须填入审核意见！')
        self.filtered(lambda s: s.state == 'to_approve').write({'state': 'draft', 'shipment_method': False})
        self.mapped('order_line').write({'route_id': False, 'warehouse_id': False})
        return True

    @api.multi
    def action_reset_to_draft(self):
        records = self.filtered(lambda s: s.state == 'to_confirm').write({'state': 'draft', 'shipment_method': False})
        self.mapped('order_line').write({'route_id': False, 'warehouse_id': False})
        return True

    @api.multi
    def action_not_validate(self):
        records = self.filtered(lambda s: not s.approve_reason)
        if records:
            raise UserError(u'审核不通过时，必须填入审核意见！')
        self.filtered(lambda s: s.state == 'to_validate').write({'state': 'draft', 'shipment_method': False})
        self.mapped('order_line').write({'route_id': False, 'warehouse_id': False})
        return True

    @api.multi
    def action_validate(self):
        self.filtered(lambda s: s.state == 'to_validate').write({'state': 'to_salesup_confirm'})
        return True

    @api.multi
    def action_salesup_confirm(self):
        self.filtered(lambda s: s.state == 'to_salesup_confirm').write({'state': 'to_confirm'})
        return True

    @api.multi
    def action_not_salesup_confirm(self):
        records = self.filtered(lambda s: not s.approve_reason)
        if records:
            raise UserError(u'审核不通过时，必须填入审核意见！')
        self.filtered(lambda s: s.state == 'to_salesup_confirm').write({'state': 'draft'})
        return True

    @api.multi
    def _validate_sale_order_data(self):
        records = self.filtered(lambda s: not s.shipment_method)
        if records:
            raise UserError(u'发货方式不能为空')
        return True

    @api.multi
    def config_sale_route(self):
        ir_model = self.env['ir.model.data']
        for order in self:
            if order.shipment_method == 'customer':
                customoer_route = ir_model.get_object('extra_sale', 'stock_customer_transit_route')
                order.order_line.write({'route_id': customoer_route.id})
            else:
                order.order_line.filtered(lambda s: not s.warehouse_id).write({'warehouse_id': order.warehouse_id.id})
                order.order_line.write({'route_id': False})
        return True

    @api.multi
    def check_partner_trust(self):
        bad_trust_partner = self.mapped('partner_id').filtered(lambda s: s.trust == 'bad')
        if bad_trust_partner:
            raise UserError(u'客户信用为【差】, 不能确认订单！')
        return True

    @api.multi
    def action_confirm(self):

        self._validate_sale_order_data()
        self.config_sale_route()
        self.check_partner_trust()
        res = super(SaleOrder, self).action_confirm()
        return res

    @api.multi
    def action_unlock(self):
        self.filtered(lambda s: s.state == 'done').write({'state': 'sale'})

    @api.multi
    def export_excel(self):
        book = xlwt.Workbook()
        sheet = book.add_sheet(u'未税含税报价单', cell_overwrite_ok=True)

        title_style = xlwt.easyxf('font: bold true, height 300;', num_format_str='#,##0.00')
        title1_style = xlwt.easyxf('font: bold true, height 300; align: wrap on, vert centre, horiz center;', num_format_str='#,##0.00')
        title2_style = xlwt.easyxf('font: bold true; align: wrap on, vert centre, horiz right;', num_format_str='#,##0.00')
        title3_style = xlwt.easyxf('font: bold true; align: wrap on, horiz right;', num_format_str='#,##0.00')
        info_bold_center = xlwt.easyxf('font: bold true; align: wrap on, vert centre, horiz centre;', num_format_str='#,##0.00')
        info_bold_left = xlwt.easyxf('font: bold true; align: wrap on, vert centre, horiz left;', num_format_str='#,##0.00')
        info_left = xlwt.easyxf('font: bold false; align: wrap on, vert centre, horiz left;', num_format_str='#,##0.00')
        info_center = xlwt.easyxf('font: bold false; align: wrap on, vert centre, horiz centre;', num_format_str='#,##0.00')
        wrap_cell = xlwt.easyxf('align: wrap on;', num_format_str='#,##0.00')

        info_center_bold_border = xlwt.easyxf('font: bold true; align: wrap on, vert centre, horiz centre; borders: bottom medium, top medium, left medium, right medium', num_format_str='#,##0.00')
        info_center_no_bold_border = xlwt.easyxf('font: bold false; align: wrap on, vert centre, horiz centre; borders: bottom medium, top medium, left medium, right medium', num_format_str='#,##0.00')

        sheet.write_merge(0, 2, 0, 11, '')
        sheet.write_merge(0, 1, 8, 11, self.company_id.name or u'', title_style)
        sheet.write_merge(2, 2, 9, 11, u'服务热线：4009-20-3909', title3_style)
        sheet.write_merge(3, 3, 0, 11, u'报价单', title1_style)
        sheet.write_merge(4, 4, 0, 7, u'报价单编码:', title2_style)
        sheet.write_merge(5, 5, 0, 7, u'报价日期：:', title2_style)
        sheet.write_merge(4, 4, 8, 11, self.name, info_bold_center)
        sheet.write_merge(5, 5, 8, 11, datetime.now().strftime('%Y-%m-%d'), info_bold_center)

        sheet.write_merge(6, 6, 0, 0, u'客户公司：')
        sheet.write_merge(7, 7, 0, 0, u'接收人：')
        sheet.write_merge(8, 8, 0, 0, u'联系方式：')
        sheet.write_merge(9, 9, 0, 0, u'电子邮箱：')
        sheet.write_merge(10, 10, 0, 11, u'报价有效期：')
        sheet.write_merge(6, 6, 6, 6, u'报价公司：')
        sheet.write_merge(7, 7, 6, 6, u'销售人员：')
        sheet.write_merge(8, 8, 6, 6, u'联系方式：')
        sheet.write_merge(9, 9, 6, 6, u'电子邮箱：')
        sheet.write_merge(6, 6, 1, 5, self.partner_id.name, info_bold_center)
        sheet.write_merge(6, 6, 7, 11, self.company_id.name, info_bold_center)
        sheet.write_merge(7, 7, 1, 5, self.partner_contact_id.name, info_bold_center)
        sheet.write_merge(7, 7, 7, 11, self.user_id.name, info_bold_center)
        sheet.write_merge(8, 8, 1, 5, (self.partner_contact_id.mobile or self.partner_contact_id.phone) or (self.partner_invoice_id.mobile or self.partner_invoice_id.phone) or '', info_bold_center)
        sheet.write_merge(8, 8, 7, 11, self.user_id.mobile or self.user_id.phone or '', info_bold_center)
        sheet.write_merge(9, 9, 1, 5, self.partner_contact_id.email or '', info_bold_center)
        sheet.write_merge(9, 9, 7, 11, self.user_id.email, info_bold_center)

        sheet.write_merge(11, 11, 0, 11, u'阁下如有需要，请在下面补充完整收货及发票信息并回传至我司为您提供服务的销售人员，谢谢！', info_center)
        sheet.write_merge(12, 12, 0, 11, '', info_center)

        sheet.write_merge(13, 13, 0, 11, u'报价主题：    报价', info_bold_left)
        sheet.write_merge(14, 14, 0, 11, u'尊敬的' + self.partner_id.name + u'先生/小姐，', info_left)

        sheet.write_merge(15, 15, 0, 11, 
            u'非常感谢阁下对{company}的关注及支持，我们很高兴将阁下所需产品的相关信息及报价提供给您，并深感荣幸！如果与阁下及贵司有进一步的合作，相信会是愉快的，富有成效的！'.format(company=self.company_id.name),
        info_left)


        sheet.write_merge(16, 16, 0, 0, u'序号', info_center_bold_border)
        sheet.write_merge(16, 16, 1, 2, u'产品描述', info_center_bold_border)
        sheet.write_merge(16, 16, 3, 3, u'品牌', info_center_bold_border)
        sheet.write_merge(16, 16, 4, 4, u'原厂货号', info_center_bold_border)
        sheet.write_merge(16, 16, 5, 5, u'货期', info_center_bold_border)
        sheet.write_merge(16, 16, 6, 6, u'包装单位', info_center_bold_border)
        sheet.write_merge(16, 16, 7, 7, u'数量', info_center_bold_border)
        sheet.write_merge(16, 16, 8, 8, u'未税单价', info_center_bold_border)
        sheet.write_merge(16, 16, 9, 9, u'含税单价', info_center_bold_border)
        sheet.write_merge(16, 16, 10, 10, u'含税总价', info_center_bold_border)
        sheet.write_merge(16, 16, 11, 11, u'备注（选填）', info_center_bold_border)

        n = 1
        line_count = 17
        for line in self.order_line:
            sheet.write_merge(line_count, line_count, 0, 0, n, info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 1, 2, line.product_id.comment_desc_cn, info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 3, 3, line.product_id.brand_id.name, info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 4, 4, line.product_id.product_model or '', info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 5, 5, line.customer_lead, info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 6, 6, line.product_id.uom_id.name, info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 7, 7, line.product_uom_qty, info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 8, 8, round(line.price_subtotal / line.product_uom_qty, 2), info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 9, 9, line.price_unit, info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 10, 10, line.price_total, info_center_no_bold_border)
            sheet.write_merge(line_count, line_count, 11, 11, line.external_comments or '', info_center_no_bold_border)
            n += 1
            line_count += 1

        sheet.write_merge(line_count, line_count, 0, 0, u'运费', info_center_bold_border)
        sheet.write_merge(line_count + 1, line_count + 1, 0, 0, u'税额', info_center_bold_border)
        sheet.write_merge(line_count + 2, line_count + 2, 0, 0, u'总额', info_center_bold_border)

        sheet.write_merge(line_count, line_count, 1, 11, 0, info_center_bold_border)
        sheet.write_merge(line_count + 1, line_count + 1, 1, 11, self.amount_tax, info_center_bold_border)
        sheet.write_merge(line_count + 2, line_count + 2, 1, 11, self.amount_total, info_center_bold_border)

        sheet.write_merge(line_count + 3, line_count + 3, 0, 11, u'', info_center_bold_border)
        sheet.write_merge(line_count + 4, line_count + 4, 0, 11, '', info_center_bold_border)

        sheet.write_merge(line_count + 5, line_count + 5, 0, 11, 
            u'1.本报价单受{company}销售条款的约束。本报价单一旦签订（贵司在本报价单上签字盖章并回传{company}即表明本报价单已签订），不论{company}销售条款是否经双方签署，即表明贵司已经阅读并知悉{company}销售条款的内容，且同意受其约束。'.format(company=self.company_id.name), 
        info_left)
        sheet.write_merge(line_count + 6, line_count + 6, 0, 11, u'2. 付款条件: ' + (self.payment_term_id.name or ''), info_left)

        sheet.write_merge(line_count + 7, line_count + 7, 0, 11, u'3. 交货期为估计值，会根据收到订单时的实际库存情况有所调整，交货期从收到预付款之日起算。 ', info_left)
        sheet.write_merge(line_count + 8, line_count + 8, 0, 11, u'4. 质保期：安装调试后12个月或发货后15个月，以先到者为准。', info_left)
        sheet.write_merge(line_count + 9, line_count + 9, 0, 11, 
            u'5. {company}不负责产品的具体应用。请在订购前务必仔细察看{company}的目录或网站及生产厂商的产品规格。'.format(company=self.company_id.name), 
        info_left)
        sheet.write_merge(line_count + 10, line_count + 10, 0, 11, u'6. {company}保留取消受进出口管制的产品的权利。'.format(company=self.company_id.name), info_left)
        sheet.write_merge(line_count + 11, line_count + 11, 0, 11, u'7. 允许分批发货。', info_left)
        sheet.write_merge(line_count + 12, line_count + 12, 0, 11, u'8. 我司银行信息：a) 上海银行张江支行  b) 03003630381。', info_left)
        sheet.write_merge(line_count + 13, line_count + 13, 0, 11, u'如果您还有任何问题，非常欢迎与我们联系。', info_left)
        sheet.write_merge(line_count + 14, line_count + 14, 0, 11, '', info_left)
        sheet.write_merge(line_count + 15, line_count + 15, 0, 11, '', info_left)
        sheet.write_merge(line_count + 16, line_count + 16, 0, 11, u'客户收货及发票信息确认', title1_style)

        sheet.write_merge(line_count + 17, line_count + 17, 0, 0, u'发票接收：', info_center_no_bold_border)
        sheet.write_merge(line_count + 17, line_count + 17, 1, 4, self.partner_invoice_id.company_title_name or '', info_center_no_bold_border)
        sheet.write_merge(line_count + 17, line_count + 17, 5, 5, u'货物接收：', info_center_no_bold_border)
        sheet.write_merge(line_count + 17, line_count + 17, 6, 11, self.partner_shipping_id.company_title_name or '', info_center_no_bold_border)

        sheet.write_merge(line_count + 18, line_count + 18, 0, 0, u'接收人：', info_center_no_bold_border)
        sheet.write_merge(line_count + 18, line_count + 18, 1, 4, self.partner_invoice_id.name, info_center_no_bold_border)
        sheet.write_merge(line_count + 18, line_count + 18, 5, 5, u'接收人：', info_center_no_bold_border)
        sheet.write_merge(line_count + 18, line_count + 18, 6, 11, self.partner_shipping_id.name, info_center_no_bold_border)

        sheet.write_merge(line_count + 19, line_count + 19, 0, 0, u'联系方式：', info_center_no_bold_border)
        sheet.write_merge(line_count + 19, line_count + 19, 1, 4, self.partner_invoice_id.mobile or self.partner_invoice_id.phone or '', info_center_no_bold_border)
        sheet.write_merge(line_count + 19, line_count + 19, 5, 5, u'联系方式：', info_center_no_bold_border)
        sheet.write_merge(line_count + 19, line_count + 19, 6, 11, self.partner_shipping_id.mobile or self.partner_shipping_id.phone or '', info_center_no_bold_border)

        sheet.write_merge(line_count + 20, line_count + 20, 0, 0, u'地址：', info_center_no_bold_border)
        sheet.write_merge(line_count + 20, line_count + 20, 1, 4, self.partner_invoice_id.street or '', info_center_no_bold_border)
        sheet.write_merge(line_count + 20, line_count + 20, 5, 5, u'地址：', info_center_no_bold_border)
        sheet.write_merge(line_count + 20, line_count + 20, 6, 11, self.partner_shipping_id.street or '', info_center_no_bold_border)

        sheet.write_merge(line_count + 21, line_count + 21, 0, 0, u'纳税人识别号', info_center_no_bold_border)
        sheet.write_merge(line_count + 21, line_count + 21, 1, 4, self.partner_id.customer_taxpayer_number or '', info_center_no_bold_border)
        sheet.write_merge(line_count + 21, line_count + 21, 5, 5, u'发票类型：', info_center_no_bold_border)
        sheet.write_merge(line_count + 21, line_count + 21, 6, 11, self.partner_id.customer_invoice_type == 'common_vat' and u'普票' or u'增票', info_center_no_bold_border)

        sheet.write_merge(line_count + 22, line_count + 22, 0, 0, u'注册地址：', info_center_no_bold_border)
        sheet.write_merge(line_count + 22, line_count + 22, 1, 4, self.partner_id.customer_invoice_address or '', info_center_no_bold_border)
        sheet.write_merge(line_count + 22, line_count + 22, 5, 5, u'注册电话：', info_center_no_bold_border)
        sheet.write_merge(line_count + 22, line_count + 22, 6, 11, self.partner_id.customer_invoice_phone or '', info_center_no_bold_border)

        sheet.write_merge(line_count + 23, line_count + 23, 0, 0, u'开户银行：', info_center_no_bold_border)
        sheet.write_merge(line_count + 23, line_count + 23, 1, 4, self.partner_id.customer_invoice_bank or '', info_center_no_bold_border)
        sheet.write_merge(line_count + 23, line_count + 23, 5, 5, u'银行账号：', info_center_no_bold_border)
        sheet.write_merge(line_count + 23, line_count + 23, 6, 11, self.partner_id.customer_invoice_account or '', info_center_no_bold_border)

        sheet.write_merge(line_count + 24, line_count + 24, 0, 11, '', info_center_no_bold_border)
        sheet.write_merge(line_count + 25, line_count + 25, 0, 11, u'阁下如有其他任何问题或任何我可协助的事宜 , 敬请随时与我或{company}客服中心联系,谢谢!'.format(company=self.company_id.name), info_left)
        sheet.write_merge(line_count + 26, line_count + 26, 0, 11, u'真诚希望再次有机会服务于阁下及令人尊敬的贵司!', info_left)

        fp = StringIO()
        book.save(fp)
        fp.seek(0)
        file_data = fp.read()
        fp.close()

        file_name = base64.encodestring(file_data)

        attach_vals = {
             'name':'quotation_' + self.name +'%s'%datetime.now().strftime('%Y-%m-%d %H:%M:%S') + '.xls',
             'datas':file_name,
             'datas_fname':u'询价单' + self.name + '.xls'
        }

        doc_id = False
        try:
            attach_obj = self.env['ir.attachment']
            doc_id = attach_obj.create(attach_vals)
        except Exception, ex:
            raise UserError(ex)
        if doc_id:
            return {
                'type': 'ir.actions.act_url',
                'url': '/web/content/%s?download=true' %(doc_id.id),
                'target': 'self',
                'name': "Redirect to the excel file",
                }

        return True


    #     res = self.action_get_account_report(start_date, end_date)

    #     x = 2

    #     for r in res:
    #         sheet.write(x, 1, r['account_code'])
    #         sheet.write(x, 2, r['account_name'])
    #         sheet.write(x, 4, r['start_debit'])
    #         sheet.write(x, 5, r['start_credit'])
    #         sheet.write(x, 6, r['product_debit'])
    #         sheet.write(x, 7, r['product_credit'])
    #         sheet.write(x, 8, r['year_debit'])
    #         sheet.write(x, 9, r['year_credit'])
    #         sheet.write(x, 10, r['end_debit'])
    #         sheet.write(x, 11, r['end_credit'])
    #         x += 1

    #     book.save(response.stream)
    #     return response

class SaleOrderLine(models.Model):
    _inherit = "sale.order.line"
    _description = u"销售单明细"

    @api.depends('price_subtotal', 'product_uom_qty')
    def _get_tax_price(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            if line.product_uom_qty > 0:

                line.update({
                    'price_unit_untaxed': line.price_subtotal / line.product_uom_qty,
                })

    quotation_id = fields.Many2one(
        'sale.quotation', string=u'报价表关联', 
         ondelete='set null', readonly=True)

    price_unit_untaxed = fields.Float(string=u'未税单价', compute="_get_tax_price", readonly=True, digits=dp.get_precision('Product Price'), default=0.0, store=True)

    @api.depends('order_id.required_currency', 'product_id', 'price_subtotal', 'product_uom_qty')
    def _get_price(self):
        for line in self:
            line.sale_price = line.product_id.pricelist_currency_ids.filtered(lambda s: s.currency_id == line.order_id.required_currency).price
            line.cost_price = line.product_id.costlist_currency_ids.filtered(lambda s: s.currency_id == line.order_id.required_currency).price

            line.predict_margin = line.price_subtotal - line.cost_price * line.product_uom_qty

    sale_price = fields.Float(string=u'销售牌价', readonly=True, compute="_get_price", store=True, digits=dp.get_precision('Product Price'))
    cost_price = fields.Float(string=u'标准成本', readonly=True, compute="_get_price", store=True, digits=dp.get_precision('Product Price'))
    predict_margin = fields.Float(string=u'预估毛利', compute="_get_price", readonly=True, store=True)

    cat_no = fields.Char(related='product_id.cat_no', string=u'原厂货号', store=True, index=True)
    brand_id = fields.Many2one(related='product_id.brand_id', string=u'品牌', relation='product.brand', store=True, index=True)
    product_tag = fields.Char(related='product_id.product_tag', string=u'产品标签', store=True, index=True)

    comment_desc_cn = fields.Char(related='product_id.comment_desc_cn', string=u'中文描述', store=True, index=True)

    warehouse_id = fields.Many2one(
        'stock.warehouse', string=u'仓库', readonly=True, states={'to_confirm': [('readonly', False)]})

    @api.multi
    def _prepare_order_line_procurement(self, group_id=False):
        vals = super(SaleOrderLine, self)._prepare_order_line_procurement(group_id=group_id)
        vals.update({
            'warehouse_id': self.warehouse_id.id or self.order_id.warehouse_id.id or False,
        })
        return vals

    @api.onchange('product_uom_qty', 'product_uom', 'route_id')
    def _onchange_product_id_check_availability(self):
        return {}

#----------------------------------------------------------
# Account Invoice
#----------------------------------------------------------
class AccountInvoice(models.Model):
    _inherit = "account.invoice"
    _description = u"采购单发票"

    @api.depends('origin')
    def get_internal_comment(self):
        sale_invoices = self.filtered(lambda s: s.type in ('out_invoice', 'out_refund'))

        so_name = list(set(sale_invoices.mapped('origin')))
        sale_ids = self.env['sale.order'].search([('name', 'in', so_name)])
        for invoice in sale_invoices:
            invoice.internal_comment = sale_ids.filtered(lambda s: s.name == invoice.origin).internal_comment

    internal_comment = fields.Char(compute="get_internal_comment", string=u'内部备注', readonly=True, help=u'销售员内部备注。')

class SaleReport(models.Model):
    _inherit = "sale.report"

    cat_no = fields.Char(string=u'原厂货号', readonly=True)
    brand_id = fields.Many2one('product.brand', string=u'品牌', readonly=True)
    product_tag = fields.Char(string=u'产品标签', readonly=True)

    def _select(self):
        select_str = super(SaleReport, self)._select()
        select_str += """,l.cat_no as cat_no,
                            l.brand_id as brand_id,
                              l.product_tag as product_tag"""
        return select_str

    def _group_by(self):
        group_by_str = super(SaleReport, self)._group_by()
        group_by_str += """,l.cat_no,l.brand_id,l.product_tag"""
        return group_by_str