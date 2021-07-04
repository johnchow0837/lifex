# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp
from odoo.tools.float_utils import float_compare, float_round

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
        elif self.location_dest_id.usage == 'inventory' or self.location_id.usage == 'inventory':
            res = super(StockMove, self)._prepare_account_move_line(qty, cost, credit_account_id, debit_account_id)
        return res


class AccountInvoice(models.Model):
    _inherit = 'account.invoice'

    @api.multi
    def get_remaining_order_payment_amount(self):
        # purchase_ids = self.mapped('invoice_line_ids.purchase_line_id.order_id')
        for inv in self:
            purchase_ids = inv.mapped('invoice_line_ids.purchase_line_id.order_id')
            inv.remaining_order_payment_amount = sum(
                [purchase_id.remaining_payment_amount for purchase_id in purchase_ids]
            )

    remaining_order_payment_amount = fields.Float(
        compute='get_remaining_order_payment_amount', digits=dp.get_precision('Product Price'),
        string=u'PO剩余金额'
    )

    @api.multi
    def action_po_payment_by_invoice(self, journal_id, date, communication):
        invoice_line_ids = self.mapped('invoice_line_ids')
        purchase_ids = invoice_line_ids.mapped('purchase_line_id.order_id')
        val_list = []
        payment_amount = 0
        payment_method_id = self.env.ref('account.account_payment_method_manual_out').id
        tmp_val = {
            'payment_type': 'outbound',
            'payment_method_id': payment_method_id,
            'communication': communication,
            'payment_date': date,
            'journal_id': journal_id,
            'partner_type': 'supplier'
        }
        for purchase_id in purchase_ids:
            line_ids = invoice_line_ids.filtered(
                lambda s: s.purchase_line_id.order_id == purchase_id
            )
            purchase_payment_amount = sum(
                [
                    float_round(
                        line_id.quantity * line_id.price_unit,
                        precision_digits=self.env['decimal.precision'].precision_get('Product Price')) for line_id in line_ids
                ]
            )
            payment_amount += purchase_payment_amount
            if float_compare(
                    purchase_payment_amount, purchase_id.remaining_payment_amount,
                    precision_digits=self.env['decimal.precision'].precision_get('Product Price')
            ) > 0:
                raise UserError(u'采购单剩余付款金额[%s]不足发票付款金额[%s], 无法付款！' % (purchase_id.remaining_payment_amount, purchase_payment_amount))
            val = tmp_val.copy()
            val.update({
                'amount': purchase_payment_amount,
                'partner_id': purchase_id.partner_id.id,
                'currency_id': purchase_id.currency_id.id,
                'purchase_id': purchase_id.id,
            })
            val_list.append(val)
        payment_partner_id = self.env['account.payment.partner'].create({
            'partner_id': self.mapped('partner_id').id,
            'payment_date': date,
            'amount': payment_amount,
            'communication': communication,
            'journal_id': journal_id,
            'state': 'confirmed',
            'partner_type': 'supplier',
            'origin': ','.join(self.mapped('number')),
        })
        for v in val_list:
            v.update({'payment_partner_id': payment_partner_id.id})
            payment_id = self.env['account.payment'].create(v)
            payment_id.post()
        return True

    @api.multi
    def action_payment_by_invoice(self, journal_id, date, communication):
        self.filtered(
            lambda s: s.state == 'open' and s.type == 'in_invoice'
        ).action_po_payment_by_invoice(journal_id, date, communication)
        return True

    @api.multi
    def action_payment_by_invoice_wizard(self):
        if self.filtered(lambda s: s.state != 'open' or s.type != 'in_invoice'):
            raise UserError(u'只有打开状态且采购发票支持付款！')
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.invoice.payment.wizard',
            'view_mode': 'form',
            'view_type': 'form',
            'target': 'new',
        }

    @api.multi
    def action_move_create(self):
        """ Creates invoice related analytics and financial move lines """
        out_invs = self.filtered(lambda s: s.type in ('out_invoice', 'out_refund', ))
        out_invs.action_out_move_create()
        in_invs = self.filtered(lambda s: s.type in ('in_invoice', 'in_refund', ))
        in_invs.action_in_move_create()
        invs = self - out_invs - in_invs
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
    def action_invoice_open_check(self):
        invalid_invs = self.filtered(
                lambda s: s.state not in ('proforma2', 'draft')
            )
        if invalid_invs:
            raise UserError(u'只有草稿状态的发票才能提交！')
        payment_model = self.env['account.payment']
        pre_payment_ids = payment_model.browse()
        so_names = self.mapped('invoice_line_ids.sale_line_ids.order_id.name')
        if so_names:
            pre_payment_ids |= payment_model.search([
                 ('communication', 'in', so_names), 
                 ('is_pre_payment', '=', True), 
                 ('payment_type', '=', 'inbound'), 
                 ('state', '=', 'posted')])

        po_names = self.mapped('invoice_line_ids.purchase_line_id.order_id.name')
        if po_names:
            pre_payment_ids |= payment_model.search([
                 ('communication', 'in', po_names), 
                 ('is_pre_payment', '=', True), 
                 ('payment_type', '=', 'outbound'), 
                 ('state', '=', 'posted')])
        if pre_payment_ids:
            payment_lines = [(0, 0, {
                'payment_id': pre_payment_id.id,
                'amount': 0,
                'amount_residual': pre_payment_id.amount_residual,
            }) for pre_payment_id in pre_payment_ids]
            ctx = self.env.context.copy()
            ctx.update({
                'default_invoice_ids': [(6, 0, self.ids)],
                'default_payment_lines': payment_lines,
            })
            return {
                'name': u'核销预付款',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'account.invoice.pre.check.wizard',
                'type': 'ir.actions.act_window',
                'context': ctx,
                'target': 'new'
            }
        return self.action_invoice_open()

    #@api.multi
    #ef check_pre_data(self):
        #pass
        # payment_model = self.env['account.payment']
        # customer_invoice = self.filtered(
        #         lambda s: s.type == 'out_invoice' and s.state in ('proforma2', 'draft')
        #     )
        # if customer_invoice:
        #     so_names = customer_invoice.mapped('origin')

        #     payment_ids = payment_model.search([
        #         ('communication', 'in', so_names), 
        #         ('is_pre_payment', '=', True), 
        #         ('payment_type', '=', 'inbound'), 
        #         ('state', '=', 'posted')], limit=1)
        #     if payment_ids:
        #         raise UserError(u'存在未冲销的预收款！不能提交发票！%s'%payment_ids.name)

        # supplier_invoice = self.filtered(
        #         lambda s: s.type == 'in_invoice' and s.state in ('proforma2', 'draft')
        #     )
        # if supplier_invoice:
        #     origin = supplier_invoice.mapped('origin')
        #     po_names = []
        #     for o in origin:
        #         po_names += o.split(', ')
        #     payment_ids = payment_model.search([
        #         ('communication', 'in', po_names), 
        #         ('is_pre_payment', '=', True), 
        #         ('payment_type', '=', 'outbound'), 
        #         ('state', '=', 'posted')], limit=1)
        #     if payment_ids:
        #         raise UserError(u'存在未冲销的预付款！不能提交发票！%s'%payment_ids.name)


class AccountInvoicePreCheckWizard(models.TransientModel):
    _name = 'account.invoice.pre.check.wizard'

    invoice_ids = fields.Many2many('account.invoice', string=u'发票', readonly=True)
    reverse_date = fields.Date(string=u'冲销日期', default=lambda self: fields.Date.context_today(self), required=True)
    journal_id = fields.Many2one('account.journal', string=u'日记账', required=True)
    payment_lines = fields.One2many('account.invoice.pre.check.wizard.line', 'wizard_id', u'付款明细')

    @api.multi
    def action_confirm(self):
        pre_payment_ids = self.payment_lines.filtered(
            lambda s: float_compare(s.amount, 0, precision_digits=self.env['decimal.precision'].precision_get('Product Price')) > 0
        )
        for pre_payment_id in pre_payment_ids:
            pre_payment_id.payment_id.action_reverse_account_move(
                date=self.reverse_date, journal_id=self.journal_id, amount=pre_payment_id.amount
            )
        return self.invoice_ids.action_invoice_open()


class AccountInvoicePreCheckWizardLine(models.TransientModel):
    _name = 'account.invoice.pre.check.wizard.line'

    wizard_id = fields.Many2one('account.invoice.pre.check.wizard', string=u'弹窗')
    payment_id = fields.Many2one('account.payment', string=u'付款记录', readonly=True)
    amount = fields.Float(string=u'冲销金额', digits=dp.get_precision('Product Price'))
    amount_residual = fields.Float(string=u'剩余未冲销金额', digits=dp.get_precision('Product Price'), readonly=True)


class AccountPayment(models.Model):
    _inherit = 'account.payment'

    @api.depends('move_line_ids')
    def get_amount_residual(self):
        move_line_ids = self.mapped('move_line_ids')
        for payment in self:
            move_line_id = move_line_ids.filtered(
                lambda s: s.account_id == payment.destination_account_id 
                and s.payment_id == payment
            )
            payment.amount_residual = abs(move_line_id.amount_residual)

    @api.depends(
        'amount',
        'return_payment_ids',
        'return_payment_ids.amount',
        'return_payment_ids.state'
    )
    def get_remaining_payment_amount(self):
        for payment_id in self:
            return_amount = 0
            for return_payment_id in payment_id.return_payment_ids.filtered(lambda s: s.state in ('draft', 'posted')):
                return_amount += return_payment_id.amount
            payment_id.remaining_payment_amount = payment_id.amount - return_amount

    @api.depends('amount', 'partner_type', 'payment_type')
    def get_actual_amount(self):
        for s, amount, partner_type, payment_type in self.mapped(lambda s: (s, s.amount, s.partner_type, s.payment_type, )):
            if s.state == 'cancel':
                s.actual_amount = 0
            else:
                if (partner_type == 'customer' and payment_type == 'outbound') or (partner_type == 'supplier' and payment_type == 'inbound'):
                    s.actual_amount = - amount
                else:
                    s.actual_amount = amount

    is_pre_payment = fields.Boolean(u'是否预付/预收', default=False)
    amount_residual = fields.Float(compute='get_amount_residual', string=u'剩余未冲销金额', digits=dp.get_precision('Product Price'))
    # order_name = fields.Char(u'单号')
    sale_id = fields.Many2one('sale.order', u'销售订单')
    purchase_id = fields.Many2one('purchase.order', u'采购订单')
    state = fields.Selection(selection_add=[('cancel', u'取消')])
    payment_partner_id = fields.Many2one('account.payment.partner', u'客户维度收款', ondelete='restrict')
    return_payment_ids = fields.One2many('account.payment', 'origin_payment_id', string=u'退款明细')
    origin_payment_id = fields.Many2one('account.payment', string=u'原款项', index=1)
    remaining_payment_amount = fields.Float(compute='get_remaining_payment_amount', string=u'剩余未退金额', digits=dp.get_precision('Product Price'))
    actual_amount = fields.Float(compute='get_actual_amount', string=u'实际金额', digits=dp.get_precision('Product Price'))

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

    @api.multi
    def action_view_reverse_wizard(self):
        if self.state != 'posted':
            raise UserError(u'只有已过帐的付/收款才能退款！')
        if not self.is_pre_payment:
            raise UserError(u'目前仅支持预付/收款冲销！')
        ctx = self.env.context.copy()
        ctx.update({
                'default_journal_id': self.journal_id.id,
                'default_amount': self.amount_residual,
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.write.off.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def action_view_return_wizard(self):
        if self.state != 'posted':
            raise UserError(u'只有已过帐的付/收款才能退款！')
        # if not self.is_pre_payment:
        #     raise UserError(u'目前仅支持预付/收款冲销！')
        if (self.partner_type == 'customer' and self.payment_type != 'inbound') \
            or (self.partner_type == 'supplier' and self.payment_type != 'outbound'):
            raise UserError(u'退款的记录不再支持退款！')
        ctx = self.env.context.copy()
        ctx.update({
                'default_amount': self.remaining_payment_amount,
            })
        return {
            'type': 'ir.actions.act_window',
            'res_model': 'account.payment.return.wizard',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'context': ctx,
        }

    @api.multi
    def check_return_payment_data(self):
        if float_compare(
                self.remaining_payment_amount, 0, precision_digits=self.env['decimal.precision'].precision_get('Product Price')
        ) < 0:
            raise UserError(u'退款金额不能超过原金额！')
        if (self.partner_type == 'customer' and self.payment_type != 'inbound') \
            or (self.partner_type == 'supplier' and self.payment_type != 'outbound'):
            raise UserError(u'退款的记录不再支持退款！')
        if self.state != 'posted':
            raise UserError(u'只有已过帐的付/收款才能退款！')
        return True

    @api.multi
    def action_reverse_account_move(self, date, journal_id, amount):
        if float_compare(amount, 0, precision_digits=self.env['decimal.precision'].precision_get('Product Price')) > 0:
            self.action_writeoff(date=date, journal_id=journal_id, amount=amount)
        self.filtered(
            lambda s: float_compare(s.amount_residual, 0, precision_rounding=s.currency_id.rounding) <= 0
        ).write({'state': 'reconciled'})
        return True

    @api.multi
    def action_writeoff(self, date=None, journal_id=None, amount=0):
        payment_ids = self.filtered(lambda s: s.state == 'posted')
        date = date or fields.Date.today()
        reversed_moves = self.env['account.move']
        for payment_id in payment_ids:
            #unreconcile all lines reversed
            ac_move = payment_id.mapped(
                    'move_line_ids.move_id'
                )
            aml = ac_move.line_ids.filtered(lambda x: x.account_id.reconcile or x.account_id.internal_type == 'liquidity')
            if amount:
                wrong_aml = aml.filtered(
                    lambda s: float_compare(abs(s.amount_residual), amount, precision_digits=self.env['decimal.precision'].precision_get('Product Price')) < 0
                            and s.account_id == payment_id.destination_account_id
                )
                if wrong_aml:
                    raise UserError(u'冲销金额大于未冲销金额：%s'% ac_move.name)
            reversed_move = ac_move.copy(default={
                'date': date,
                'journal_id': journal_id.id if journal_id else ac_move.journal_id.id,
                'ref': _('reversal of: ') + ac_move.name})
            for acm_line in reversed_move.line_ids.with_context(check_move_validity=False):
                amount_currency = 0
                if acm_line.currency_id:
                    amount_currency = (acm_line.amount_currency / abs(acm_line.amount_currency)) * amount
                credit, debit = 0, 0
                if acm_line.debit:
                    credit = amount or abs(acm_line.amount_residual)
                elif acm_line.credit:
                    debit = amount or abs(acm_line.amount_residual)
                _logger.info("credit:%s", credit)
                _logger.info("debit:%s", debit)
                acm_line.write({
                    'debit': debit,
                    'credit': credit,
                    'amount_currency': amount_currency
                })
            self.env['account.move']._reconcile_reversed_pair(ac_move, reversed_move)
            reversed_moves |= reversed_move
        if reversed_moves:
            reversed_moves._post_validate()
            reversed_moves.post()
            return [x.id for x in reversed_moves]
        return []

    @api.multi
    def post(self):
        res = super(AccountPayment, self).post()
        for payment in self:
            invoice_ids = self.mapped('invoice_ids')
            sale_ids = invoice_ids.mapped(
                'invoice_line_ids.sale_line_ids.order_id'
            )
            invoice_nums = ','.join(list(set(invoice_ids.mapped('name'))))
            sale_names = ','.join(sale_ids.mapped('name'))
            for sale_id in sale_ids:
                message = u"""<a>销售订单:%s, 票%s, 收款:%s元</a>
                        <a href='/web#model=res.partner&id=%s'>@%s</a>, 
                        <a href='/web#model=res.partner&id=%s'>@%s</a>""" % (
                    sale_names, invoice_nums, payment.amount,
                    sale_id.user_id.partner_id.id, sale_id.user_id.partner_id.name,
                    sale_id.create_uid.partner_id.id, sale_id.create_uid.partner_id.name
                )
                sale_id.message_post(body=message)
        return res

    @api.multi
    def action_reverse(self):
        if self.filtered(lambda s: s.state != 'posted'):
            raise UserError(u'只能红冲已过帐的款项！')
        ac_move = self.mapped(
            'move_line_ids.move_id'
        )
        ac_move.reverse_moves()
        self.write({'state': 'reconciled'})
        return True

    @api.multi
    def cancel(self):
        for rec in self:
            for move in rec.move_line_ids.mapped('move_id'):
                if rec.invoice_ids:
                    move.line_ids.remove_move_reconcile()
                move.button_cancel()
                move.unlink()
            rec.state = 'cancel'

    @api.multi
    def action_return(self, amount, date=False):
        return_payment_id = self.copy({
            'amount': amount, 'payment_date': date or datetime.now().strftime('%Y-%m-%d'),
            'origin_payment_id': self.id, 'payment_type': 'outbound' if self.payment_type == 'inbound' else 'inbound'
        })
        self.check_return_payment_data()
        return_payment_id.post()
        return True


class AccountPaymentWriteOffWizard(models.TransientModel):
    _name = 'account.payment.write.off.wizard'

    reverse_date = fields.Date(string=u'冲销日期', default=lambda self: fields.Date.context_today(self), required=True)
    amount = fields.Float(string=u'冲销金额', digits=dp.get_precision('Product Price'))
    journal_id = fields.Many2one('account.journal', string=u'日记账', required=True)

    @api.multi
    def button_reverse(self):
        payment_ids = self.env['account.payment'].browse(self.env.context['active_ids'])
        payment_ids.action_reverse_account_move(date=self.reverse_date, journal_id=self.journal_id, amount=self.amount)
        return True


class AccountPaymentReturnWizard(models.TransientModel):
    _name = 'account.payment.return.wizard'

    amount = fields.Float(string=u'退款金额', digits=dp.get_precision('Product Price'))

    @api.multi
    def button_return(self):
        payment_ids = self.env['account.payment'].browse(self.env.context['active_ids'])
        payment_ids.action_return(amount=self.amount)
        return True


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    @api.depends('payment_ids', 'payment_ids.amount', 'amount_total', 'payment_ids.state')
    def get_payment_amount(self):
        for sale in self:
            payment_amount = 0
            for payment_id in sale.payment_ids.filtered(lambda s: s.state == 'posted'):
                if payment_id.payment_type == 'outbound':
                    payment_amount -= payment_id.amount
                elif payment_id.payment_type == 'inbound':
                    payment_amount += payment_id.amount
            sale.payment_amount = payment_amount
            sale.remaining_payment_amount = sale.amount_total - payment_amount

    payment_ids = fields.One2many('account.payment', 'sale_id', u'收款记录')
    payment_amount = fields.Float(compute="get_payment_amount", string=u'收款金额', store=True)
    remaining_payment_amount = fields.Float(compute="get_payment_amount", string=u'剩余收款', store=True)

    @api.multi
    def check_order_payment_state(self):
        if not self:
            return True
        if self.state == 'cancel':
            raise UserError(u'只又未取消的销售单才能收款!')
        if self.remaining_payment_amount < -0.01:
            raise UserError(u'已经收款的销售单不能再进行收款!')
        return True

    @api.multi
    def check_order_return_payment_state(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        if not self:
            return True
        # if self.state not in ('sale', 'done', 'cancel'):
        #     raise UserError(u'只有已确认或已取消的销售单才能退款!')
        if float_compare(self.remaining_payment_amount, self.amount_total, precision_digits=prec) > 0:
            raise UserError(u'退款金额不能超过订单金额!')
        return True

    @api.multi
    def action_payment_wizard(self):
        # self.check_order_payment_state()
        ctx = self.env.context.copy()
        ctx.update({
            'default_payment_type': 'inbound',
            'default_amount': self.remaining_payment_amount if self.remaining_payment_amount > 0 else 0
        })
        return {
            'name': '收/付款',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'order.payment.wizard',
            'type': 'ir.actions.act_window',
            'context': ctx,
        }

    @api.multi
    def action_return_payment_wizard(self):
        # self.check_order_payment_state()
        ctx = self.env.context.copy()
        ctx.update({
            'default_payment_type': 'outbound',
            'default_amount': self.payment_amount,
            'action_refund': True
        })
        return {
            'name': '退款',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'order.payment.wizard',
            'type': 'ir.actions.act_window',
            'context': ctx,
        }


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    @api.depends('payment_ids', 'payment_ids.amount', 'amount_total', 'payment_ids.state')
    def get_payment_amount(self):
        for purchase in self:
            payment_amount = 0
            for payment_id in purchase.payment_ids.filtered(lambda s: s.state == 'posted'):
                if payment_id.payment_type == 'outbound':
                    payment_amount += payment_id.amount
                elif payment_id.payment_type == 'inbound':
                    payment_amount -= payment_id.amount
            purchase.payment_amount = payment_amount
            purchase.remaining_payment_amount = purchase.amount_total - payment_amount

    payment_ids = fields.One2many('account.payment', 'purchase_id', u'付款记录')
    payment_amount = fields.Float(compute="get_payment_amount", string=u'付款金额', store=True, digits=dp.get_precision('Product Price'))
    remaining_payment_amount = fields.Float(compute="get_payment_amount", string=u'剩余付款', store=True, digits=dp.get_precision('Product Price'))

    @api.multi
    def check_order_payment_state(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        if not self:
            return True
        if self.state == 'cancel':
            raise UserError(u'已取消的订单不能付款!')
        if float_compare(self.remaining_payment_amount, 0, precision_digits=prec) < 0:
            raise UserError(u'已经付款的采购单不能再进行付款!')
        # if float_compare(self.remaining_payment_amount, self.amount_total_actual, precision_digits=prec) < 0:
        #     raise UserError(u'已经付款的采购单不能再进行付款!')
        return True

    @api.multi
    def check_order_return_payment_state(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        if not self:
            return True
        # if self.state not in ('purchase', 'done', 'cancel'):
        #     raise UserError(u'只有已确认或已取消的采购单才能退款!')
        if float_compare(self.remaining_payment_amount, self.amount_total, precision_digits=prec) > 0:
            raise UserError(u'退款金额不能超过订单金额!')
        return True

    @api.multi
    def action_payment_wizard(self):
        # self.check_order_payment_state()
        ctx = self.env.context.copy()
        ctx.update({
            'default_payment_type': 'outbound',
            'default_amount': self.remaining_payment_amount if self.remaining_payment_amount > 0 else 0
        })
        return {
            'name': '收/付款',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'order.payment.wizard',
            'type': 'ir.actions.act_window',
            'context': ctx,
        }

    @api.multi
    def action_return_payment_wizard(self):
        # self.check_order_payment_state()
        ctx = self.env.context.copy()
        ctx.update({
            'default_payment_type': 'inbound',
            'default_amount': self.payment_amount,
            'action_refund': True
        })
        return {
            'name': '退款',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'order.payment.wizard',
            'type': 'ir.actions.act_window',
            'context': ctx,
        }


class OrderPaymentWizard(models.TransientModel):
    _name = 'order.payment.wizard'

    payment_type = fields.Selection([('inbound', u'收款'), ('outbound', u'付款')], string=u'操作类型', required=1)
    amount = fields.Float(u'金额', required=1, digits=dp.get_precision('Product Price'))
    payment_date = fields.Date(u'付款日期', required=1)
    communication = fields.Char(u'备注')
    journal_id = fields.Many2one('account.journal', u'付款方式', required=1)

    @api.multi
    def action_pay(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        active_model = self.env.context.get('active_model', '')
        order_ids = self.env[
            self.env.context.get('active_model', '')
        ].browse(self.env.context.get('active_ids', []))
        if float_compare(self.amount, 0, precision_digits=prec) <= 0:
            raise UserError(u'金额必须大于0！')
        if float_compare(self.amount - order_ids.remaining_payment_amount, 0, precision_digits=prec) > 0:
            raise UserError(u'收款金额不能大于剩余应收！')
        payment_method_id = self.env.ref('account.account_payment_method_manual_in').id \
            if self.payment_type == 'inbound' else self.env.ref('account.account_payment_method_manual_out').id
        val = {
            'payment_type': self.payment_type,
            'amount': self.amount,
            'payment_method_id': payment_method_id,
            'partner_id': order_ids.partner_id.id,
            'communication': self.communication,
            'currency_id': order_ids.currency_id.id,
            'payment_date': self.payment_date,
            'journal_id': self.journal_id.id,
        }
        if active_model == 'sale.order':
            val.update({'sale_id': order_ids.id, 'partner_type': 'customer'})
        elif active_model == 'purchase.order':
            val.update({'purchase_id': order_ids.id, 'partner_type': 'supplier'})
        payment_id = self.env['account.payment'].create(val)
        payment_id.post()
        order_ids.check_order_payment_state()
        return True

    @api.multi
    def action_return_pay(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        active_model = self.env.context.get('active_model', '')
        order_ids = self.env[
            self.env.context.get('active_model', '')
        ].browse(self.env.context.get('active_ids', []))
        if float_compare(self.amount, 0, precision_digits=prec) <= 0:
            raise UserError(u'金额必须大于0！')
        if float_compare(self.amount, order_ids.payment_amount, precision_digits=prec) > 0:
            raise UserError(u'退款金額不能大于已收款金額！')
        payment_method_id = self.env.ref('account.account_payment_method_manual_in').id \
            if self.payment_type == 'inbound' else self.env.ref('account.account_payment_method_manual_out').id
        val = {
            'payment_type': self.payment_type,
            'amount': self.amount,
            'payment_method_id': payment_method_id,
            'partner_id': order_ids.partner_id.id,
            'communication': self.communication,
            'currency_id': order_ids.currency_id.id,
            'payment_date': self.payment_date,
            'journal_id': self.journal_id.id,
        }
        if active_model == 'sale.order':
            val.update({'sale_id': order_ids.id, 'partner_type': 'customer'})
        elif active_model == 'purchase.order':
            val.update({'purchase_id': order_ids.id, 'partner_type': 'supplier'})
        payment_id = self.env['account.payment'].create(val)
        payment_id.post()
        order_ids.check_order_return_payment_state()
        return True


class AccountPaymentPartner(models.Model):
    """按客户/供应商维度收付款"""
    _name = 'account.payment.partner'

    @api.depends('amount', 'payment_ids', 'payment_ids.state', 'payment_ids.amount')
    def get_remaining_amount(self):
        for payment in self:
            sum_amount = 0
            for pay in payment.payment_ids.filtered(lambda s: s.state == 'posted'):
                if (payment.partner_type == 'customer' and pay.payment_type == 'inbound') \
                        or (payment.partner_type == 'supplier' and pay.payment_type == 'outbound'):
                    sum_amount += pay.amount
                else:
                    sum_amount -= pay.amount
            payment.remaining_amount = payment.amount - sum_amount

    partner_id = fields.Many2one('res.partner', u'业务伙伴', required=1)
    payment_date = fields.Date(u'日期', required=1)
    amount = fields.Float(u'金额', digits=dp.get_precision('Product Price'))
    remaining_amount = fields.Float(
        compute='get_remaining_amount', string=u'剩余金额',
        digits=dp.get_precision('Product Price'), store=True
    )
    payment_ids = fields.One2many('account.payment', 'payment_partner_id', string=u'款项明细')
    partner_type = fields.Selection([('customer', 'Customer'), ('supplier', 'Vendor')], required=1)
    communication = fields.Char(u'付款备注')
    journal_id = fields.Many2one('account.journal', u'付款方式', required=1)
    state = fields.Selection([('draft', u'草稿'), ('confirmed', u'已确认'), ('cancel', u'作废')], string=u'状态', default='draft')
    origin = fields.Char(u'源单据', readonly=1)

    @api.multi
    def action_cancel(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        if self.filtered(lambda s: float_compare(s.amount, s.remaining_amount, precision_digits=prec) != 0):
            raise UserError(u'只有余额等于初始金额才能作废！')
        self.write({'state': 'cancel'})

    @api.multi
    def action_confirm(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        if self.filtered(lambda s: float_compare(s.amount, 0, precision_digits=prec) <= 0):
            raise UserError(u'付款金额必须大于0！')
        self.filtered(lambda s: s.state == 'draft').write({'state': 'confirmed'})

    @api.multi
    def check_payment_data(self):
        if self.state != 'confirmed':
            raise UserError(u'只有已确认的单据才能处理！')
        prec = self.env['decimal.precision'].precision_get('Product Price')
        if float_compare(self.remaining_amount, 0, precision_digits=prec) < 0:
            raise UserError(u'剩余金额为0的单据不能再分配！')
        if float_compare(self.remaining_amount, self.amount, precision_digits=prec) > 0:
            raise UserError(u'剩余金额不能大于初始金额！')

    @api.multi
    def action_payment_wizard(self):
        # self.check_payment_data()
        ctx = self.env.context.copy()
        ctx.update({'default_payment_partner_id': self.id})
        view_id = self.env.ref('extra_account.view_account_payment_customer_wizard').id \
            if self.partner_type == 'customer' else self.env.ref('extra_account.view_account_payment_supplier_wizard').id
        return {
            'name': u'分配款项',
            'type': 'ir.actions.act_window',
            'view_mode': 'form',
            'res_model': 'account.payment.partner.wizard',
            'view_id': view_id,
            'target': 'new',
            'context': ctx
        }


class AccountPaymentPartnerWizard(models.TransientModel):
    """按客户/供应商维度收付款分配弹窗"""
    _name = 'account.payment.partner.wizard'

    @api.depends('payment_ids', 'payment_ids.amount')
    def get_remaining_amount(self):
        for wizard in self:
            sum_amount = 0
            for line in wizard.payment_ids:
                sum_amount += line.amount
            wizard.remaining_amount = wizard.payment_partner_id.remaining_amount - sum_amount

    payment_partner_id = fields.Many2one('account.payment.partner', string=u'收付款', readonly=1)
    payment_ids = fields.One2many(
        'account.payment.partner.wizard.line', 'wizard_id', string=u'款项明细', ondelete='cascade'
    )
    remaining_amount = fields.Float(
        compute='get_remaining_amount', string=u'剩余金额',
        digits=dp.get_precision('Product Price')
    )
    partner_id = fields.Many2one('res.partner', related='payment_partner_id.partner_id')

    @api.multi
    def action_order_pay(self):
        prec = self.env['decimal.precision'].precision_get('Product Price')
        if float_compare(self.remaining_amount, 0, precision_digits=prec) < 0:
            raise UserError(u'分配金额不能超过剩余金额！')
        payment_method_id = self.env.ref('account.account_payment_method_manual_in').id \
            if self.payment_partner_id.partner_type == 'customer' else self.env.ref('account.account_payment_method_manual_out').id
        tmp_val = {
            'payment_type': 'inbound' if self.payment_partner_id.partner_type == 'customer' else 'outbound',
            # 'amount': self.amount,
            'payment_method_id': payment_method_id,
            'partner_id': self.payment_partner_id.partner_id.id,
            'communication': self.payment_partner_id.communication,
            'payment_date': datetime.now().strftime('%Y-%m-%d'),
            'journal_id': self.payment_partner_id.journal_id.id,
            'partner_type': self.payment_partner_id.partner_type,
            'payment_partner_id': self.payment_partner_id.id,
        }
        for line in self.payment_ids:
            val = tmp_val.copy()
            val.update({
                'amount': line.amount,
                'sale_id': line.sale_id.id,
                'purchase_id': line.purchase_id.id,
                'currency_id': line.sale_id.currency_id.id or line.purchase_id.currency_id.id or False,
                # 'payment_type': line.payment_type
            })
            payment_id = self.env['account.payment'].create(val)
            payment_id.post()
            line.sale_id.check_order_payment_state()
            line.purchase_id.check_order_payment_state()
        self.payment_partner_id.check_payment_data()
        return True


class AccountPaymentPartnerWizardLine(models.TransientModel):
    """按客户/供应商维度收付款分配弹窗明细"""
    _name = 'account.payment.partner.wizard.line'

    @api.depends('sale_id', 'purchase_id')
    def get_remaining_payment_amount(self):
        for line in self:
            line.remaining_payment_amount = line.sale_id.remaining_payment_amount \
                if line.sale_id else line.purchase_id.remaining_payment_amount

    wizard_id = fields.Many2one('account.payment.partner.wizard', string=u'分配弹窗')
    sale_id = fields.Many2one('sale.order', u'销售订单')
    purchase_id = fields.Many2one('purchase.order', u'采购订单')
    remaining_payment_amount = fields.Float(compute='get_remaining_payment_amount', string=u'剩余金额')
    amount = fields.Float(u'金额', digits=dp.get_precision('Product Price'))
    partner_id = fields.Many2one('res.partner')
    # payment_type = fields.Selection([('inbound', u'收款'), ('outbound', u'付款')], string=u'操作类型', required=1)

    @api.onchange('sale_id', 'purchase_id')
    def onchange_order(self):
        for line in self:
            line.amount = line.sale_id.remaining_payment_amount \
                if line.sale_id else line.purchase_id.remaining_payment_amount
            # if not line.purchase_id:
            #     line.payment_type = 'inbound' if line.sale_id else False
            # elif not line.sale_id:
            #     line.payment_type = 'outbound' if line.purchase_id else False


class AccountInvoicePaymentWizard(models.TransientModel):
    """发票上付款"""
    _name = 'account.invoice.payment.wizard'

    payment_date = fields.Date(u'付款日期', required=1)
    communication = fields.Char(u'备注')
    journal_id = fields.Many2one('account.journal', u'付款方式', required=1)

    @api.multi
    def action_wizard_pay(self):
        invoice_ids = self.env['account.invoice'].browse(self.env.context.get('active_ids', []))
        if invoice_ids.filtered(lambda s: s.state != 'open' or s.type != 'in_invoice'):
            raise UserError(u'只有打开状态且采购发票支持付款！')
        invoice_ids.action_payment_by_invoice(self.journal_id.id, self.payment_date, self.communication)
        return True