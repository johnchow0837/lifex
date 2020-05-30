# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from lxml import etree
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


#----------------------------------------------------------
# Procurement Make Po Wizard
#----------------------------------------------------------
class ProcurementMakePoWizard(models.TransientModel):
    _name = 'procurement.make.po.wizard'
    _description = u'采购需求创建采购单'

    # purchase_id = fields.Many2one('purchase.order', string=u'合并采购单')
    date_planned = fields.Datetime(string=u'计划日期', required=True)

    @api.multi
    def action_make_po(self):
        procurement_ids = self.env['procurement.order'].browse(self.env.context.get('active_ids', []))
        procurement_ids.write({'date_planned': self.date_planned, 'state': 'running'})
        procurement_ids.make_po_new()
        return True

#----------------------------------------------------------
# Procurement Cancel Wizard
#----------------------------------------------------------
class ProcurementCancelWizard(models.TransientModel):
    _name = 'procurement.cancel.wizard'
    _description = u'取消需求导航'

    @api.multi
    def action_cancel(self):
        procurement_ids = self.env['procurement.order'].browse(self.env.context.get('active_ids', []))
        procurement_ids.filtered(lambda s: s.state == 'exception' and not s.move_dest_id).cancel()
        return True

#----------------------------------------------------------
# Procurement Split Wizard
#----------------------------------------------------------
class ProcurementSplitWizard(models.TransientModel):
    _name = 'procurement.split.wizard'
    _description = u'拆分需求导航'

    procurement_id = fields.Many2one('procurement.order', string=u'拆分需求', required=True, readonly=True)
    procurement_qty = fields.Float(related='procurement_id.product_qty', string=u'原数量', readonly=True)
    split_qty = fields.Integer(string=u'拆分数量', required=True, default=0)

    @api.multi
    def action_split(self):
        if self.split_qty < 1 or self.split_qty > self.procurement_id.product_qty:
            raise UserError(u'拆分数量至少为1且不能大于被拆分需求的数量！')

        if self.procurement_id.state != 'exception' or self.procurement_id.purchase_line_id:
            raise UserError(u'只能拆分未被确认的需求！')

        self.procurement_id.procurement_split(split_qty=self.split_qty)

        return True


#----------------------------------------------------------
# Procurement dtot Wizard
#----------------------------------------------------------
class ProcurementDtotWizard(models.TransientModel):
    _name = 'procurement.dtot.wizard'
    _description = u'直发转非直发'

    tips = fields.Text(string=u'提示：', readonly=True)
    warehouse_id = fields.Many2one(
        'stock.warehouse', string=u'仓库', required=True)

    @api.multi
    def action_dtot_transfer(self):
        procurement_ids = self.env['procurement.order'].browse(self.env.context.get('active_ids'))
        procurement_ids.action_dtot_transfer(self.warehouse_id)
        return True

#----------------------------------------------------------
# Procurement ttod Wizard
#----------------------------------------------------------
class ProcurementTtodWizard(models.TransientModel):
    _name = 'procurement.ttod.wizard'
    _description = u'非直发转直发'

    tips = fields.Text(string=u'提示：', readonly=True)

    @api.multi
    def action_ttod_transfer(self):
        procurement_ids = self.env['procurement.order'].browse(self.env.context.get('active_ids'))
        procurement_ids.action_ttod_transfer()
        return True

#----------------------------------------------------------
# sale.order.line.modify.qty
#----------------------------------------------------------
class SaleOrderLineModifyQty(models.TransientModel):
    _name = 'sale.order.line.modify.qty'
    _description = u'修改数量'

    sale_line_id = fields.Many2one('sale.order.line', required=True, readonly=True)
    qty = fields.Float(string=u'数量', required=True)

    @api.multi
    def action_modify_qty(self):
        if self.qty < 0:
            raise UserError(u'数量不能小于0')
        if self.sale_line_id.order_id.state != 'sale':
            raise UserError(u'只有“销售订单”状态下才能修改数量！')
        self.sale_line_id.write({'product_uom_qty': self.qty})
        self.sale_line_id.action_prepare_modify_qty()
        return True

#----------------------------------------------------------
# stock quant modify order_for wizard
#----------------------------------------------------------
class StockQuantModifyWizard(models.TransientModel):
    _name = 'stock.quant.modify.wizard'
    _description = u'修改所属单号'

    order_for = fields.Char(u'所属单号')

    @api.multi
    def action_modify_order_for(self):
        quant_ids = self.env['stock.quant'].browse(self.env.context.get('active_ids', []))
        quant_ids.write({'order_for': self.order_for})
        return True