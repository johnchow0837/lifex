# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging, json

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Stock Picking Express
#----------------------------------------------------------
class StockPickingExpress(models.Model):
    _name = "stock.picking.express"
    _description = u"发货单物流信息"

    express_num = fields.Char(string=u'物流单号', required=True, index=True)
    express_carrier = fields.Char(string=u'物流公司', required=True, index=True)
    express_date = fields.Datetime(string=u'配送时间', required=True, index=True)
    express_note = fields.Char(string=u'物流备注', required=False, index=True)
    picking_id = fields.Many2one(comodel_name='stock.picking', required=True, index=True, ondelete='cascade', string=u'发货单')

#----------------------------------------------------------
# Stock Picking
#----------------------------------------------------------
class StockPicking(models.Model):
    _inherit = "stock.picking"

    @api.depends('group_id.name')
    def get_internal_comment(self):
        so_name = list(set(self.mapped('group_id.name')))
        sale_ids = self.env['sale.order'].search([('name', 'in', so_name)])
        for picking in self:
            picking.internal_comment = sale_ids.filtered(lambda s: s.name == picking.group_id.name).internal_comment

    express_ids = fields.One2many('stock.picking.express', 'picking_id', string=u'物流信息', readonly=False, states={'cancel': [('readonly', True)]})
    internal_comment = fields.Char(compute="get_internal_comment", string=u'内部备注', readonly=True, help=u'销售员内部备注。')

    @api.multi
    def do_transfer(self):
        todo_records = self.filtered(lambda s: s.state != 'done' and s.location_dest_id.usage == 'customer')
        self.filtered(lambda s: s.location_dest_id.usage == 'customer').check_logistics_data()
        res = super(StockPicking, self).do_transfer()
        done_records = todo_records.filtered(lambda s: s.state == 'done')
        done_records.sync_order_send()
        return res

    @api.multi
    def check_logistics_data(self):
        for picking in self:
            if not picking.express_ids:
                raise UserError(u'销售发货时，必须至少有一个物流单号！')
        return True

    @api.multi
    def sync_order_send(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for picking in self:
            data = {
                'package_id': picking.name,
                'sale_order_id': picking.origin,
                'send_time': picking.date_done,
            }

            product_list = picking.move_lines.prepare_product_list()
            logistics_list = []
            for line in picking.express_ids:
                logistics_list.append({
                        'send_no': line.express_num,
                        'send_company': line.express_carrier,
                    })

            data.update({'product_list': json.dumps(product_list), 'logistics_list': json.dumps(logistics_list)})

            api_val = {
                'api_type': 'order_send',
                'http_method': 'post',
                'data_model': 'stock.picking',
                'key_value': picking.id,
                'data': data,
                'url': '?route=rest/package/order/send',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

    @api.multi
    def _create_extra_moves(self):
        raise UserError(u'数据错误，请联系IT处理！(额外移动)')


#----------------------------------------------------------
# Stock Move
#----------------------------------------------------------
class StockMove(models.Model):
    _inherit = "stock.move"

    cat_no = fields.Char(related='product_id.cat_no', string=u'原厂货号', store=False)
    brand_id = fields.Many2one(related='product_id.brand_id', string=u'品牌', relation='product.brand', store=False)

    @api.multi
    def prepare_product_list(self):
        product_list = []
        product_ids = self.mapped('product_id')
        for product_id in product_ids:
            moves = self.filtered(lambda s: s.product_id == product_id)
            num = sum([move.product_uom_qty for move in moves])
            product_list.append({
                    'sku_code': product_id.default_code,
                    'num': num,
                })
        return product_list

#----------------------------------------------------------
# Stock Pack Operation
#----------------------------------------------------------
class StockPackOperation(models.Model):
    _inherit = "stock.pack.operation"

    cat_no = fields.Char(related='product_id.cat_no', string=u'原厂货号', store=False)
    brand_id = fields.Many2one(related='product_id.brand_id', string=u'品牌', relation='product.brand', store=False)

#----------------------------------------------------------
# Stock Warehouse
#----------------------------------------------------------

class StockWarehouse(models.Model):
    _inherit = "stock.warehouse"

    partner_address = fields.Char(related='partner_id.street', store=True, string=u'具体地址')

class StockQuant(models.Model):
    _inherit = 'stock.quant'

    @api.model
    def _quant_create_from_move(self, qty, move, lot_id=False, owner_id=False,
                                src_package_id=False, dest_package_id=False,
                                force_location_from=False, force_location_to=False):
        if move.location_id.usage == 'internal':
            raise UserError(u'数据错误，请联系IT处理！(创建负数份)')
        return super(StockQuant, self)._quant_create_from_move(
                qty, move, lot_id=lot_id, owner_id=owner_id,
                src_package_id=src_package_id, dest_package_id=dest_package_id,
                force_location_from=force_location_from, force_location_to=force_location_to
            )