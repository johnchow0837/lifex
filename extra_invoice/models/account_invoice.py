# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Account Invoice
#----------------------------------------------------------
class AccountInvoice(models.Model):
    _inherit = "account.invoice"
    _description = u"采购单发票"

    # @api.depends('origin')
    # def get_internal_comment(self):
    # 	sale_invoices = self.filtered(lambda s: s.type in ('out_invoice', 'out_refund'))

    #     so_name = list(set(sale_invoices.mapped('origin')))
    #     sale_ids = self.env['sale.order'].search([('name', 'in', so_name)])
    #     for invoice in sale_invoices:
    #         invoice.internal_comment = sale_ids.filtered(lambda s: s.name == invoice.origin).internal_comment

    invoice_num = fields.Char(string=u'发票号码', index=True)
    invoice_code = fields.Char(string=u'发票代码', index=True)

    partner_phone = fields.Char(related='partner_id.phone', string=u'客户电话', readonly=True, required=False)
    partner_address = fields.Char(related='partner_id.street', string=u'客户地址', readonly=True, required=False)

    partner_shipping_phone = fields.Char(related='partner_shipping_id.phone', string=u'送货电话', readonly=True, required=False)
    partner_shipping_address = fields.Char(related='partner_shipping_id.street', string=u'送货详细地址', readonly=True, required=False)
    # internal_comment = fields.Char(compute="get_internal_comment", string=u'内部备注', readonly=True, help=u'销售员内部备注。')

    # @api.multi
    # def action_invoice_cancel(self):
    #     self.mapped('move_id').filtered(lambda s: s.state == 'posted').button_cancel()
    #     return super(AccountInvoice, self).action_invoice_cancel()


class AccountInvoiceLine(models.Model):
    _inherit = 'account.invoice.line'

    # def _set_additional_fields(self, invoice):
    #     super(AccountInvoiceLine, self)._set_additional_fields(invoice)
    #     if invoice.type == 'in_invoice':
    #         self.account_id = 1

#----------------------------------------------------------
# Account Payment Term
#----------------------------------------------------------
class AccountPaymentTerm(models.Model):
    _inherit = "account.payment.term"
    _description = u"付款条款"

    comment_en = fields.Char(string=u'英文描述')
    code = fields.Char(string=u'代码', required=True, index=True)
    payment_type = fields.Selection(selection=[('sale', u'销售'), ('purchase', u'采购')], string=u'条款类型', default='sale', required=True, index=True)