# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, models, fields, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

class QuotationCreateSaleWizard(models.TransientModel):
    _name = 'quotation.create.sale.wizard'
    _description = u'报价单窗口'

    quotation_create_sale_lines = fields.One2many('quotation.create.sale.wizard.line', 'wizard_id', string=u'报价单明细')

    @api.multi
    def action_quotation_sale(self):
        self.quotation_create_sale_lines._validate_quotation_line_wizard_data()
        request_quotation_id = self.mapped('quotation_create_sale_lines.request_quotation_line_id.request_quotation_id')
        sale_val = request_quotation_id._prepare_sale_order_val()
        sale_id = self.env['sale.order'].create(sale_val)
        sale_line_model = self.env['sale.order.line']
        for line in self.quotation_create_sale_lines:
            sale_line_val = line.quotation_id._prepare_sale_order_line_val(sale_id)
            extra_sale_line_val = line._prepare_extra_sale_line_val()
            sale_line_val.update(extra_sale_line_val)
            sale_line_id = sale_line_model.create(sale_line_val)


class QuotationCreateSaleWizardLine(models.TransientModel):
    _name = 'quotation.create.sale.wizard.line'
    _description = u'报价单明细窗口'

    wizard_id = fields.Many2one('quotation.create.sale.wizard', required=True, ondelete='cascade')
    request_quotation_line_id = fields.Many2one(
        relation='sale.request.quotation.line', string=u'客户询价表关联', 
        ondelete='cascade', readonly=True, related="quotation_id.request_quotation_line_id", store=True)

    quotation_id = fields.Many2one(
        'sale.quotation', string=u'报价表关联', 
        required=True, ondelete='cascade', readonly=True)

    product_id = fields.Many2one("product.product", readonly=True, string=u"商品")
    default_code = fields.Char(string=u'系统编号', readonly=True)
    cat_no = fields.Char(string=u'产品编号', readonly=True)
    tax_id = fields.Many2one('account.tax', readonly=True, required=True, string=u'税率')
    comment_desc_cn = fields.Char(string=u'产品中文描述', readonly=True)
    product_list_price_cny = fields.Float(string=u'产品牌价(人民币)', readonly=True,)
    product_purchase_price_cny = fields.Float(string=u'采购成本(人民币)', readonly=True)
    product_uom_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'))
    price_unit = fields.Float(string=u'销售单价', required=True, default=0, digits=dp.get_precision('Product Price'))
    vendor_lead_time = fields.Float(string=u'货期', required=True)
    product_uom = fields.Many2one('product.uom', string=u'单位', readonly=True, required=True)
    external_comments = fields.Char(string=u'外部备注')

    @api.multi
    def _prepare_extra_sale_line_val(self):
        val = {
                'product_uom_qty': self.product_uom_qty, 
                'customer_lead': self.vendor_lead_time,
                'price_unit': self.price_unit,
                'product_uom': self.product_uom.id,
                'external_comments': self.external_comments,
            }
        return val

    @api.multi
    def _validate_quotation_line_wizard_data(self):
        request_quotation_id = self.mapped('request_quotation_line_id.request_quotation_id')
        if len(request_quotation_id) != 1:
            raise UserError(u'只能同时对一张客户询价单进行报价')

        if self.filtered(lambda s: s.price_unit <= 0):
            raise UserError(u'请设置正确的金额！')
        return True