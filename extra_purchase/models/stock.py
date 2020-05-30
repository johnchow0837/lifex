# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp
from odoo.tools.float_utils import float_round
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Procurement Rule
#----------------------------------------------------------
class ProcurementRule(models.Model):
    _inherit = "procurement.rule"
    _description = u"补货规则"

    auto_run = fields.Boolean(string=u'自动运行', default=True)

#----------------------------------------------------------
# Stock Move
#----------------------------------------------------------
class StockMove(models.Model):
    _inherit = "stock.move"
    _description = u"库存移动"

    order_for = fields.Char(string=u'所属单号', default='', index=True, readonly=True, states={'draft': [('readonly', False)]})

    def _prepare_procurement_from_move(self):
        res = super(StockMove, self)._prepare_procurement_from_move()
        res.update({'origin': self.group_id.name or self.origin or self.picking_id.name})
        return res

    @api.multi
    def action_cancel(self):
        moves = self.filtered(lambda s: s.procurement_id.sale_line_id.order_id.name)
        if moves:
            tocancel_pros = self.env['procurement.order']
            location_id = self.env.ref('extra_sale.stock_customer_transit_locations')
            customer_transit_moves = moves.filtered(lambda s: s.location_id == location_id)
            if customer_transit_moves:
                procuremnet_ids = self.env['procurement.order'].search([('move_dest_id', 'in', customer_transit_moves.ids), ('state', '=', 'exception'), 
                    ('location_id', 'child_of', location_id.id), ('purchase_line_id', '=', False)])
                tocancel_pros |= procuremnet_ids

            elsemoves = moves.filtered(lambda s: s.location_id != location_id)
            for move in elsemoves:
                procuremnet_ids = self.env['procurement.order'].search([('state', '=', 'exception'), ('origin', '=', move.order_for), ('product_id', '=', move.product_id.id),
                    ('location_id', 'child_of', move.location_id.id), ('purchase_line_id', '=', False)])
                tocancel_pros |= procuremnet_ids
            tocancel_pros.cancel()

        return super(StockMove, self).action_cancel()


#----------------------------------------------------------
# Stock Quant
#----------------------------------------------------------
class StockQuant(models.Model):
    _inherit = 'stock.quant'
    _description = u'份'

    order_for = fields.Char(string=u'所属单号', default='', index=True)

    # @api.model
    # def _quant_create_from_move(self, qty, move, lot_id=False, owner_id=False,
    #                             src_package_id=False, dest_package_id=False,
    #                             force_location_from=False, force_location_to=False):
    #     quant = super(StockQuant, self)._quant_create_from_move(qty, move, lot_id=lot_id, owner_id=owner_id, src_package_id=src_package_id,
    #         dest_package_id=dest_package_id, force_location_from=force_location_from, force_location_to=force_location_to)

    #     if move.order_for:
    #         quant.write({'order_for': move.order_for})

    #     return quant

    @api.model
    def _quant_create_from_move(self, qty, move, lot_id=False, owner_id=False,
                                src_package_id=False, dest_package_id=False,
                                force_location_from=False, force_location_to=False):
        '''Create a quant in the destination location and create a negative
        quant in the source location if it's an internal location. '''
        price_unit = move.get_price_unit()
        location = force_location_to or move.location_dest_id
        rounding = move.product_id.uom_id.rounding
        vals = {
            'product_id': move.product_id.id,
            'location_id': location.id,
            'qty': float_round(qty, precision_rounding=rounding),
            'cost': price_unit,
            'history_ids': [(4, move.id)],
            'in_date': datetime.now().strftime(DEFAULT_SERVER_DATETIME_FORMAT),
            'company_id': move.company_id.id,
            'lot_id': lot_id,
            'owner_id': owner_id,
            'package_id': dest_package_id,
            'order_for': move.order_for,
        }
        if move.location_id.usage == 'internal':
            # if we were trying to move something from an internal location and reach here (quant creation),
            # it means that a negative quant has to be created as well.
            # negative_vals = vals.copy()
            # negative_vals['location_id'] = force_location_from and force_location_from.id or move.location_id.id
            # negative_vals['qty'] = float_round(-qty, precision_rounding=rounding)
            # negative_vals['cost'] = price_unit
            # negative_vals['negative_move_id'] = move.id
            # negative_vals['package_id'] = src_package_id
            # negative_quant_id = self.sudo().create(negative_vals)
            # vals.update({'propagated_from_id': negative_quant_id.id})

            raise UserError(u'不能创建负数份！')

        picking_type = move.picking_id and move.picking_id.picking_type_id or False
        if lot_id and move.product_id.tracking == 'serial' and (not picking_type or (picking_type.use_create_lots or picking_type.use_existing_lots)):
            if qty != 1.0:
                raise UserError(_('You should only receive by the piece with the same serial number'))

        # create the quant as superuser, because we want to restrict the creation of quant manually: we should always use this method to create quants
        return self.sudo().create(vals)

    @api.model
    def quants_get_preferred_domain(self, qty, move, ops=False, lot_id=False, domain=None, preferred_domain_list=[]):
        if move.order_for:
            domain += [('order_for', '=', move.order_for)]
        else:
            domain += [('order_for', 'in', ('', False))]

        return super(StockQuant, self).quants_get_preferred_domain(qty, move, ops=ops, lot_id=lot_id, domain=domain, preferred_domain_list=preferred_domain_list)

    @api.model
    def allocate_so_quants(self, quant_ids, so_dict):
        if not quant_ids or not so_dict:
            return 0
        else:
            solved_qty = 0
            for so_info in so_dict:
                if not quant_ids:
                    break
                solved_quant_ids = self.browse()
                to_solve_qty = so_dict[so_info]

                result_quants = quant_ids
                for quant in quant_ids:
                    if to_solve_qty < 0.01:
                        break
                    if abs(quant.qty - to_solve_qty) < 0.01:
                        solved_quant_ids += quant
                        result_quants -= quant
                        to_solve_qty = 0
                        solved_qty += quant.qty
                        break
                    elif quant.qty - to_solve_qty > 0.01:
                        split_quant = quant._quant_split(to_solve_qty)
                        solved_quant_ids += quant
                        result_quants -= quant
                        result_quants += split_quant
                        solved_qty += to_solve_qty
                        to_solve_qty = 0
                        break
                    elif to_solve_qty - quant.qty > 0.01:
                        solved_quant_ids += quant
                        result_quants -= quant
                        solved_qty += quant.qty
                        to_solve_qty -= quant.qty
                        continue

                solved_quant_ids.write({'order_for': so_info})
                quant_ids = result_quants
            if not self._context.get('keep_order_for', False):
                quant_ids and quant_ids.write({'order_for': ''})
            return solved_qty



    