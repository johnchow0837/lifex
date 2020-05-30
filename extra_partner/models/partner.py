# -*- coding: utf-8 -*-

import random, string, logging, json

from odoo import api, fields, models, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Res Partner
#----------------------------------------------------------
class ResPartner(models.Model):
    _inherit = "res.partner"

    # Supplier Info
    supplier_name_2 = fields.Char(string=u'供应商名称2', index=True)
    supplier_guid = fields.Char(string=u'供应商编码', index=True, required=True, copy=False)
    supplier_type = fields.Selection(selection=[('consignment', u'代理商')], string=u'供应商类别', default="consignment") # TODO
    supplier_cat_no = fields.Char(string=u'供应商目录号', index=True)
    search_condition = fields.Char(string=u'搜索条件')
    supplier_taxpayer_number = fields.Char(string=u'供应商纳税人登记号', index=True)
    business_scope = fields.Char(string=u'业务范围')
    payment_method = fields.Char(string=u'付款方式')
    payment_currency = fields.Many2one('res.currency', string=u'付款币种')

    # Customer_Info
    customer_guid = fields.Char(string=u'客户编码', index=True, required=True, copy=False)
    customer_invoice_type = fields.Selection(selection=[('common_vat', u'普票'), ('vat', u'增票')], string=u'客户开票类型', default='common_vat')
    customer_taxpayer_number = fields.Char(string=u'客户纳税人识别号', index=True)

    customer_invoice_title = fields.Char(string=u'发票抬头', index=True)
    customer_invoice_bank = fields.Char(string=u'发票银行', index=True)
    customer_invoice_account = fields.Char(string=u'发票银行账号', index=True)
    customer_invoice_address = fields.Char(string=u'发票注册地址', index=True)
    customer_invoice_phone = fields.Char(string=u'发票注册电话', index=True)

    # Share_Info
    company_title_name = fields.Char(string=u'公司抬头', index=True)

    _sql_constraints = [
        ('supplier_guid_uniq', 'unique (supplier_guid)', u'供应商编码必须唯一 !'),
        ('customer_guid_uniq', 'unique (customer_guid)', u'客户编码必须唯一 !'),
        ('customer_taxpayer_number_uniq', 'unique (customer_taxpayer_number)', u'客户税号必须唯一 !'),
    ]

    @api.multi
    def _fields_sync(self, values):
        """ Sync commercial fields and address fields from company and to children after create/update,
        just as if those were all modeled as fields.related to the parent """
        # 1. From UPSTREAM: sync from parent
        if values.get('parent_id') or values.get('type', 'contact'):
            # 1a. Commercial fields: sync if parent changed
            if values.get('parent_id'):
                self._commercial_sync_from_company()
            # 1b. Address fields: sync if parent or use_parent changed *and* both are now set 
            # if self.parent_id and self.type == 'contact':
            #     onchange_vals = self.onchange_parent_id().get('value', {})
            #     self.update_address(onchange_vals)

        # 2. To DOWNSTREAM: sync children
        if self.child_ids:
            # 2a. Commercial Fields: sync if commercial entity
            if self.commercial_partner_id == self:
                commercial_fields = self._commercial_fields()
                if any(field in values for field in commercial_fields):
                    self._commercial_sync_to_children()
            for child in self.child_ids.filtered(lambda c: not c.is_company):
                if child.commercial_partner_id != self.commercial_partner_id :
                    self._commercial_sync_to_children()
                    break
            # 2b. Address fields: sync if address changed
            # address_fields = self._address_fields()
            # if any(field in values for field in address_fields):
            #     contacts = self.child_ids.filtered(lambda c: c.type == 'contact')
            #     contacts.update_address(values)

    @api.onchange('name')
    def extra_onchange_name(self):
        if self.name:
            self.customer_invoice_title = self.name
        else:
            self.customer_invoice_title = ''

    @api.model
    def get_random_code(self):
        first_int = str(random.randint(1, 9))
        upperletters = string.ascii_uppercase.replace('O', '').replace('I', '')
        med_two_letters = ''.join([random.choice(upperletters) for x in range(0, 2)])
        last_four_int = str(random.randint(0, 9999))
        return first_int + med_two_letters + last_four_int

    @api.model
    def create(self, val):
        if not val.get('customer_guid', ''):
            if val.get('customer', False):
                val['customer_guid'] = self.env['ir.sequence'].next_by_code('partner.customer')
            else:
                val['customer_guid'] = self.env['ir.sequence'].next_by_code('extra.partner')

        if not val.get('supplier_guid', ''):
            if val.get('supplier', False):
                val['supplier_guid'] = self.env['ir.sequence'].next_by_code('partner.supplier')
            else:
                val['supplier_guid'] = self.env['ir.sequence'].next_by_code('extra.partner')

        return super(ResPartner, self).create(val)

    @api.model
    def sync_user(self, val):
        _logger.info('sync_user===========%s', val)
        '''用户创建/编辑接口'''
        if isinstance(val, str):
            val = json.loads(val)

        customer_guid = val.get('user_id', '')
        if not customer_guid:
            _logger.info(u'%s:用户ID不能为空', customer_guid)
            return json.dumps({'result': '1', 'message': u'用户ID不能为空'})
        customer_name = val.get('user_name', '')
        login_name = val.get('login_name', '')
        user_email = val.get('user_email', '')
        user_phone = val.get('user_phone', '')


        if not customer_name and not login_name and not user_email and not user_phone:
            _logger.info(u'%s:用户名称、登录名、邮箱、电话必填一项', customer_guid)
            return json.dumps({'result': '1', 'message': u'用户名称、登录名、邮箱、电话必填一项'})

        parent_id = False
        if 'user_company_id' in val:
            parent_guid = val.get('user_company_id', 'nullbysys')
            parent_id = self.search([('customer_guid', '=', parent_guid), ('customer', '=', True), ('is_company', '=', True)], limit=1)
            parent_id = parent_id.id

        partner_id = self.search([('customer_guid', '=', customer_guid), ('customer', '=', True), ('is_company', '=', False)], limit=1)

        try:
            res = {}
            res.update({
                    'is_company': False,
                    'name': customer_name or login_name or user_phone or user_email,
                    'ref': login_name,
                    'customer_guid': customer_guid,
                    'email': user_email,
                    'phone': user_phone,
                    'parent_id': parent_id,
                    'type': False
                })
            if not partner_id:
                self.create(res)
            else:
                res.pop('customer_guid')
                partner_id.write(res)
            _logger.info(u'%s:用户同步成功', customer_guid)
            return json.dumps({'result': '0', 'message': ''})
        except Exception as e:
            self.env.cr.rollback()
            _logger.exception(e)
            return json.dumps({'result': '1', 'message': u'用户%s创建/编辑失败:%s'%(customer_name, e.message, )})

    @api.model
    def sync_company(self, val):
        _logger.info('sync_company===========%s', val)
        '''公司创建/编辑接口'''
        if isinstance(val, str):
            val = json.loads(val)

        company_id = val.get('company_id', '')
        if not company_id:
            _logger.info(u'%s:公司ID不能为空', company_id)
            return json.dumps({'result': '1', 'message': u'公司ID不能为空'})
        company_name = val.get('company_name', '')
        if not company_name:
            _logger.info(u'%s:公司名称不能为空', company_name)
            return json.dumps({'result': '1', 'message': u'公司名称不能为空'})

        parent_id = False
        if 'parent_id' in val:
            parent_guid = val.get('parent_id', 'nullbysys')
            parent_id = self.search([('customer_guid', '=', parent_guid), ('customer', '=', True), ('is_company', '=', True)], limit=1)
            parent_id = parent_id.id

        partner_id = self.search([('customer_guid', '=', company_id), ('customer', '=', True), ('is_company', '=', True)], limit=1)

        try:
            res = {}
            res.update({
                    'is_company': True,
                    'name': company_name,
                    'customer_guid': company_id,
                    'customer': True,
                    'parent_id': parent_id,
                    'type': False
                })
            if not partner_id:
                self.create(res)
            else:
                res.pop('customer_guid')
                partner_id.write(res)
            _logger.info(u'%s:公司同步成功', company_id)
            return json.dumps({'result': '0', 'message': ''})
        except Exception as e:
            self.env.cr.rollback()
            _logger.exception(e)
            return json.dumps({'result': '1', 'message': u'用户公司%s创建/编辑失败:%s'%(company_name, e.message, )})


#----------------------------------------------------------
# Res Bank
#----------------------------------------------------------
class ResBank(models.Model):
    _inherit = 'res.bank'

    bank_code = fields.Char(string=u'银行代码', help=u"12位数字标准码", required=True)