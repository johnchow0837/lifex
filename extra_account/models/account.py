# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging, json

_logger = logging.getLogger(__name__)

class ResCompany(models.Model):
    _inherit = 'res.company'

    company_receivable_acc_id = fields.Many2one('account.account', u'应收科目')
    company_payable_acc_id = fields.Many2one('account.account', u'应付科目')
    company_prepay_acc_id = fields.Many2one('account.account', u'预付科目')
    company_prereceive_acc_id = fields.Many2one('account.account', u'预收科目')

class AccountTax(models.Model):
    _inherit = 'account.tax'

    invoice_account_id = fields.Many2one('account.account', u'开票的税科目')

class StockMove(models.Model):
    _inherit = 'stock.move'

    def _prepare_account_move_line(self, qty, cost, credit_account_id, debit_account_id):
        res = []
        if self.location_dest_id.usage == 'customer' and self.procurement_id.sale_line_id.order_id:
            if not self.company_id.company_receivable_acc_id:
                raise UserError(u'请先配置公司应收科目!')
            res = super(StockMove, self)._prepare_account_move_line(qty, cost, credit_account_id, debit_account_id)
            receivable_amount = 0
            line_taxes = self.procurement_id.sale_line_id.tax_id.compute_all(
                self.procurement_id.sale_line_id.price_unit,
                self.procurement_id.sale_line_id.order_id.currency_id,
                qty, self.procurement_id.sale_line_id.product_id, self.procurement_id.sale_line_id.order_id.partner_id
            )
            taxes = line_taxes['taxes']
            price_subtotal = line_taxes['total_excluded']
            for tax in taxes:
                res.append((0, 0, {
                    'name': self.procurement_id.sale_line_id.order_id.name + ':' + tax['name'],
                    'quantity': 1,
                    'ref': self.picking_id.origin + ":" + self.picking_id.name if self.picking_id.origin else self.picking_id.name,
                    'partner_id': self.procurement_id.sale_line_id.order_id.partner_id.id,
                    'debit': 0,
                    'credit': tax['amount'],
                    'account_id': tax['account_id'],
                }))
                receivable_amount += tax['amount']
            accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
            res.append((0, 0, {
                'name': self.product_id.display_name,
                'product_id': self.product_id.id,
                'quantity': self.product_uom_qty,
                'product_uom_id': self.product_id.uom_id.id,
                'ref': self.picking_id.origin + ":" + self.picking_id.name if self.picking_id.origin else self.picking_id.name,
                'partner_id': self.procurement_id.sale_line_id.order_id.partner_id.id,
                'debit': 0,
                'credit': price_subtotal,
                'account_id': accounts_data['income'].id,
            }))
            receivable_amount += price_subtotal
            res.append((0, 0, {
                'name': self.procurement_id.sale_line_id.order_id.name + ':' + str(receivable_amount),
                'product_id': self.product_id.id,
                'quantity': qty,
                'product_uom_id': self.product_id.uom_id.id,
                'ref': self.picking_id.origin + ":" + self.picking_id.name if self.picking_id.origin else self.picking_id.name,
                'partner_id': self.procurement_id.sale_line_id.order_id.partner_id.id,
                'debit': receivable_amount,
                'credit': 0,
                # 'account_id': self.procurement_id.sale_line_id.order_id.partner_id.property_account_receivable_id.id,
                'account_id': self.company_id.company_receivable_acc_id.id
            }))
        elif self.location_id.usage == 'supplier' and self.procurement_id.purchase_line_id.order_id:
            if not self.company_id.company_payable_acc_id:
                raise UserError(u'请先配置公司应付科目!')
            res = []
            payable_amount = 0
            line_taxes = self.procurement_id.purchase_line_id.taxes_id.compute_all(
                self.procurement_id.purchase_line_id.price_unit,
                self.procurement_id.purchase_line_id.order_id.currency_id,
                qty, self.procurement_id.purchase_line_id.product_id, self.procurement_id.purchase_line_id.order_id.partner_id
            )
            taxes = line_taxes['taxes']
            price_subtotal = line_taxes['total_excluded']
            for tax in taxes:
                res.append((0, 0, {
                    'name': self.procurement_id.purchase_line_id.order_id.name + ':' + tax['name'],
                    'quantity': 1,
                    'ref': self.picking_id.origin + ":" + self.picking_id.name if self.picking_id.origin else self.picking_id.name,
                    'partner_id': self.procurement_id.purchase_line_id.order_id.partner_id.id,
                    'debit': tax['amount'],
                    'credit': 0,
                    'account_id': tax['account_id'],
                }))
                payable_amount += tax['amount']
            accounts_data = self.product_id.product_tmpl_id.get_product_accounts()
            res.append((0, 0, {
                'name': self.product_id.display_name,
                'product_id': self.product_id.id,
                'quantity': self.product_uom_qty,
                'product_uom_id': self.product_id.uom_id.id,
                'ref': self.picking_id.origin + ":" + self.picking_id.name if self.picking_id.origin else self.picking_id.name,
                'partner_id': self.procurement_id.sale_line_id.order_id.partner_id.id,
                'debit': price_subtotal,
                'credit': 0,
                'account_id': accounts_data['stock_valuation'].id,
            }))
            payable_amount += price_subtotal
            res.append((0, 0, {
                'name': self.procurement_id.purchase_line_id.order_id.name + ':' + str(payable_amount),
                'product_id': self.product_id.id,
                'quantity': qty,
                'product_uom_id': self.product_id.uom_id.id,
                'ref': self.picking_id.origin + ":" + self.picking_id.name if self.picking_id.origin else self.picking_id.name,
                'partner_id': self.procurement_id.purchase_line_id.order_id.partner_id.id,
                'debit': 0,
                'credit': payable_amount,
                # 'account_id': self.procurement_id.purchase_line_id.order_id.partner_id.property_account_payable_id.id,
                'account_id': self.company_id.company_payable_acc_id.id,
            }))
        return res


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        out_invs = self.filtered(lambda s: s.type in ('out_invoice', 'out_refund', ))
        out_invs.action_out_move_create()
        in_invs = self.filtered(lambda s: s.type in ('in_invoice', 'in_refund', ))
        in_invs.action_in_move_create()
        invs = self - out_invs
        super(AccountInvoice, invs).action_move_create()
        return True

    @api.multi
    def action_out_move_create(self):
        """ Creates out invoice"""
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            if not inv.company_id.company_receivable_acc_id:
                raise UserError(u'请先配置公司应收科目!')

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = []
            tax_iml = inv.tax_line_move_line_get()

            name = inv.name or '/'
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)

            journal = inv.journal_id.with_context(ctx)

            iml = []
            iml_tax = inv.tax_line_move_line_get()

            diff_currency = inv.currency_id != company_currency

            for i in iml_tax:
                tax = self.env['account.tax'].browse(i['tax_line_id'])
                if not tax.invoice_account_id:
                    raise UserError(u'请先联系财务或IT配置【税开票科目】！')
                iml_tax_dest = i.copy()
                iml_tax_dest.update({'account_id': tax.invoice_account_id.id, 'price': - i['price']})
                iml += [iml_tax_dest]
            iml += iml_tax

            price_total = inv.amount_total
            if inv.type == 'out_refund':
                price_total = - price_total
            iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': price_total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'invoice_id': inv.id
                })

            iml.append({
                    'type': 'src',
                    'name': name,
                    'price': - price_total,
                    'account_id': inv.company_id.company_receivable_acc_id.id,
                    'date_maturity': inv.date_due,
                    'invoice_id': inv.id
                })

            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            date = inv.date or inv.date_invoice
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
        return True

    @api.multi
    def action_in_move_create(self):
        """ Creates in invoice"""
        account_move = self.env['account.move']

        for inv in self:
            if not inv.journal_id.sequence_id:
                raise UserError(_('Please define sequence on the journal related to this invoice.'))
            if not inv.invoice_line_ids:
                raise UserError(_('Please create some invoice lines.'))
            if inv.move_id:
                continue

            if not inv.company_id.company_payable_acc_id:
                raise UserError(u'请先配置公司应付科目!')

            ctx = dict(self._context, lang=inv.partner_id.lang)

            if not inv.date_invoice:
                inv.with_context(ctx).write({'date_invoice': fields.Date.context_today(self)})
            company_currency = inv.company_id.currency_id

            # create move lines (one per invoice line + eventual taxes and analytic lines)
            iml = []
            tax_iml = inv.tax_line_move_line_get()

            name = inv.name or '/'
            part = self.env['res.partner']._find_accounting_partner(inv.partner_id)

            journal = inv.journal_id.with_context(ctx)

            iml = []
            iml_tax = inv.tax_line_move_line_get()

            diff_currency = inv.currency_id != company_currency

            for i in iml_tax:
                tax = self.env['account.tax'].browse(i['tax_line_id'])
                if not tax.invoice_account_id:
                    raise UserError(u'请先联系财务或IT配置【税开票科目】！')
                iml_tax_dest = i.copy()
                iml_tax_dest.update({'account_id': tax.invoice_account_id.id, 'price': - i['price']})
                iml += [iml_tax_dest]
            iml += iml_tax

            price_total = inv.amount_total
            if inv.type == 'in_refund':
                price_total = - price_total
            iml.append({
                    'type': 'dest',
                    'name': name,
                    'price': price_total,
                    'account_id': inv.company_id.company_payable_acc_id.id,
                    'date_maturity': inv.date_due,
                    'invoice_id': inv.id
                })

            iml.append({
                    'type': 'src',
                    'name': name,
                    'price': - price_total,
                    'account_id': inv.account_id.id,
                    'date_maturity': inv.date_due,
                    'invoice_id': inv.id
                })

            line = [(0, 0, self.line_get_convert(l, part.id)) for l in iml]
            date = inv.date or inv.date_invoice
            move_vals = {
                'ref': inv.reference,
                'line_ids': line,
                'journal_id': journal.id,
                'date': date,
                'narration': inv.comment,
            }
            ctx['company_id'] = inv.company_id.id
            ctx['invoice'] = inv
            ctx_nolang = ctx.copy()
            ctx_nolang.pop('lang', None)
            move = account_move.with_context(ctx_nolang).create(move_vals)
            # Pass invoice in context in method post: used if you want to get the same
            # account move reference when creating the same invoice after a cancelled one:
            move.post()
            # make the invoice point to that move
            vals = {
                'move_id': move.id,
                'date': date,
                'move_name': move.name,
            }
            inv.with_context(ctx).write(vals)
        return True

    @api.multi
    def action_invoice_open(self):
        self.check_pre_data()
        return super(AccountInvoice, self).action_invoice_open()

    @api.multi
    def check_pre_data(self):
        payment_model = self.env['account.payment']
        customer_invoice = self.filtered(
                lambda s: s.type == 'out_invoice' and s.state in ('proforma2', 'draft')
            )
        partner_model = self.env['res.partner']
        if customer_invoice:
            so_names = customer_invoice.mapped('origin')

            payment_ids = payment_model.search([
                ('communication', 'in', so_names), 
                ('is_pre_payment', '=', True), 
                ('payment_type', '=', 'inbound'), 
                ('state', '=', 'posted')], limit=1)
            if payment_ids:
                raise UserError(u'存在未冲销的预收款！不能提交发票！%s'%payment_ids.name)

        supplier_invoice = self.filtered(
                lambda s: s.type == 'in_invoice' and s.state in ('proforma2', 'draft')
            )
        if supplier_invoice:
            origin = supplier_invoice.mapped('origin')
            po_names = []
            for o in origin:
                po_names += o.split(', ')
            payment_ids = payment_model.search([
                ('communication', 'in', po_names), 
                ('is_pre_payment', '=', True), 
                ('payment_type', '=', 'outbound'), 
                ('state', '=', 'posted')], limit=1)
            if payment_ids:
                raise UserError(u'存在未冲销的预付款！不能提交发票！%s'%payment_ids.name)

class AccountPayment(models.Model):
    _inherit = 'account.payment'

    is_pre_payment = fields.Boolean(u'是否预付/预收', default=False)

    @api.one
    @api.depends('invoice_ids', 'payment_type', 'partner_type', 'partner_id')
    def _compute_destination_account_id(self):
        if self.invoice_ids:
            self.destination_account_id = self.invoice_ids[0].account_id.id
        elif self.payment_type == 'transfer':
            if not self.company_id.transfer_account_id.id:
                raise UserError(_('Transfer account not defined on the company.'))
            self.destination_account_id = self.company_id.transfer_account_id.id
        elif self.partner_id:
            if self.partner_type == 'customer':
                if not self.is_pre_payment:
                    self.destination_account_id = self.partner_id.property_account_receivable_id.id 
                else:
                    if not self.company_id.company_prereceive_acc_id:
                        raise UserError(_('公司预收科目未定义.'))
                    self.destination_account_id = self.company_id.company_prereceive_acc_id.id
            else:
                if not self.is_pre_payment:
                    self.destination_account_id = self.partner_id.property_account_payable_id.id
                else:
                    if not self.company_id.company_prepay_acc_id:
                        raise UserError(_('公司预付科目未定义.'))
                    self.destination_account_id = self.company_id.company_prepay_acc_id.id

    # def _create_payment_entry(self, amount):
    #     if self.is_pre_payment:
    #         amount = - amount
    #     return super(AccountPayment, self)._create_payment_entry(amount)

    @api.multi
    def action_writeoff(self):
        payment_ids = self.filtered(lambda s: s.state == 'posted')
        payment_ids.mapped(
                'move_line_ids.move_id'
            ).reverse_moves()
        payment_ids.write({'state': 'reconciled'})
        return True