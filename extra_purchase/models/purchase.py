# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Purchase Order
#----------------------------------------------------------
class PurchaseOrder(models.Model):
    _inherit = "purchase.order"
    _description = u"采购单"

    @api.depends('order_line','order_line.product_qty', 'order_line.delivery_lines', 
        'order_line.delivery_lines.product_id', 'order_line.delivery_lines.send_quantity')
    def _get_pogoodsstatus(self):
        for po in self:
            order_line = po.order_line.filtered(lambda s: s.product_id.type == 'product')

            delivery_lines = order_line.mapped('delivery_lines')

            if not delivery_lines:
                po.delivery_status = 'no'
                continue

            init_delivery_status = 'yes'
            for line in order_line:
                deliverys = line.delivery_lines.filtered(lambda s: s.product_id.id == line.product_id.id)
                sum_qty = sum([delivery.send_quantity for delivery in deliverys]) if deliverys else 0
                if line.product_qty - sum_qty > 0.01:
                    init_delivery_status = 'partial'
                    break
            po.delivery_status = init_delivery_status

    @api.depends('order_line', 'order_line.product_qty', 'order_line.move_ids', 'order_line.move_ids.state', 'order_line.move_ids.product_uom_qty')
    def _get_po_goods_in_status(self):
        for po in self:
            po_goods_in_status = 'no'
            po_last_in_datetime = False
            send_status = []
            for line in po.order_line.filtered(lambda s: s.product_id.type != 'service'):
                sum_qty = 0
                for move in line.move_ids.filtered(lambda s: s.state == 'done' and s.location_id.usage == 'supplier'):
                    sum_qty += move.product_uom_qty
                    if not po_last_in_datetime:
                        po_last_in_datetime = move.date
                    else:
                        if po_last_in_datetime < move.date:
                            po_last_in_datetime = move.date
                if abs(line.product_qty - sum_qty) > 0.01:
                    if sum_qty > 0.01:
                        send_status.append('partial')
                        break
                    else:
                        send_status.append('no')
                        continue
                elif abs(line.product_qty - sum_qty) < 0.01:
                    send_status.append('yes')
                    continue
            if set(send_status) == set(['no']):
                po_goods_in_status = 'no'
            elif set(send_status) == set(['yes']):
                po_goods_in_status = 'yes'
            else:
                if po.order_line:
                    po_goods_in_status = 'partial'
            po.po_goods_in_status = po_goods_in_status
            po.po_last_in_datetime = po_last_in_datetime

    shipment_method = fields.Selection(selection=[('customer', u'直发'), ('warehouse', u'中转'), ('stocking', u'备货'), ('other', u'其他')], string=u'订单类型', readonly=True, 
        default='warehouse')
    partner_shipping_name = fields.Char(string=u'收货人', readonly=True, index=True)
    partner_shipping_address = fields.Char(string=u'收货地址', readonly=True, index=True)
    partner_shipping_mobile = fields.Char(string=u'收货手机', readonly=True, index=True)
    partner_shipping_phone = fields.Char(string=u'收货电话', readonly=True, index=True)

    delivery_ids = fields.One2many('purchase.order.delivery', 'purchase_id', string=u'发货情况', copy=False)
    delivery_status = fields.Selection(
        compute="_get_pogoodsstatus", 
        selection=[('no', u'未发货'), ('partial', u'部分发货'), ('yes', u'完全发货')], 
        string=u'发货状态', 
        store=True)
    supplier_contact = fields.Many2one('res.partner', string=u'供应商联系人', readonly=True, states={'draft': [('readonly', False)]})

    po_goods_in_status = fields.Selection(compute="_get_po_goods_in_status", selection=[('no', u'未入库'), ('partial', u'部分入库'), ('yes', u'全部入库')],
        string=u'入库状态', store=True, multi='in_goods')

    po_last_in_datetime = fields.Datetime(compute="_get_po_goods_in_status", string=u'最后入库时间', store=True, multi='in_goods')

    order_comment = fields.Char(string=u'下单备注', states={'draft': [('readonly', False)]}, readonly=True)

    confirm_date = fields.Datetime(u'确认时间', readonly=True)

    @api.multi
    def button_approve(self):
        res = super(PurchaseOrder, self).button_approve()
        self.write({'confirm_date': datetime.now()})
        return res

    @api.multi
    def get_sale_order(self):
        origin = (self.origin or '').split(', ')
        sale_id = self.env['sale.order'].search([('name', 'in', origin)])
        return sale_id

    @api.multi
    def get_sale_receiver_info(self):
        return {
            'name': self.partner_shipping_name or '', 
            'street': self.partner_shipping_address or '',
            'phone': self.partner_shipping_phone or '',
        }

    @api.multi
    def get_sale_contract(self):
        sale_id = self.get_sale_order()
        contract_num_list = sale_id.mapped('contract_num')
        contract_num_list = [i for i in contract_num_list if i]
        contract_num = ','.join(contract_num_list)
        return contract_num or self.origin

    @api.multi
    def action_delivery(self):
        if self.state != 'purchase':
            raise UserError(u'只有供应商已确认状态才能进行发货')

        delivery_lines = []
        for line in self.order_line.filtered(lambda s: s.product_id.type == 'product'):
            delivery_line_ids = line.mapped('delivery_lines')
            sent_qty = sum([delivery.send_quantity for delivery in delivery_line_ids]) if delivery_line_ids else 0
            if line.product_qty - sent_qty > 0:
                delivery_lines.append((0, 0, {
                        'purchase_line_id': line.id,
                        'product_id': line.product_id.id,
                        'line_qty': line.product_qty,
                        'sent_qty': sent_qty,
                        'qty': line.product_qty - sent_qty,
                    }))
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'purchase.order.delivery.wizard',
            'target': 'new',
            'context': {'default_purchase_id': self.id, 'default_delivery_lines': delivery_lines}
        }

    @api.multi
    def action_to_approve(self):
        self.filtered(lambda s: s.state == 'draft').write({'state': 'to approve'})
        return True

    @api.multi
    def action_reset_to_draft(self):
        self.filtered(lambda s: s.state == 'purchase').with_context(keep_procurement=True, cancel_procurement=True).button_cancel()
        self.write({'state': 'draft'})
        return True

    @api.multi
    def button_cancel(self):
        procurements = self.mapped('order_line.procurement_ids').filtered(lambda s: s.state in ('running', 'exception', 'confirmed'))
        res = super(PurchaseOrder, self).button_cancel()
        # procurements = self.mapped('order_line.procurement_ids')
        _logger.info(procurements)
        if not self.env.context.get('keep_procurement', False):
            procurements.write({'state': 'exception', 'purchase_line_id': False})
        return res

#----------------------------------------------------------
# Purchase Order Line
#----------------------------------------------------------
class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'
    _description = u'采购单明细'

    cat_no = fields.Char(related='product_id.cat_no', string=u'原厂货号', store=True, index=True)
    brand_id = fields.Many2one(related='product_id.brand_id', string=u'品牌', relation='product.brand', store=True, index=True)
    delivery_lines = fields.One2many('purchase.order.delivery.line', 'purchase_line_id', string=u'发货情况', copy=False)

    order_for = fields.Char(string=u'所属单号', default='', index=True, readonly=True)

    @api.multi
    def _prepare_stock_moves(self, picking):
        res = super(PurchaseOrderLine, self)._prepare_stock_moves(picking)
        for r in res:
            r.update({'order_for': self.order_for})
        return res

#----------------------------------------------------------
# Purchase Order Delivery
#----------------------------------------------------------
class PurchaseOrderDelivery(models.Model):
    _name = 'purchase.order.delivery'
    _description = u'采购单发货'

    @api.model
    def _get_send_time(self):
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return date

    name = fields.Char(string=u'快递单号')
    purchase_id = fields.Many2one('purchase.order', string=u'采购单', required=True, ondelete='cascade', index=True, copy=False)
    partner_id = fields.Many2one(relation='res.partner', string=u'供应商', related='purchase_id.partner_id', store=True)
    send_time = fields.Datetime(string=u'发货时间', required=True, default=_get_send_time)
    send_company = fields.Char(string=u'快递公司', required=True)
    note = fields.Char(u'备注', default='')
    delivery_lines = fields.One2many('purchase.order.delivery.line', 'delivery_id', string=u'发货明细', copy=False)


#----------------------------------------------------------
# Purchase Order Delivery Line
#----------------------------------------------------------
class PurchaseOrderDeliveryLine(models.Model):
    _name = 'purchase.order.delivery.line'
    _description = u'采购单发货明细'

    delivery_id = fields.Many2one('purchase.order.delivery', string=u'发货记录', required=True, ondelete='cascade', index=True, copy=False)
    send_quantity = fields.Float(string=u'发货数量', default=1)
    purchase_line_id = fields.Many2one('purchase.order.line', string=u'采购单明细', required=True, ondelete='cascade', index=True, copy=False)
    product_id = fields.Many2one('product.product', string=u'产品', required=True, ondelete='cascade', index=True)
    product_uom = fields.Many2one('product.uom', string=u'单位', required=True, ondelete='set null', index=True)

#----------------------------------------------------------
# Purchase Invoice
#----------------------------------------------------------
class PurchaseInvoice(models.Model):
    _name = 'purchase.invoice'
    _description = u'采购发票'

    purchase_ids = fields.Many2many('purchase.order', string=u'采购单', required=True)
    invoice_num = fields.Char(string=u'发票号码', index=True, required=True)
    invoice_code = fields.Char(string=u'发票代码', index=True)
    invoice_date = fields.Date(string=u'开票日期', index=True, required=True)
    price_total = fields.Float(string=u'含税金额', default=0)
    price_tax = fields.Float(string=u'税额', default=0)

