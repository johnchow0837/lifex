# -*- coding: utf-8 -*-

from odoo import api, fields, models, _, registry
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Procurement Order
#----------------------------------------------------------
class ProcurementOrder(models.Model):
    _inherit = "procurement.order"
    _description = u"补货单"

    @api.depends('origin')
    def _get_sale_id(self):
        sale_model = self.env['sale.order']
        for order in self:
            sale_id = sale_model.search([('name', '=', order.origin)], limit=1)
            order.sale_id = sale_id.id

    @api.depends(
        'sale_id', 
        'sale_id.address_info_name', 
        'sale_id.address_info_mobile', 
        'sale_id.address_info_telephone', 
        'sale_id.address_info_address',
        'sale_id.purchase_comment'
    )
    def _get_sale_receive_info(self):
        for order in self:
            if order.sale_id:
                sale_id = order.sale_id
                order.customer_partner_id = sale_id.partner_id.id
                order.partner_shipping_name = sale_id.address_info_name
                order.partner_shipping_address = sale_id.address_info_address
                order.partner_shipping_mobile = sale_id.address_info_mobile
                order.partner_shipping_phone = sale_id.address_info_telephone
                order.purchase_comment = sale_id.purchase_comment
            else:
                order.customer_partner_id = order.warehouse_id.partner_id.id
                order.partner_shipping_name = order.warehouse_id.partner_id.name
                order.partner_shipping_mobile = order.warehouse_id.partner_id.mobile
                order.partner_shipping_phone = order.warehouse_id.partner_id.phone
                order.partner_shipping_address = order.warehouse_id.partner_id.street

    supplier_partner_id = fields.Many2one('res.partner', string=u'供应商', index=True)
    sale_id = fields.Many2one(comodel_name='sale.order', compute="_get_sale_id", store=True, readonly=True, string=u'销售单', index=True)
    customer_partner_id = fields.Many2one(comodel_name='res.partner', compute="_get_sale_receive_info", string=u'客户名称', store=True, readonly=True, index=True)
    # partner_shipping_id = fields.Many2one(comodel_name='res.partner', compute="_get_sale_info", string=u'客户收货人', store=True, readonly=True, index=True)
    partner_shipping_name = fields.Char(compute="_get_sale_receive_info", string=u'收货人', store=True, readonly=True, index=True)
    partner_shipping_address = fields.Char(compute="_get_sale_receive_info", string=u'收货地址', store=True, readonly=True, index=True)
    partner_shipping_mobile = fields.Char(compute="_get_sale_receive_info", string=u'收货手机', store=True, readonly=True, index=True)
    partner_shipping_phone = fields.Char(compute="_get_sale_receive_info", string=u'收货电话', store=True, readonly=True, index=True)
    purchase_comment = fields.Char(compute="_get_sale_receive_info", string=u'采购备注', store=True, readonly=True, index=True)


    purchase_currency = fields.Many2one(comodel_name='res.currency', string=u'采购币种', readonly=True, index=True)
    purchase_price = fields.Float(string=u'采购价格', required=True, default=0)
    supplier_delay = fields.Float(string=u'供应商货期', required=True, default=0)
    brand_id = fields.Many2one(related='product_id.brand_id', string=u'品牌', relation='product.brand', store=True, index=True)
    cat_no = fields.Char(related='product_id.cat_no', string=u'原厂货号', store=True, index=True)

    # @api.model
    # def _run_move_create(self, procurement):
    #     vals = super(ProcurementOrder, self)._run_move_create(procurement)
    #     if procurement.group_id:
    #         procu_has_sale_line = self.search(
    #             [('group_id', '=', procurement.group_id.id), ('sale_line_id', '!=', False)])
    #         if procu_has_sale_line:
    #             order_for = procu_has_sale_line[0].sale_line_id.order_id.name
    #             vals.update({'order_for': order_for})

    #     return vals

    @api.model
    def run_scheduler(self, use_new_cursor=False, company_id=False):
        ''' Call the scheduler in order to check the running procurements (super method), to check the minimum stock rules
        and the availability of moves. This function is intended to be run for all the companies at the same time, so
        we run functions as SUPERUSER to avoid intercompanies and access rights issues. '''
        super(ProcurementOrder, self).run_scheduler(use_new_cursor=use_new_cursor, company_id=company_id)
        try:
            if use_new_cursor:
                cr = registry(self._cr.dbname).cursor()
                self = self.with_env(self.env(cr=cr))  # TDE FIXME

            # Minimum stock rules
            self.sudo()._procure_orderpoint_confirm(use_new_cursor=use_new_cursor, company_id=company_id)

            # Search all confirmed stock_moves and try to assign them
            # confirmed_moves = self.env['stock.move'].search([('state', '=', 'confirmed'), ('product_uom_qty', '!=', 0.0)], limit=None, order='priority desc, date_expected asc')
            self.env.cr.execute("""select sm.id from stock_move sm 
                            join stock_location sl2
                            on sl2.id = sm.location_id and sm.product_uom_qty > 0 and sm.state = 'confirmed' and sm.order_for like 'SO%'
                            join (select b.product_id as product_id, b.order_for, sl1.parent_left as parent_left, sl1.parent_right as parent_right from (select sq.product_id as product_id, sq.order_for, sq.location_id as location_id
                            from stock_quant sq 
                            join stock_location sl 
                            on sq.reservation_id is null and sl.usage = 'internal' and sq.qty > 0 and sq.location_id = sl.id and sq.order_for like 'SO%'
                            group by sq.product_id, sq.location_id, sq.order_for) b join stock_location sl1 on sl1.id = b.location_id) a
                            on a.product_id = sm.product_id and a.parent_left >= sl2.parent_left and a.parent_right <= sl2.parent_right and sm.state = 'confirmed'
                            and a.order_for = sm.order_for
                            group by sm.id""")
            res = self.env.cr.fetchall()
            _logger.info('need to assigned move : %s'%res)
            confirmed_ids = []
            if res:
                for re in res:
                    confirmed_ids.append(re[0])


            for x in xrange(0, len(confirmed_ids), 100):
                # TDE CLEANME: muf muf
                self.env['stock.move'].browse(confirmed_ids[x:x + 100]).action_assign()
                if use_new_cursor:
                    self._cr.commit()
            if use_new_cursor:
                self._cr.commit()
        finally:
            if use_new_cursor:
                try:
                    self._cr.close()
                except Exception:
                    pass
        return {}

    def _get_stock_move_values(self):
        vals = super(ProcurementOrder, self)._get_stock_move_values()
        group_order_map_dict = {}
        if self.group_id:
            if self.group_id in group_order_map_dict:
                vals.update({'order_for': group_order_map_dict[self.group_id]})
            else:
                procu_has_sale_line = self.search(
                [('group_id', '=', self.group_id.id), ('sale_line_id', '!=', False)], limit=1)
                if procu_has_sale_line:
                    order_for = procu_has_sale_line.sale_line_id.order_id.name
                    vals.update({'order_for': order_for})
                    group_order_map_dict.update({self.group_id: order_for})
        return vals

    @api.model
    def create(self, val):
        _logger.info(self.env.context)
        if self.env.context.get('import_procurement', False):
            if val.get('warehouse_id', False):
                warehouse_id = self.env['stock.warehouse'].browse(val.get('warehouse_id', False))
                val.update({'location_id': warehouse_id.lot_stock_id.id})

                buy_route_ids = self.env.ref('purchase.route_warehouse0_buy')
                buy_rule_id = buy_route_ids.pull_ids.filtered(lambda s: s.warehouse_id.id == warehouse_id.id and s.location_id.id == warehouse_id.lot_stock_id.id)
                if not buy_rule_id:
                    raise UserError(u'找不到对应补货规则')

                val.update({'route_ids': [(4, buy_route_ids.ids)]})
        return super(ProcurementOrder, self).create(val)

    # @api.model
    # def _prepare_compute_purchase_sql(self):
    #     sql = """select * from (select out_table.product_id, out_table.out_qty - coalesce(pro_table.pro_qty, 0) - coalesce(quant_table.quant_qty, 0) as create_qty
    #         from
    #         (select sm.product_id, sum(sm.product_uom_qty) as out_qty from stock_move sm join stock_location sl
    #         on sl.id = sm.location_dest_id and sl.usage = 'customer'
    #         and sm.state = 'confirmed'
    #         join stock_location sl1 on sl1.id = sm.location_id
    #         and sl1.parent_left >= {parent_left} and sl1.parent_right <= {parent_right}
    #         group by sm.product_id) out_table
    #         left join
    #         (select po.product_id, sum(po.product_qty - coalesce(sm1.product_uom_qty, 0)) as pro_qty from procurement_order po
    #         join stock_location sl3 on sl3.parent_left >= {parent_left} and sl3.parent_right <= {parent_right}
    #         and sl3.id = po.location_id and po.state != 'cancel'
    #         left join stock_move sm1 on sm1.procurement_id = po.id and sm1.state = 'done'
    #         group by po.product_id
    #         ) pro_table
    #         on pro_table.product_id = out_table.product_id
    #         left join
    #         (select sq.product_id, sum(qty) as quant_qty from stock_quant sq join stock_location sl2 on sl2.id = sq.location_id
    #         and sq.reservation_id is null and sl2.parent_left >= {parent_left} and sl2.parent_right <= {parent_right}
    #         group by sq.product_id
    #         ) quant_table
    #         on quant_table.product_id = out_table.product_id) a where a.create_qty > 0"""
    #     return sql

    @api.model
    def _prepare_compute_purchase_sql(self):
        sql = """select * from
            (select move_table.product_id as product_id,
            move_table.product_uom_qty as out_qty,
            move_table.so_name as so_name,
            move_table.date_expected as date_expected,
            coalesce(quants_table.qty, 0) as quant_qty,
            coalesce(procurements_table.product_qty, 0) as procurement_qty
            from

            (select sm.product_id, sm.order_for as so_name, sum(sm.product_uom_qty) as product_uom_qty,
            min(sm.date_expected) as date_expected
            from stock_move sm join stock_location sl
            on sl.id = sm.location_id
            and sm.state not in ('cancel', 'waiting', 'done')
            and sm.order_for like 'SO%%' 
            and sl.parent_left >= {parent_left} and sl.parent_right <= {parent_right}
            join stock_location sldest on sldest.id = sm.location_dest_id
            and (sldest.parent_right < {parent_left} or sldest.parent_left > {parent_right})
            and sldest.usage = 'customer'
            group by sm.product_id, sm.order_for) move_table

            left join (
            select quants.product_id as product_id, sum(quants.qty) as qty,
            quants.order_for as so_name
            from stock_quant quants join stock_location quant_locations
            on quant_locations.id = quants.location_id and quants.qty > 0
            and quant_locations.parent_left >= {parent_left} and quant_locations.parent_right <= {parent_right}
            group by quants.product_id, quants.order_for
            ) quants_table
            on quants_table.product_id = move_table.product_id and move_table.so_name = quants_table.so_name


            left join (
            select z.so_name as so_name, z.product_id, sum(z.product_qty) as product_qty from
            (select
            procurements.product_id as product_id,
            procurements.origin as so_name,
            procurements.product_qty - sum(COALESCE(sm.product_uom_qty, 0)) as product_qty
            from procurement_order procurements
            join stock_location procurement_locations
            on procurements.location_id = procurement_locations.id and procurements.state != 'cancel'
            and procurement_locations.parent_left >= {parent_left} and procurement_locations.parent_right <= {parent_right}
            and procurements.origin like 'SO%%'
            left join stock_move sm
            on sm.procurement_id = procurements.id and sm.state = 'done'
            group by procurements.id) z
            where z.product_qty > 0
            group by z.so_name, z.product_id
            )
            procurements_table
            on procurements_table.product_id = move_table.product_id and procurements_table.so_name = move_table.so_name)
            product_inventory where product_inventory.out_qty > product_inventory.quant_qty + product_inventory.procurement_qty
            order by product_inventory.date_expected
            """
        return sql

    @api.model
    def compute_purchase_procurements(self):
        warehouse_ids = self.env['stock.warehouse'].search([])
        quant_model = self.env['stock.quant']
        for warehouse_id in warehouse_ids:
            location = warehouse_id.lot_stock_id
            sql = self._prepare_compute_purchase_sql()
            sql = sql.format(parent_left=location.parent_left, parent_right=location.parent_right)
            _logger.info(sql)
            self.env.cr.execute(sql)
            res = self.env.cr.dictfetchall()
            for re in res:
                try:
                    self.env.cr.execute('''select id from sale_order_line where product_id = %s
                        and order_id = (select id from sale_order where name = %s) for update nowait''', (re['product_id'], re['so_name'], ))
                    exist_qty = re['procurement_qty'] + re['quant_qty']

                    create_qty = re['out_qty'] - exist_qty

                    if create_qty > 0:
                        quant_ids = quant_model.search([('location_id.parent_left', '>=', location.parent_left),
                                ('location_id.parent_right', '<=', location.parent_right), ('product_id', '=', re['product_id']),
                                ('qty', '>', 0), ('company_id', '=', location.company_id.id), ('order_for', 'in', (False, '')),
                                ('reservation_id', '=', False)], order="in_date,id")

                        solved_qty = quant_model.allocate_so_quants(quant_ids, {re['so_name']: create_qty})
                        create_qty -= solved_qty

                    if create_qty > 0:
                        val = self._prepare_purchase_procurement_val(re['product_id'], create_qty, warehouse_id, re['date_expected'], re['so_name'])
                        procurement_id = self.create(val)
                        procurement_id.set_sup_info()

                except Exception, e:
                    _logger.info(e)
                    self.env.cr.rollback()
                self.env.cr.commit()
        return True

    @api.model
    def _prepare_purchase_procurement_val(self, product_id, qty, warehouse_id, date_expected, so_name):
        product_id = self.env['product.product'].browse(product_id)
        buy_route_ids = self.env['ir.model.data'].xmlid_to_object('purchase.route_warehouse0_buy')
        buy_rule_id = buy_route_ids.pull_ids.filtered(lambda s: s.warehouse_id.id == warehouse_id.id and s.location_id.id == warehouse_id.lot_stock_id.id)
        if not buy_rule_id:
            raise UserError(u'找不到对应补货规则')
        val = {
            'product_id': product_id.id,
            'product_qty': qty,
            'location_id': warehouse_id.lot_stock_id.id,
            'warehouse_id': warehouse_id.id,
            'product_uom': product_id.uom_id.id,
            'origin': so_name,
            'name': product_id.name + ':compute_procurements',
            'date_planned': datetime.now(),
            'supplier_partner_id': product_id.seller_ids and product_id.seller_ids[0].name.id or False,
            'state': 'exception',
            'rule_id': buy_rule_id and buy_rule_id[0].id or False,
            'route_ids':[(4, buy_route_ids.ids)],
        }
        return val

    @api.multi
    def _run(self):
        self.ensure_one()
        if self.rule_id.auto_run and self.rule_id.action != 'buy':
            return super(ProcurementOrder, self)._run()

    @api.multi
    def set_sup_info(self):
        for p in self:
            sup_info = p.product_id.seller_ids.filtered(lambda s: s.name.id == p.supplier_partner_id.id)
            if not self.env.context.get('manu_set', False):
                p.supplier_delay = sup_info and sup_info[0].delay or 0

            p.date_planned = datetime.now() + timedelta(days=p.supplier_delay)

            if sup_info and p.purchase_currency:
                if p.purchase_currency.name == 'CNY':
                    p.purchase_price = sup_info[0].price
                elif sup_info[0].currency_id.id == p.purchase_currency.id:
                    p.purchase_price = sup_info[0].for_price
                else:
                    p.purchase_price = 0
            else:
                p.purchase_price = 0

    @api.multi
    def run(self, autocommit=False):
        location = self.env['ir.model.data'].xmlid_to_object('extra_sale.stock_customer_transit_locations')
        for p in self:
            if p.move_dest_id and p.location_id.id == location.id:
                p.supplier_partner_id = p.move_dest_id.procurement_id.sale_line_id.quotation_id.vendor_id.id
                p.purchase_currency = p.sale_id.required_currency.id
                p.set_sup_info()
        return super(ProcurementOrder, self).run(autocommit=autocommit)

    @api.model
    def fields_view_get(self, view_id=None, view_type='tree', toolbar=False, submenu=False):
        res = super(ProcurementOrder, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree':
            remove_menu_name = []
            if self._context.get('no_run'):
                remove_menu_name.append('procurement.procurement_order_server_action')

            if not self._context.get('show_cancel', False):
                remove_menu_name.append('extra_purchase.cancel_procurements_server_action')

            if not self._context.get('customer_procurement', False):
                remove_menu_name.append('extra_purchase.action_procurement_dtot_server_action')

            if not self._context.get('transfer_procurement', False):
                remove_menu_name.append('extra_purchase.action_procurement_ttod_server_action')

            if remove_menu_name:
                try:
                    result_action_list = []
                    # _logger.info(res['toolbar']['action'])
                    for action in res['toolbar']['action']:
                        if action['xml_id'] not in remove_menu_name:
                            result_action_list.append(action)
                    res['toolbar']['action'] = result_action_list
                except Exception, e:
                    _logger.info(e)

        return res

    @api.multi
    def procurement_split(self, split_qty):
        self.ensure_one()
        if split_qty < 1 or self.product_qty < split_qty:
            return self.browse()

        else:
            if self.purchase_line_id or self.state != 'exception':
                return self.browse()
            split_procurement = self.with_context(procurement_autorun_defer=True).copy({'product_qty': split_qty, 
                'purchase_line_id': False, 'state': 'exception', 'move_dest_id': self.move_dest_id.id})

            _logger.info(split_procurement)
            self.write({'product_qty': self.product_qty - split_qty})

            return split_procurement

    @api.multi
    def action_dtot_transfer(self, warehouse_id):
        so_info = self.get_procurement_sale_data()
        self.check_procurement_sale_data(so_info=so_info)
        sale_lines = self.env['sale.order.line'].browse()
        moves = self.env['stock.move'].browse()
        for so, product_info in so_info.items():
            for p, qty_info in product_info.items():
                sale_lines |= qty_info['sale_lines']
                moves |= qty_info['moves']
        moves.action_cancel()
        sale_lines.mapped('procurement_ids').write({'sale_line_id': False})
        sale_lines.write({'warehouse_id': warehouse_id.id, 'route_id': False})
        sale_lines._action_procurement_create()
        return True

    @api.multi
    def action_ttod_transfer(self):
        customer_route = self.env.ref('extra_sale.stock_customer_transit_route')
        so_info = self.get_procurement_sale_data()
        self.check_procurement_sale_data(so_info=so_info)
        sale_lines = self.env['sale.order.line'].browse()
        moves = self.env['stock.move'].browse()
        for so, product_info in so_info.items():
            for p, qty_info in product_info.items():
                sale_lines |= qty_info['sale_lines']
                moves |= qty_info['moves']
        moves.action_cancel()
        sale_lines.mapped('procurement_ids').write({'sale_line_id': False})
        sale_lines.write({'warehouse_id': False, 'route_id': customer_route.id})
        sale_lines._action_procurement_create()
        return True

    @api.multi
    def check_procurement_sale_data(self, so_info={}):
        # 直发转非直发或非直发转直发时，勾选需求必须和销售单数量一致，且不能发货
        if not so_info:
            so_info = self.get_procurement_sale_data()
        for so, product_info in so_info.items():
            for p, qty_info in product_info.items():
                procurement_qty = qty_info['procurement_qty']
                move_qty = qty_info['move_qty']
                sale_qty = qty_info['sale_qty']
                sale_lines = qty_info['sale_lines']
                if sale_lines.filtered(lambda s: s.state != 'sale'):
                    raise UserError(u'SO:%s-SKU:%s必须处于“销售订单”状态才能转换！'%(so, p.default_code, ))
                if sale_qty != procurement_qty:
                    raise UserError(u'SO:%s-SKU:%s勾选数量:%s必须等于销售单明细行数量%s'%(so, p.default_code, procurement_qty, sale_qty, ))
                if sale_qty != move_qty:
                    raise UserError(u'SO:%s-SKU:%s未发货数量:%s必须等于销售单明细行数量%s'%(so, p.default_code, move_qty, sale_qty, ))
        return True

    @api.multi
    def get_procurement_sale_data(self):
        so_info = {}
        so_list = list(set(self.mapped('origin')))
        for so in so_list:
            procurements = self.filtered(lambda s: s.origin == so)
            product_ids = procurements.mapped('product_id')
            so_info.update({so: {}})
            for product_id in product_ids:
                prodprocurements = procurements.filtered(lambda s: s.product_id.id == product_id.id)
                procurement_qty = sum([prodprocurement.product_qty for prodprocurement in prodprocurements])
                moves = self.env['stock.move'].search([('order_for', '=', so), 
                    ('location_dest_id.usage', '=', 'customer'),
                    ('product_id', '=', product_id.id),
                    ('state', 'not in', ('cancel', 'done'))])
                move_qty = sum([move.product_uom_qty for move in moves])
                sale_lines = moves.mapped('procurement_id.sale_line_id')
                sale_qty = sum([sale_line.product_uom_qty for sale_line in sale_lines])
                so_info[so].update({product_id: {'procurement_qty': procurement_qty, 'move_qty': move_qty, 
                    'sale_qty': sale_qty, 'prodprocurements': prodprocurements, 'moves': moves, 'sale_lines': sale_lines}})
        return so_info

    @api.multi
    def action_procurement_dtot_server_action(self):
        # 直发转非直发
        ctx = self.env.context.copy()
        location_id = self.env.ref('extra_sale.stock_customer_transit_locations')
        if self.filtered(lambda s: s.location_id.id != location_id.id):
            raise UserError(u'直发转非直发时，只能全部选择直发需求!')
        if self.filtered(lambda s: s.state != 'exception' or s.purchase_line_id):
            raise UserError(u'直发转非直发时，状态必须为“异常”!')

        so_info = self.get_procurement_sale_data()

        self.check_procurement_sale_data(so_info=so_info)

        tips = []
        for so, product_info in so_info.items():
            for p, qty_info in product_info.items():
                tips.append(u'销售单:%s, SKU:%s, 数量:%s'%(so, p.default_code, qty_info['procurement_qty'], ))
        tips = '\n'.join(tips)
        ctx.update({'default_tips': tips})

        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'procurement.dtot.wizard',
            'context': ctx,
        }

    @api.multi
    def action_procurement_ttod_server_action(self):
        # 非直发转直发
        ctx = self.env.context.copy()

        if self.filtered(lambda s: s.location_id.parent_left > s.warehouse_id.lot_stock_id.parent_left 
            or s.location_id.parent_right < s.warehouse_id.lot_stock_id.parent_left):
            raise UserError(u'非直发转直发时，只能全部选择非直发需求!')
        if self.filtered(lambda s: s.state != 'exception' or s.purchase_line_id):
            raise UserError(u'非直发转直发时，状态必须为“异常”!')

        so_info = self.get_procurement_sale_data()

        self.check_procurement_sale_data(so_info=so_info)

        tips = []
        for so, product_info in so_info.items():
            for p, qty_info in product_info.items():
                tips.append(u'销售单:%s, SKU:%s, 数量:%s'%(so, p.default_code, qty_info['procurement_qty'], ))
        tips = '\n'.join(tips)
        ctx.update({'default_tips': tips})

        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'procurement.ttod.wizard',
            'context': ctx,
        }

    @api.multi
    def action_procurement_split_server_action(self):

        if len(self) != 1:
            raise UserError(u'只能同时对一个需求进行拆分!')

        if not self.product_qty > 1:
            raise UserError(u'所选择的需求对应的数量必须大于1！')

        if self.purchase_line_id or self.state != 'exception':
            raise UserError(u'只能拆分未确认的需求！')

        ctx = self.env.context.copy()
        ctx.update({'default_procurement_id': self.id})

        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'procurement.split.wizard',
            'context': ctx,
        }

    @api.multi
    def set_supplier_partner_server_action(self):

        partner_ids = self.mapped('product_id.seller_ids.name')
        if not partner_ids:
            raise UserError(u'勾选需求未配置供应商')

        product_ids = self.mapped('product_id')

        all_partner = self.env['res.partner'].browse()
        for partner_id in partner_ids:
            if all(partner_id in product_id.mapped('seller_ids.name') for product_id in product_ids):
                all_partner |= partner_id

        if not all_partner:
            raise UserError(u'勾选需求没有公共供应商')

        ctx = self.env.context.copy()
        ctx.update({'supplier_partner_id': all_partner.ids})

        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'procurement.set.partner.wizard',
            'context': ctx,
        }

    @api.multi
    def _prepare_purchase_order(self, partner):
        res = super(ProcurementOrder, self)._prepare_purchase_order(partner)
        customer_locations = self.env.ref('extra_sale.stock_customer_transit_locations')
        res.update({'partner_shipping_name': self.partner_shipping_name,
            'partner_shipping_mobile': self.partner_shipping_mobile, 'partner_shipping_phone': self.partner_shipping_phone, 'partner_shipping_address': self.partner_shipping_address, 
            'supplier_contact': partner.child_ids.filtered(lambda s: s.type == 'contact') and partner.child_ids.filtered(lambda s: s.type == 'contact')[0].id or False})

        if self.location_id.id == customer_locations.id:
            res.update({'shipment_method': 'customer'})
        else:
            warehouse_id = self.env['stock.warehouse'].search([('lot_stock_id', '=', self.location_id.id)], limit=1)
            if warehouse_id and self.origin == 'stocking':
                res.update({'shipment_method': 'stocking', 
                    'partner_shipping_name': self.warehouse_id.partner_id.name,
                    'partner_shipping_mobile': self.warehouse_id.partner_id.mobile, 
                    'partner_shipping_phone': self.warehouse_id.partner_id.phone, 
                    'partner_shipping_address': self.warehouse_id.partner_id.street})
            elif warehouse_id and 'SO' in self.origin:
                res.update({'shipment_method': 'warehouse',
                    'partner_shipping_name': self.warehouse_id.partner_id.name,
                    'partner_shipping_mobile': self.warehouse_id.partner_id.mobile, 
                    'partner_shipping_phone': self.warehouse_id.partner_id.phone, 
                    'partner_shipping_address': self.warehouse_id.partner_id.street})
            else:
                res.update({'shipment_method': 'other',
                    'partner_shipping_name': self.warehouse_id.partner_id.name,
                    'partner_shipping_mobile': self.warehouse_id.partner_id.mobile, 
                    'partner_shipping_phone': self.warehouse_id.partner_id.phone, 
                    'partner_shipping_address': self.warehouse_id.partner_id.street})
        return res

    @api.multi
    def make_po_new(self):
        res = []
        po_model = self.env['purchase.order']
        po = po_model.browse()
        for procurement in self:

            partner = procurement.supplier_partner_id
            suppliers = procurement.product_id.seller_ids.filtered(lambda s: s.name == partner)
            supplier = suppliers and suppliers[0] or False

            if not supplier:
                raise UserError("产品[%s]未配置供应商"%procurement.product_id.default_code)

            if not po:
                vals = procurement._prepare_purchase_order(partner)
                po = po_model.create(vals)
                name = (procurement.group_id and (procurement.group_id.name + ":") or "") + (procurement.name != "/" and procurement.name or procurement.move_dest_id.raw_material_production_id 
                    and procurement.move_dest_id.raw_material_production_id.name or "")
                message = _("This purchase order has been created from: <a href=# data-oe-model=procurement.order data-oe-id=%d>%s</a>") % (procurement.id, name)
                po.message_post(body=message)
            elif not po.origin or procurement.origin not in po.origin.split(', '):
                # Keep track of all procurements
                if po.origin:
                    if procurement.origin:
                        po.write({'origin': po.origin + ', ' + procurement.origin})
                    else:
                        po.write({'origin': po.origin})
                else:
                    po.write({'origin': procurement.origin})
                name = (procurement.group_id and (procurement.group_id.name + ":") or "") + (procurement.name != "/" 
                    and procurement.name or procurement.move_dest_id.raw_material_production_id and procurement.move_dest_id.raw_material_production_id.name or "")
                message = _("This purchase order has been modified from: <a href=# data-oe-model=procurement.order data-oe-id=%d>%s</a>") % (procurement.id, name)
                po.message_post(body=message)
            if po:
                res += [procurement.id]

            # Create Line
            po_line = False
            for line in po.order_line:

                if line.product_id == procurement.product_id and line.product_uom == procurement.product_id.uom_po_id:
                    if ('SO' not in procurement.origin and not line.order_for) or ('SO' in procurement.origin and procurement.origin == line.order_for):
                        procurement_uom_po_qty = procurement.product_uom._compute_quantity(procurement.product_qty, procurement.product_id.uom_po_id)
                        seller = procurement.product_id._select_seller(
                            partner_id=partner,
                            quantity=line.product_qty + procurement_uom_po_qty,
                            date=po.date_order and po.date_order[:10],
                            uom_id=procurement.product_id.uom_po_id)

                        price_unit = self.env['account.tax']._fix_tax_included_price_company(seller.price, line.product_id.supplier_taxes_id, line.taxes_id, procurement.company_id) if seller else 0.0
                        if price_unit and seller and po.currency_id and seller.currency_id != po.currency_id:
                            price_unit = seller.currency_id.compute(price_unit, po.currency_id)

                        po_line = line.write({
                            'product_qty': line.product_qty + procurement_uom_po_qty,
                            'price_unit': price_unit,
                            'procurement_ids': [(4, procurement.id)]
                        })
                        break
            if not po_line:
                vals = procurement._prepare_purchase_order_line(po, supplier)
                self.env['purchase.order.line'].create(vals)
        return res

    @api.multi
    def _prepare_purchase_order_line(self, po, supplier):
        res = super(ProcurementOrder, self)._prepare_purchase_order_line(po, supplier)
        if 'SO' in self.origin:
            res.update({'order_for': self.origin})
        return res

    @api.multi
    def cancel_procurements_server_action(self):
        ctx = self.env.context
        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'procurement.cancel.wizard',
            'context': ctx,
        }

    @api.multi
    def make_po_wizard_server_action(self):

        partner_ids = self.mapped('supplier_partner_id')
        if not partner_ids:
            raise UserError(u'勾选需求未配置供应商')

        try:
            partner_ids.ensure_one()
        except Exception, e:
            raise UserError(u'只能同时对一个供应商创建采购单')

        location_ids = self.mapped('location_id')

        try:
            location_ids.ensure_one()
        except Exception, e:
            raise UserError(u'只能同时对一个仓库创建采购单')

        partner_shipping_name = self.mapped('partner_shipping_name')
        partner_shipping_name = set([r for r in partner_shipping_name])

        partner_shipping_phone = self.mapped('partner_shipping_phone')
        partner_shipping_phone = set([r for r in partner_shipping_phone])

        partner_shipping_address = self.mapped('partner_shipping_address')
        partner_shipping_address = set([r for r in partner_shipping_address])

        partner_shipping_mobile = self.mapped('partner_shipping_mobile')
        partner_shipping_mobile = set([r for r in partner_shipping_mobile])

        if len(partner_shipping_name) != 1 or len(partner_shipping_phone) != 1 or len(partner_shipping_address) != 1 or len(partner_shipping_mobile) != 1:
            raise UserError(u'只能同时对一个配送地址创建采购单')

        # if partner_shipping_id:
        #     try:
        #         partner_shipping_id.ensure_one()
        #     except Exception, e:
        #         raise UserError(u'只能同时对一个配送地址创建采购单')
        #     if self.filtered(lambda s: not s.partner_shipping_id):
        #         raise UserError(u'只能同时对一个配送地址创建采购单')

        records = self.filtered(lambda s: s.state != 'exception' or s.purchase_line_id)
        if records:
            raise UserError(u'已经创建过采购单')

        ctx = self.env.context.copy()

        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'procurement.make.po.wizard',
            'context': ctx,
        }