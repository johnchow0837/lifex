# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Request Quotation
#----------------------------------------------------------
class SaleRequestQuotation(models.Model):
    _inherit = "sale.request.quotation"
    _description = u"客户询价单"

    @api.multi
    def _prepare_sale_order_val(self):
    	val = super(SaleRequestQuotation, self)._prepare_sale_order_val()

        pricelist_id = self.env['product.pricelist'].search([('currency_id', '=', self.required_currency.id)], limit=1)
        if not pricelist_id:
            raise UserError(u'请先配置相应货币的价格表')


        val.update({
            # 'state': 'to_approve',
            'required_currency': self.required_currency.id,
            'pricelist_id': pricelist_id.id,
        })
        return val

#----------------------------------------------------------
# Quotation
#----------------------------------------------------------
class SaleQuotation(models.Model):
    _inherit = "sale.quotation"
    _description = u"报价表"

    @api.multi
    def _prepare_sale_order_line_val(self, sale_id):
    	val = super(SaleQuotation, self)._prepare_sale_order_line_val(sale_id)

        val.update({'quotation_id': self.id})
        return val

    @api.multi
    def unlink(self):
        sale_line_model = self.env['sale.order.line']
        sale_line_id = sale_line_model.search([('quotation_id', 'in', self.ids)], limit=1)
        if sale_line_id:
            raise UserError(u'报价已经生成报价单，不能删除！')
        return super(SaleQuotation, self).unlink()