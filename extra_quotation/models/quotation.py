# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Request Quotation
#----------------------------------------------------------
class SaleRequestQuotation(models.Model):
    _name = "sale.request.quotation"
    _description = u"客户询价单"
    _inherit = ['mail.thread', 'ir.needaction_mixin']

    @api.depends('order_line', 'order_line.quotation_lines')
    def get_quotation_state(self):
        for quotation in self:
            lines = quotation.mapped('order_line.quotation_lines')
            if not lines:
                quotation.quotation_state = 'no'
                continue
            else:
                no_re_lines = quotation.order_line.filtered(lambda s: not s.quotation_lines)
                if no_re_lines:
                    quotation.quotation_state = 'partial'
                else:
                    quotation.quotation_state = 'yes'

    name = fields.Char(string=u'询价单号', required=True, index=True, copy=False, readonly=True, states={'draft': [('readonly', False)]}, default=lambda self: 'New')

    state = fields.Selection([
        ('draft', u'草稿'),
        ('commited', u'已提交'),
        ('progress', u'处理中'),
        ('closed', u'完成'),
        ('cancel', u'已取消'),
        ], string=u'状态', readonly=True, copy=False, index=True, track_visibility='onchange', default='draft')

    quotation_state = fields.Selection([('no', u'未报价'), ('partial', u'部分报价'), ('yes', u'已报价')], compute='get_quotation_state', store=True, string=u'询价状态', readonly=True)

    required_currency = fields.Many2one('res.currency', string=u'报价币种', required=True, readonly=True, states={'draft': [('readonly', False)]})

    create_date = fields.Datetime(string=u'创建时间', readonly=True, index=True)
    commited_date = fields.Datetime(string=u'提交时间', readonly=True, index=True, help="Date on which the request quotation is commited.", copy=False)
    commited_user = fields.Many2one('res.users', string=u'提交人', index=True, track_visibility='onchange', readonly=True, copy=False)
    processed_date = fields.Datetime(string=u'处理时间', readonly=True, index=True, copy=False)
    processed_user = fields.Many2one('res.users', string=u'处理人', index=True, track_visibility='onchange', readonly=True, copy=False)
    closed_date = fields.Datetime(string=u'关闭时间', index=True, readonly=True, copy=False)
    closed_user = fields.Many2one('res.users', string=u'关闭人', index=True, readonly=True, track_visibility='onchange', copy=False)
    cancelled_date = fields.Datetime(string=u'取消时间', index=True, readonly=True, copy=False)
    cancelled_user = fields.Many2one('res.users', string=u'取消人', index=True, track_visibility='onchange', readonly=True, copy=False)


    user_id = fields.Many2one('res.users', string=u'询价员', index=True, readonly=True, states={'draft': [('readonly', False)]}, track_visibility='onchange', default=lambda self: self.env.user)
    partner_id = fields.Many2one('res.partner', string=u'客户', readonly=True, states={'draft': [('readonly', False)]}, required=True, change_default=True, index=True, track_visibility='always')
    partner_name = fields.Char(string=u'客户名称', required=True, readonly=True, states={'draft': [('readonly', False)]}, track_visibility='always')

    order_line = fields.One2many('sale.request.quotation.line', 'request_quotation_id', string=u'客户询价表', states={'cancel': [('readonly', True)], 'done': [('readonly', True)]}, copy=True)

    note = fields.Text(string=u'备注')

    product_name = fields.Char(related='order_line.product_name', string=u'产品名称')

    _sql_constraints = [
        ('quotation_name_uniq', 'unique (name)', u'询价单号不能重复 !')
    ]

    @api.multi
    def unlink(self):
        records = self.filtered(lambda s: s.state != 'draft')
        if records:raise UserError(u'只能删除草稿状态记录！')
        return super(SaleRequestQuotation, self).unlink()

    @api.onchange('partner_id')
    def onchange_partner_id(self):
        if self.partner_id:
            self.partner_name = self.partner_id.name
        else:
            self.partner_name = ''

    @api.multi
    def action_commit(self):
        self.filtered(lambda s: s.state == 'draft').write({'state': 'commited', 'commited_user': self.env.uid, 'commited_date': datetime.now()})
        return True

    @api.multi
    def action_process(self):
        self.filtered(lambda s: s.state == 'commited').write({'state': 'progress', 'processed_user': self.env.uid, 'processed_date': datetime.now()})
        history_val = self.order_line._prepare_history_val()
        history_model = self.env['sale.request.quotation.line.history']
        for history in history_val:
            history_model.create(history_val[history])
        return True

    @api.multi
    def action_confirmed(self):
        self.action_commit()
        self.action_process()
        return True

    @api.multi
    def action_close(self):
        self.filtered(lambda s: s.state == 'progress').write({'state': 'closed', 'closed_user': self.env.uid, 'closed_date': datetime.now()})
        return True

    @api.multi
    def action_cancel(self):
        self.filtered(lambda s: s.state in ('progress', 'commited', 'draft')).write({'state': 'closed', 'cancelled_user': self.env.uid, 'cancelled_date': datetime.now()})
        return True

    @api.multi
    def action_draft(self):
        records = self.filtered(lambda s: s.state == 'cancel')
        records.write({
                'state': 'draft',
                'cancelled_user': False,
                'cancelled_date': False,
                'processed_user': False,
                'processed_date': False,
                'commited_user': False,
                'commited_date': False,
                'closed_user': False,
                'closed_date': False,
            })
        records.mapped('order_line.quotation_lines').unlink()
        return True

    @api.model
    def create(self, vals):
        if vals.get('name', 'New') == 'New':
            vals['name'] = self.env['ir.sequence'].next_by_code('sale.request.quotation') or 'New'

        result = super(SaleRequestQuotation, self).create(vals)
        return result

    @api.multi
    def _prepare_sale_order_val(self):
        val = {
            'partner_id': self.partner_id.id,
            'data_order': datetime.now(),
            'payment_term_id': self.partner_id.property_payment_term_id.id,
            'origin': self.name,
            'user_id': self.env.uid,
        }
        return val

#----------------------------------------------------------
# Request Quotation Line
#----------------------------------------------------------
class SaleRequestQuotationLine(models.Model):
    _name = "sale.request.quotation.line"
    _description = u"客户询价表"

    _rec_name = 'product_name'

    request_quotation_id = fields.Many2one('sale.request.quotation', string=u'客户询价单关联', required=True, 
        readonly=True, states={'draft': [('readonly', False)]},
        ondelete='cascade', index=True, copy=False)
    cat_no = fields.Char(string=u'产品货号', readonly=True, states={'draft': [('readonly', False)]})
    product_name = fields.Char(string=u'产品名称', required=True, readonly=True, states={'draft': [('readonly', False)]})
    comment_desc = fields.Char(string=u'产品描述', readonly=True, states={'draft': [('readonly', False)]})
    cas_code = fields.Char(string=u'化学品CAS号', readonly=True, states={'draft': [('readonly', False)]})
    product_category_name = fields.Char(string=u'产品分类', help=u'产品大类', readonly=True, states={'draft': [('readonly', False)]})
    product_brand_name = fields.Char(string=u'品牌名称', help=u'模糊匹配系统存有的品牌', readonly=True, states={'draft': [('readonly', False)]})
    package_name = fields.Char(string=u'包装', help=u'包装单位', readonly=True, states={'draft': [('readonly', False)]})
    product_uom_name = fields.Char(string=u'单位', readonly=True, states={'draft': [('readonly', False)]})
    product_uom_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), required=True, default=1.0, readonly=True, states={'draft': [('readonly', False)]})
    suggest_vendor = fields.Char(string=u'建议供应商', readonly=True, states={'draft': [('readonly', False)]})
    required_date = fields.Date(string=u'希望到货日期', readonly=True, states={'draft': [('readonly', False)]})

    commited_date = fields.Datetime(string=u'提交时间', readonly=True, index=True, 
        related='request_quotation_id.commited_date', store=True,
        help="Date on which the request quotation is commited.", copy=False)
    user_id = fields.Many2one(related='request_quotation_id.user_id', store=True, relation='res.users', index=True, readonly=True, string=u'询价员')

    state = fields.Selection([
        ('draft', u'草稿'),
        ('confirmed', u'已确认'),
        ('progress', u'处理中'),
        ('closed', u'完成'),
        ('cancel', u'已取消'),
    ],
    related='request_quotation_id.state', store=True,
    string=u'状态', readonly=True, copy=False,
    default='draft')
    quotation_lines = fields.One2many('sale.quotation', 'request_quotation_line_id', string=u'报价单', copy=False, readonly=True)
    history_ids = fields.One2many('sale.request.quotation.line.history', 'request_quotation_line_id', string=u'历史', copy=False, readonly=True)

    sale_comment = fields.Char(string=u'销售备注', readonly=True, states={'draft': [('readonly', False)]})

    @api.model
    def create(self, val):
        request_quotation_id = val.get('request_quotation_id', False)
        request_quotation = self.env['sale.request.quotation'].browse(request_quotation_id)
        if request_quotation.state != 'draft':
            raise UserError(u'询价单必须为草稿状态才能增加询价明细！')
        return super(SaleRequestQuotationLine, self).create(val)

    @api.multi
    def action_match_product(self):
        res = {}
        product_model = self.env['product.product']
        for request_id in self:
            match_product = {'perfect': product_model.browse(), 'partial': product_model.browse()}
            if request_id.cat_no:
                perfect_product = product_model.search([('cat_no', '=', request_id.cat_no), ('active', '=', True)], limit=1)
                match_product['perfect'] += perfect_product
            partial_product = product_model.search([('name', 'like', request_id.product_name), ('active', '=', True)])

            _logger.info(partial_product)
            match_product['partial'] += partial_product
            res.update({request_id: match_product})
        return res

    @api.multi
    def unlink(self):
        records = self.filtered(lambda s: s.state != 'draft')
        if records:raise UserError(u'只能删除草稿状态记录！')
        return super(SaleRequestQuotationLine, self).unlink()

    @api.multi
    def action_quotate(self):
        if self.filtered(lambda s: s.state != 'progress'):
            raise UserError(u'只有处理中状态才可以报价')
        context = self.env.context.copy()

        categ_id = self.env['product.category'].search([('name', 'like', self.product_category_name)], limit=1)
        brand_id = self.env['product.brand'].search([('name', 'like', self.product_brand_name)], limit=1)
        uom_id = self.env['product.uom'].search([('name', 'like', self.product_uom_name)], limit=1)
        suggest_vendor = self.env['res.partner'].search([('name', 'like', self.suggest_vendor)], limit=1)

        context.update({
                'default_m_cat_no': self.cat_no,
                'default_m_product_name': self.product_name,
                'default_m_comment_desc': self.comment_desc,
                'default_m_modify_cas_code': self.cas_code,
                'default_m_product_category_name': self.product_category_name,
                'default_m_product_brand_name': self.product_brand_name,
                'default_m_package_name': self.package_name,
                'default_m_product_uom_name': self.product_uom_name,
                'default_m_product_uom_qty': self.product_uom_qty,
                'default_m_suggest_vendor': self.suggest_vendor,
                'default_m_required_date': self.required_date,
                'default_m_sale_comment': self.sale_comment,

                'default_modify_cat_no': self.cat_no,
                'default_modify_product_name': self.product_name,
                'default_modify_comment_desc': self.comment_desc,
                'default_modify_modify_cas_code': self.cas_code,
                'default_modify_product_category_name': self.product_category_name,
                'default_modify_product_brand_name': self.product_brand_name,
                'default_modify_package_name': self.package_name,
                'default_modify_product_uom_name': self.product_uom_name,
                'default_modify_product_uom_qty': self.product_uom_qty,
                'default_suggest_vendor': self.suggest_vendor,
                'default_required_date': self.required_date,
                'default_request_quotation_line_id': self.id,

                'default_new_product_name': self.product_name,
                'default_new_comment_desc_cn': self.comment_desc,
                'default_new_cas_code': self.cas_code,
                'default_new_categ_id': categ_id.id,
                'default_new_brand_id': brand_id.id,
                'default_new_package_name': self.package_name,
                'default_new_uom_id': uom_id.id,
                'default_new_cat_no': self.cat_no,
                'default_new_vendor_id': suggest_vendor.id,

                'default_sale_currency': self.request_quotation_id.required_currency.id,
                'default_product_purchase_currency': self.request_quotation_id.required_currency.id,
            })
        return {
                 'name': u'采购报价',
                 'type': 'ir.actions.act_window',
                 'view_type': 'form',
                 'view_mode': 'form',
                 'res_model': 'quotate.wizard',
                 'target': 'new',
                 'context': context,
            }

    @api.multi
    def _prepare_history_val(self):
        start_val = self.read([
            'cat_no', 'product_name', 'comment_desc', 'cas_code', 'product_category_name',
            'product_brand_name', 'product_uom_qty', 'suggest_vendor', 'required_date'
            ])

        result_val = {}
        for val in start_val:
            result_val.update({val['id']: {
                    'request_quotation_line_id': val['id'],
                    'cat_no': val['cat_no'],
                    'product_name': val['product_name'],
                    'comment_desc': val['comment_desc'],
                    'cas_code': val['cas_code'],
                    'product_category_name': val['product_category_name'],
                    'product_brand_name': val['product_brand_name'],
                    'product_uom_qty': val['product_uom_qty'],
                    'suggest_vendor': val['suggest_vendor'],
                    'required_date': val['required_date'],
                }})
        return result_val

#----------------------------------------------------------
# Request Quotation Line
#----------------------------------------------------------
class SaleRequestQuotationLineHistory(models.Model):
    _name = "sale.request.quotation.line.history"
    _description = u"客户询价表历史"

    _rec_name = 'product_name'

    cat_no = fields.Char(string=u'产品货号', readonly=True)
    product_name = fields.Char(string=u'产品名称', readonly=True)
    comment_desc = fields.Char(string=u'产品描述', readonly=True)
    cas_code = fields.Char(string=u'化学品CAS号', readonly=True)
    product_category_name = fields.Char(string=u'产品分类', help=u'产品大类', readonly=True)
    product_brand_name = fields.Char(string=u'品牌名称', help=u'模糊匹配系统存有的品牌', readonly=True)
    package_name = fields.Char(string=u'包装', help=u'包装单位', readonly=True)
    product_uom_name = fields.Char(string=u'单位', readonly=True)
    product_uom_qty = fields.Float(string=u'数量', digits=dp.get_precision('Product Unit of Measure'), readonly=True, default=1.0)
    suggest_vendor = fields.Char(string=u'建议供应商')
    required_date = fields.Date(string=u'希望到货日期')
    request_quotation_line_id = fields.Many2one(
        'sale.request.quotation.line', string=u'客户询价表关联', 
        required=True, ondelete='cascade', index=True, copy=False)

#----------------------------------------------------------
# Quotation
#----------------------------------------------------------
class SaleQuotation(models.Model):
    _name = "sale.quotation"
    _description = u"报价表"

    _rec_name = 'product_id'

    request_quotation_id = fields.Many2one(relation='sale.request.quotation', string=u'客户询价单关联', related='request_quotation_line_id.request_quotation_id', 
        store=True, ondelete='cascade', index=True, copy=False)
    request_quotation_line_id = fields.Many2one(
        'sale.request.quotation.line', string=u'客户询价表关联', 
        required=True, ondelete='cascade', index=True, copy=False)

    vendor_id = fields.Many2one('res.partner', string=u'供应商', readonly=True, required=True, index=True)

    product_id = fields.Many2one("product.product", index=True, readonly=True, string=u"商品")
    default_code = fields.Char(string=u'系统编号', index=True)
    cat_no = fields.Char(string=u'产品编号', index=True)
    comment_desc_cn = fields.Char(string=u'产品中文描述', required=True)
    comment_desc_en = fields.Char(string=u'产品英文描述')
    cas_code = fields.Char(string=u'化学品CAS号', index=True)
    vendor_code = fields.Char(string=u'供应商编码', index=True, required=True)
    vendor_name = fields.Char(string=u'供应商名称', index=True, required=True)
    vendor_cat_no = fields.Char(string=u'供应商目录号', index=True, required=False)
    product_brand_name = fields.Char(string=u'产品品牌', required=True)
    package_name = fields.Char(string=u'包装', required=False)
    product_uom_name = fields.Char(string=u'单位', required=True)
    product_category_name = fields.Char(string=u'产品分类', required=True)
    product_list_price_cny = fields.Float(string=u'产品牌价(人民币)', required=True)
    product_list_price_for = fields.Float(string=u'产品牌价(FOR)')
    product_purchase_price_cny = fields.Float(string=u'采购成本(人民币)', required=True)
    product_purchase_price_for = fields.Float(string=u'采购成本(FOR)')
    product_purchase_currency = fields.Many2one('res.currency', string=u'采购币种', required=True)
    currency_exchange_rate = fields.Float(string=u'汇率', required=True)
    price_expired_date = fields.Date(string=u'价格有效期', required=True)
    vendor_lead_time = fields.Float(string=u'供应商货期', required=True)
    vendor_lead_time_desc = fields.Char(string=u'供应商货期描述')
    
    # storage_condition = fields.Char(string=u'储存条件', required=True)
    storage_condition = fields.Selection(selection=[('normal', u'常温'), ('2-8', u'2-8摄氏度'), ('0-4', u'0-4摄氏度'), ('-20', u'零下20摄氏度'), ('-80', u'零下80摄氏度')], 
        string=u'储存条件', required=True, default='normal')



    counting_weight = fields.Float(string=u'毛重')
    net_weight = fields.Float(string=u'净重')
    duty_rate = fields.Float(string=u'关税税率')

    vendor_term = fields.Selection(selection=[('DDP', 'DDP'), ('CIP', 'CIP'), ('CIF', 'CIF'), ('EXW', 'EXW'), ('FOB', 'FOB')], 
        string=u'供应商贸易方式', required=True, default='DDP')

    vendor_shipment = fields.Selection(selection=[('land', u'陆运'), ('air', u'空运'), ('ocean', u'海运')],
        string=u'供应商运输方式', required=True, default='land')


    vendor_payment = fields.Char(string=u'供应商付款条件', required=True)
    is_discontinued = fields.Boolean(string=u'是否停产', default=False)
    sale_currency = fields.Many2one('res.currency', string=u'销售币种')
    external_comments = fields.Char(string=u'外部备注')
    internal_comments = fields.Char(string=u'内部备注')
    product_manager_name = fields.Char(string=u'产品经理')
    is_stockitem = fields.Boolean(string=u'是否库存产品')
    min_order_qty = fields.Float(string=u'最小起定量')
    vendor_contact_info = fields.Char(string=u'供应商联系人', required=True)
    concat = fields.Char(string=u'联系电话', required=True)
    email = fields.Char(string=u'联系邮箱', required=False)
    product_status = fields.Char(string=u'产品状态')
    purchase_comment = fields.Char(string="采购备注")
    match_status = fields.Selection(selection=[('perfect', u'完美匹配'), ('partial', u'推荐替换')], string=u'匹配状态', default='perfect')
    # attachment_number = fields.Integer(compute='_compute_attachment_number', string=u'附件数')

    # @api.multi
    # def _compute_attachment_number(self):
    #     attachment_data = self.env['ir.attachment'].read_group([('res_model', '=', 'account.invoice.apply'), ('res_id', 'in', self.ids)], ['res_id'], ['res_id'])
    #     attachment = dict((data['res_id'], data['res_id_count']) for data in attachment_data)
    #     for inv_apply in self:
    #         inv_apply.attachment_number = attachment.get(inv_apply.id, 0)

    # @api.multi
    # def action_get_attachment_view(self):
    #     self.ensure_one()
    #     res = self.env['ir.actions.act_window'].for_xml_id('base', 'action_attachment')
    #     res['domain'] = [('res_model', '=', 'sale.quotation'), ('res_id', 'in', self.ids)]
    #     res['context'] = {'default_res_model': 'sale.quotation', 'default_res_id': self.id[0]}
    #     return res

    @api.model
    def fields_view_get(self, view_id=None, view_type='tree', toolbar=False, submenu=False):
        res = super(SaleQuotation, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if view_type == 'tree':
            remove_menu_name = []
            if self._context.get('no_quotation'):
                remove_menu_name.append('extra_quotation.create_sale_order_server_action')

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
    def _prepare_sale_order_line_val(self, sale_id):
        val = {
            'product_id': self.product_id.id,
            # 'product_uom': self.product_id.uom_id.id,
            'name': self.product_id.name,
            'order_id': sale_id.id,
        }
        return val

    @api.multi
    def _prepare_default_create_sale_wizard_val(self):
        val = {
                'product_uom_qty': self.request_quotation_line_id.product_uom_qty,
                'product_id': self.product_id.id,
                'default_code': self.product_id.default_code,
                'cat_no': self.product_id.cat_no,
                'comment_desc_cn': self.product_id.comment_desc_cn,
                'product_list_price_cny': self.product_list_price_cny,
                'product_purchase_price_cny': self.product_purchase_price_cny,
                'quotation_id': self.id,
                'price_unit': self.product_list_price_cny,
                'vendor_lead_time': self.vendor_lead_time,

                'product_uom': self.product_id.uom_id.id,
                'tax_id': self.product_id.taxes_id and self.product_id.taxes_id[0].id or False,
            }
        return val

    @api.multi
    def create_sale_order_server_action(self):

        request_quotation_id = self.mapped('request_quotation_id')
        if len(request_quotation_id) != 1:
            raise UserError(u'只能同时对一张询价单进行报价！')

        request_quotation_line_id = self.mapped('request_quotation_line_id')

        for s in request_quotation_line_id:
            if len(self.filtered(lambda f: f.request_quotation_line_id == s)) != 1:
                raise UserError(u'不能同时对同样的客户询价进行报价！%s'%s.product_name)

        ctx = self.env.context.copy()

        default_lines = []
        for line in self:
            val = line._prepare_default_create_sale_wizard_val()
            default_lines.append((0, 0, val))

        ctx.update({'default_quotation_create_sale_lines': default_lines})

        return {
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'target': 'new',
            'res_model': 'quotation.create.sale.wizard',
            'context': ctx,
        }

