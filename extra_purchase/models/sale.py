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

    @api.depends('name')
    @api.multi
    def get_is_purchased(self):
    	for sale in self:
	    	po = self.env['purchase.order.line'].search([('order_id.state', '!=', 'cancel'), ('order_for', '=', sale.name)], limit=1)
	    	if po:
	    		sale.is_purchased = True
	    	else:
	    		sale.is_purchased = False

    is_purchased = fields.Boolean(compute="get_is_purchased", string=u'采购是否下单')

    # partner_shipping_mobile = fields.Char(related='partner_shipping_id.mobile', string=u'送货手机', readonly=True)
    # partner_shipping_phone = fields.Char(related='partner_shipping_id.phone', string=u'送货电话', readonly=True)

class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _description = u"销售明细"

    @api.multi
    def action_prepare_modify_qty(self):
        for line in self:
            procurement_ids = self.env['procurement.order'].search([('sale_id', '=', line.order_id.id), 
                ('product_id', '=', line.product_id.id), ('state', '!=', 'cancel')])
            if procurement_ids.mapped('purchase_line_id'):
                raise UserError(u'对应采购需求已下单，请先取消采购单！')
            quant_ids = self.env['stock.quant'].search([('order_for', '=', line.order_id.name), ('product_id', '=', line.product_id.id)])
            procurement_ids.cancel()
            procurement_ids.write({'sale_line_id': False})
            procurement_ids.mapped('move_ids').action_cancel()
            quant_ids.write({'order_for': ''})
            if line.product_uom_qty > 0:
                line._action_procurement_create()
        return True

    @api.multi
    def action_modify_qty_wizard(self):
        if self.order_id.state != 'sale':
            raise UserError(u'只有“销售订单”状态才能修改数量！')
        ctx = self.env.context.copy()
        ctx.update({'default_sale_line_id': self.id})
        return {
                'name': u'修改数量',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'sale.order.line.modify.qty',
                'type': 'ir.actions.act_window',
                'context': ctx,
                'target': 'new'
            }

