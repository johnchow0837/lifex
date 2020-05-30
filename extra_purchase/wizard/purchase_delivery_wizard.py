# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


#----------------------------------------------------------
# Purchase Order Delivery Wizard
#----------------------------------------------------------
class PurchaseOrderDeliveryWizard(models.TransientModel):
    _name = 'purchase.order.delivery.wizard'
    _description = u'采购单发货导航'

    @api.model
    def get_send_time(self):
        date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        return date

    send_method = fields.Selection(selection=[('self', u'自送'), ('express', u'快递')], string=u'配送方法', default='express')
    name = fields.Char(string=u'快递单号')
    send_company = fields.Char(string=u'快递公司')
    send_time = fields.Datetime(string=u'发货时间', required=True, default=get_send_time)
    note = fields.Char(string=u'备注')
    purchase_id = fields.Many2one('purchase.order', string=u'采购单')
    delivery_lines = fields.One2many('purchase.order.delivery.wizard.line', 'wizard_id', string=u'发货明细', copy=False)

    @api.multi
    def _validate_delivery_info(self):
        if self.purchase_id.state != 'purchase':
            raise UserError(u'只有供应商已确认状态的采购单才能发货')
        if not self.send_time:
            raise UserError(u'发货时间不能为空')
        if self.send_method != 'self':
            if not self.send_company or not self.name:
                raise UserError(u'配送方式为快递时,快递公司和快递单号都不能为空')
        return True

    @api.multi
    def action_confirm(self):
        self._validate_delivery_info()
        self.delivery_lines.check_qty()

        send_method = self.send_method

        name = self.name
        send_company = self.send_company
        if self.send_method == 'self':
            name = u'无'
            send_company = u'自送'

        delivery_val = {
            'purchase_id': self.purchase_id.id,
            'name': self.name if send_method != 'self' else u'自送',
            'send_time': self.send_time,
            'send_company': self.send_company if send_method != 'self' else u'自送',
            'note': self.note,
        }
        delivery_lines = []
        wizard_delivery_lines = self.delivery_lines.filtered(lambda s: s.qty > 0.01)
        if not wizard_delivery_lines:
            return True

        for line in wizard_delivery_lines:
            delivery_lines.append((0, 0, {
                    'product_id': line.product_id.id,
                    'send_quantity': line.qty,
                    'product_uom': line.purchase_line_id.product_uom.id,
                    'purchase_line_id': line.purchase_line_id.id,
                }))
        delivery_val.update({'delivery_lines': delivery_lines})
        self.env['purchase.order.delivery'].create(delivery_val)

        return True


#----------------------------------------------------------
# Purchase Order Delivery Wizard Line
#----------------------------------------------------------
class PurchaseOrderDeliveryWizardLine(models.TransientModel):
    _name = 'purchase.order.delivery.wizard.line'

    wizard_id = fields.Many2one('purchase.order.delivery.wizard', string=u'发货表头', ondelete='cascade', required=True)
    purchase_line_id = fields.Many2one('purchase.order.line', string=u'采购明细', required=True, ondelete='cascade')
    sent_qty = fields.Float(string=u'已发货数量', readonly=True, default=0)
    line_qty = fields.Float(string=u'采购数量', readonly=True, default=0)
    qty = fields.Float(string=u'要发货数量', required=True, default=0)
    product_id = fields.Many2one('product.product', string=u'产品', ondelete='cascade', required=True)

    @api.multi
    def check_qty(self):
        for line in self:
            sent_qty = 0
            for delivery in line.purchase_line_id.delivery_lines:
                sent_qty += delivery.send_quantity
            if line.qty < 0:
                raise UserError(u'发货数量不能为负数')
            if line.qty + sent_qty - line.purchase_line_id.product_qty > 0.01:
                raise UserError(u'发货数量不能大于未发货数量')
        return True