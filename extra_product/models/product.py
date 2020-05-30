# -*- coding: utf-8 -*-

import re
import random, string
import xlrd
import base64
from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.osv import expression


#----------------------------------------------------------
# Product Category
#----------------------------------------------------------
class ProductCategory(models.Model):
    _inherit = "product.category"
    _description = u"产品分类"

    description = fields.Char(string=u'描述')
    guid = fields.Char(string=u'编码')
    category_tax_code = fields.Char(string=u'税收分类编码')
    active = fields.Boolean(string=u'有效', default=True)

    _sql_constraints = [
        ('product_category_guid_uniq', 'unique (guid)', u'产品分类guid必须唯一 !')
    ]

    @api.multi
    def sync_categ_update(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for category in self:
            data = {
                'sync_id': str(category.id),
                'parent_id': str(category.parent_id.id or ''),
                'name_zh': category.name or '',
                # 'name_en': category.name_en, # TODO API
                'description': category.description or '',
                # 'key_words': '', # TODO API
                # 'seq': '' # TODO API
                'status': '1' if category.active else '0',
            }
            api_val = {
                'api_type': 'categ_update',
                'http_method': 'post',
                'data_model': 'product.category',
                'key_value': category.id,
                'data': data,
                'url': '?route=rest/product/category/update',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

    @api.multi
    def sync_categ_update_other_odoo(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for category in self:
            data = category.copy_data()[0]
            data.update({'guid': str(category.id)})
            api_val = {
                'api_type': 'categ_update_odoo',
                'http_method': 'post',
                'data_model': 'product.category',
                'key_value': category.id,
                'data': data,
                'url': 'wy',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return api_ids

    @api.model
    def categ_update_odoo(self, val):
        category_guid = val.get('guid', '')
        if not category_guid:
            return {'result': '1', 'message': u'分类guid不能为空'}
        category_id = self.with_context(active_test=True).search([('guid', '=', category_guid)], limit=1)

        if val.get('parent_id'):
            parent_id = self.env['product.category'].search([('guid', '=', val.get('parent_id'))], limit=1)
            if not parent_id:
                return {'result': '1', 'message': u'找不到对应的父级分类:%s'%val.get('parent_id')}
            val.update({'parent_id': parent_id.id})
        if category_id:
            category_id.write(val)
        else:
            self.create(val)
        return {'result': '0', 'message': u'成功'}

    @api.multi
    def sync_categ_update_other_odoo_batch(self):
        a = [self]
        parent_id = self.mapped('parent_id')
        while parent_id:
            a.append(parent_id)
            parent_id = parent_id.mapped('parent_id')
        a.reverse()
        categ_ids = self.browse()
        for categ_id in a:
            categ_ids |= categ_id
        api_ids = categ_ids.sync_categ_update_other_odoo()
        return api_ids

    @api.multi
    def action_check_data(self):
        child_ids = self.mapped('child_id')
        if child_ids:
            raise UserError(u'所选分类有子分类，无法操作')

        product_ids = self.env['product.product'].search([('categ_id', 'in', self.ids)], limit=1)
        if product_ids:
            raise UserError(u'所选分类有产品，无法操作')
        return True

    @api.multi
    def action_delete(self):
        self.action_check_data()
        self.write({'active': False})
        self.sync_categ_delete()
        return True

    @api.multi
    def sync_categ_delete(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for category in self:
            data = {
                'sync_id': str(category.id),
            }
            api_val = {
                'api_type': 'categ_delete',
                'http_method': 'get',
                'data_model': 'product.category',
                'key_value': category.id,
                'data': data,
                'url': '?route=rest/product/category/delete',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

#----------------------------------------------------------
# Product Brand
#----------------------------------------------------------
class ProductBrand(models.Model):
    _name = "product.brand"
    _description = u"产品品牌"

    name = fields.Char(string=u'品牌名称', required=True)
    name_en = fields.Char(string=u'英文名称')
    active = fields.Boolean(string=u'有效', default=True)
    description = fields.Text(string=u'品牌描述')
    guid = fields.Char(string=u'编码')

    _sql_constraints = [
        ('product_brand_guid_uniq', 'unique (guid)', u'产品品牌guid必须唯一 !')
    ]

    @api.multi
    def sync_brand_update(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for brand in self:
            data = {
                'sync_id': str(brand.id),
                'brand_zh': brand.name or '',
                'brand_en': brand.name_en or '',
                'brand_description': brand.description or '',
                'status': '1' if brand.active else '0',
                'core_flag': '0', # TODO API
                # 'image_path': '', # TODO API
            }
            api_val = {
                'api_type': 'brand_update',
                'http_method': 'post',
                'data_model': 'product.brand',
                'key_value': brand.id,
                'data': data,
                'url': '?route=rest/product/brand/update',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

    @api.multi
    def sync_brand_update_other_odoo(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for brand in self:
            data = brand.copy_data()[0]
            data.update({'guid': str(brand.id)})
            api_val = {
                'api_type': 'brand_update_odoo',
                'http_method': 'post',
                'data_model': 'product.brand',
                'key_value': brand.id,
                'data': data,
                'url': 'wy',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return api_ids

    @api.model
    def brand_update_odoo(self, val):
        brand_guid = val.get('guid', '')
        if not brand_guid:
            return {'result': '1', 'message': u'品牌guid不能为空'}
        brand_id = self.with_context(active_test=True).search([('guid', '=', brand_guid)], limit=1)
        if brand_id:
            brand_id.write(val)
        else:
            self.create(val)
        return {'result': '0', 'message': u'成功'}

    @api.multi
    def action_check_data(self):
        product_ids = self.env['product.product'].search([('brand_id', 'in', self.ids)], limit=1)
        if product_ids:
            raise UserError(u'所选品牌有产品，无法操作')
        return True

    @api.multi
    def action_delete(self):
        self.action_check_data()
        self.write({'active': False})
        self.sync_brand_delete()
        return True

    @api.multi
    def sync_brand_delete(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for brand in self:
            data = {
                'sync_id': str(brand.id),
            }
            api_val = {
                'api_type': 'brand_delete',
                'http_method': 'get',
                'data_model': 'product.brand',
                'key_value': brand.id,
                'data': data,
                'url': '?route=rest/product/brand/delete',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

#----------------------------------------------------------
# Products Template
#----------------------------------------------------------
class ProductTemplate(models.Model):
    _inherit = "product.template"

    cas_code = fields.Char(string=u'化学品CAS号')
    brand_id = fields.Many2one('product.brand', string=u'产品品牌', required=False)
    package_name = fields.Char(string=u'包装', required=False)
    cat_no = fields.Char(string=u'原厂货号')
    comment_desc_cn = fields.Char(string=u'产品中文描述', required=False)
    comment_desc_en = fields.Char(string=u'产品英文描述')
    storage_condition = fields.Selection(selection=[('normal', u'常温'), ('2-8', u'2-8摄氏度'), ('0-4', u'0-4摄氏度'), ('-20', u'零下20摄氏度'), ('-80', u'零下80摄氏度')], 
        string=u'储存条件', required=False, default='normal')
    counting_weight = fields.Float(string=u'毛重')
    net_weight = fields.Float(string=u'净重')

    is_discontinued = fields.Boolean(string=u'是否停产', default=False)
    on_website = fields.Boolean(string=u'是否上架', default=True, readonly=True)
    product_manager_name = fields.Char(string=u"产品经理", default=lambda s: s.env.user.name, readonly=True)
    is_stockitem = fields.Boolean(string=u"是否库存产品")
    min_orderqty = fields.Float(string=u"最小库存量")
    product_status = fields.Char(string=u"产品状态", required=False)
    product_model = fields.Char(string=u"规格型号")
    duty_rate = fields.Float(string=u'关税税率', default=0)
    pricelist_currency_ids = fields.One2many('product.pricelist.currency', 'product_tmpl_id', string=u'产品货币价格表', copy=True)
    costlist_currency_ids = fields.One2many('product.costlist.currency', 'product_tmpl_id', string=u'产品货币成本表', copy=True)

    product_tag = fields.Char(string=u'产品标签', index=True)

    _sql_constraints = [
        ('product_brand_catno_uniq', 'unique (brand_id,cat_no)', u'每种商品产品和原厂货号组合不能重复 !')
    ]

    @api.multi
    def sync_product_update(self):
        self.mapped('product_variant_id').sync_product_update()
        return True

    @api.multi
    def action_delete(self):
        self.mapped('product_variant_id').action_delete()
        return True

    @api.multi
    def sync_product_update_other_odoo(self):
        self.mapped('product_variant_id').sync_product_update_other_odoo()
        return True

    # @api.multi
    # def action_delete_other_odoo(self):
    #     self.mapped('product_variant_id').action_delete_other_odoo()
    #     return True

#----------------------------------------------------------
# Products Product
#----------------------------------------------------------
class ProductProduct(models.Model):
    _inherit = "product.product"

    _sql_constraints = [
        ('default_code_uniq', 'unique (default_code)', u'产品编码必须唯一 !'),
        ('barcode_uniq', 'unique (barcode)', u'产品条码必须唯一 !')
    ]

    @api.model
    def get_random_code(self):
        first_int = str(random.randint(1, 9))
        upperletters = string.ascii_uppercase.replace('O', '').replace('I', '')
        med_two_letters = ''.join([random.choice(upperletters) for x in range(0, 2)])
        last_four_int = '%04d'%random.randint(0, 9999)
        return first_int + med_two_letters + last_four_int

    @api.model
    def create(self, val):
        if not val.get('default_code', ''):
            default_code = self.get_random_code()
            duplicated = True
            while duplicated:
                product_id = self.search([('default_code', '=', default_code)], limit=1)
                if product_id:
                    default_code = self.get_random_code()
                else:
                    duplicated = False
            val.update({'default_code': default_code})
        return super(ProductProduct, self).create(val)
    
    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        if not args:
            args = []
        if name:
            positive_operators = ['=', 'ilike', '=ilike', 'like', '=like']
            products = self.env['product.product']
            if operator in positive_operators:
                products = self.search(['|', ('cat_no', '=', name), ('default_code', '=', name)] + args, limit=limit)
                if not products:
                    products = self.search([('barcode', '=', name)] + args, limit=limit)
            if not products and operator not in expression.NEGATIVE_TERM_OPERATORS:
                # Do not merge the 2 next lines into one single search, SQL search performance would be abysmal
                # on a database with thousands of matching products, due to the huge merge+unique needed for the
                # OR operator (and given the fact that the 'name' lookup results come from the ir.translation table
                # Performing a quick memory merge of ids in Python will give much better performance
                products = self.search(args + ['|', ('cat_no', operator, name), ('default_code', operator, name)], limit=limit)
                if not limit or len(products) < limit:
                    # we may underrun the limit because of dupes in the results, that's fine
                    limit2 = (limit - len(products)) if limit else False
                    products += self.search(args + [('name', operator, name), ('id', 'not in', products.ids)], limit=limit2)
            elif not products and operator in expression.NEGATIVE_TERM_OPERATORS:
                domain = expression.OR([
                    ['&', ('default_code', operator, name), ('name', operator, name)],
                    ['&', ('default_code', '=', False), ('name', operator, name)],
                    ['&', ('cat_no', operator, name), ('name', operator, name)],
                    ['&', ('cat_no', '=', False), ('name', operator, name)],
                ])
                domain = expression.AND([args, domain])
                products = self.search(domain, limit=limit)
            if not products and operator in positive_operators:
                ptrn = re.compile('(\[(.*?)\])')
                res = ptrn.search(name)
                if res:
                    products = self.search(['|', ('cat_no', '=', res.group(2)), ('default_code', '=', res.group(2))] + args, limit=limit)
            # still no results, partner in context: search on supplier info as last hope to find something
            if not products and self._context.get('partner_id'):
                suppliers = self.env['product.supplierinfo'].search([
                    ('name', '=', self._context.get('partner_id')),
                    '|',
                    ('product_code', operator, name),
                    ('product_name', operator, name)])
                if suppliers:
                    products = self.search([('product_tmpl_id.seller_ids', 'in', suppliers.ids)], limit=limit)
        else:
            products = self.search(args, limit=limit)
        return products.name_get()

    @api.multi
    def sync_product_update(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for product in self:
            data = {
                'sku_code': product.default_code,
                'brand_id': str(product.brand_id.id),
                'category_ids': str(product.categ_id.id or ''),
                'name_zh': product.comment_desc_cn,
                'name_en': product.comment_desc_en,
                'mfg_model': product.cat_no,
                'sales_uom': product.uom_id.name,
                'delivery_time': str(product.sale_delay), # API TBD
                'sales_moq': '1', # API TBD
            }
            api_val = {
                'api_type': 'product_update',
                'http_method': 'post',
                'data_model': 'product.product',
                'key_value': product.id,
                'data': data,
                'url': '?route=rest/product/product/update',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

    @api.multi
    def sync_product_update_other_odoo(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        brand_ids = self.mapped('brand_id').with_context(force_send=False)
        api_ids |= brand_ids.sync_brand_update_other_odoo()
        category_ids = self.mapped('categ_id').with_context(force_send=False)
        api_ids |= category_ids.sync_categ_update_other_odoo_batch()
        for product in self:
            data = product.copy_data()[0]
            data.update({'default_code': product.default_code})
            api_val = {
                'api_type': 'product_update_odoo',
                'http_method': 'post',
                'data_model': 'product.product',
                'key_value': product.id,
                'data': data,
                'url': 'wy',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

    @api.model
    def product_update_odoo(self, val):
        self = self.with_context(active_test=True)
        default_code = val.get('default_code', '')
        if not default_code:
            return {'result': '1', 'message': u'SKU号不能为空'}
        product_id = self.search([('default_code', '=', default_code)], limit=1)
        category_id = self.env['product.category'].search([('guid', '=', val.get('categ_id'))], limit=1)
        if not category_id or not val.get('categ_id'):
            return {'result': '1', 'message': u'产品分类参数错误，或者找不到对应的产品分类:%s'%val.get('categ_id')}
        brand_id = self.env['product.brand'].search([('guid', '=', val.get('brand_id'))], limit=1)
        if not brand_id or not val.get('brand_id'):
            return {'result': '1', 'message': u'产品品牌参数错误，或者找不到对应的产品品牌:%s'%val.get('brand_id')}
        val.update({'categ_id': category_id.id, 'brand_id': brand_id.id})
        if product_id:
            for i in val:
                if 'tax' not in i and isinstance(val[i], list):
                    val[i] = False
            product_id.write(val)
        else:
            self.create(val)
        return {'result': '0', 'message': u'成功'}

    @api.model
    def product_delete_odoo(self):
        default_code = val.get('default_code', '')
        if not default_code:
            return {'result': '1', 'message': u'SKU号不能为空'}
        product_id = self.with_context(active_test=True).search([('default_code', '=', default_code)], limit=1)
        if product_id:
            product_id.write({'active': False, 'on_website': False})
        else:
            return {'result': '1', 'message': u'找不到SKU【%s】'% default_code}
        return {'result': '0', 'message': u'成功'}

    @api.multi
    def sync_product_delete_other_odoo(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for product in self:
            data = {
                'default_code': product.default_code,
            }
            api_val = {
                'api_type': 'product_delete_odoo',
                'http_method': 'get',
                'data_model': 'product.product',
                'key_value': product.id,
                'data': data,
                'url': 'wy',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

    @api.multi
    def action_delete(self):
        self.write({'active': False, 'on_website': False})
        self.sync_product_delete()
        self.sync_product_delete_other_odoo()
        return True

    @api.multi
    def sync_product_delete(self):
        api_model = self.env['extra.api']
        api_ids = api_model.browse()
        for product in self:
            data = {
                'sku_code': product.default_code,
            }
            api_val = {
                'api_type': 'product_delete',
                'http_method': 'get',
                'data_model': 'product.product',
                'key_value': product.id,
                'data': data,
                'url': '?route=rest/product/product/updateStatus',
            }
            api_ids |= api_model.create(api_val)
        if self.env.context.get('force_send', False):
            for api_id in api_ids:
                api_id.action_send()
        return True

#----------------------------------------------------------
# Products Supplier Info
#----------------------------------------------------------
class ProductSupplierInfo(models.Model):
    _inherit = 'product.supplierinfo'

    vendor_term = fields.Selection(selection=[('DDP', 'DDP'), ('CIP', 'CIP'), ('CIF', 'CIF'), ('EXW', 'EXW'), ('FOB', 'FOB')], 
        string=u'供应商贸易方式', required=True)

    vendor_shipment = fields.Selection(selection=[('land', u'陆运'), ('air', u'空运'), ('ocean', u'海运')],
        string=u'供应商运输方式', required=True, default='land')

    for_price = fields.Float(string=u'外币价格', default=0)

    @api.model
    def create(self, val):
        if val.get('product_tmpl_id', False) and not val.get('product_id', False):
            product_id = self.env['product.product'].search([('product_tmpl_id', '=', val.get('product_tmpl_id', False))], limit=1)
            val.update({'product_id': product_id.id})
        elif not val.get('product_tmpl_id', False) and val.get('product_id', False):
            product_id = self.env['product.product'].search([('id', '=', val.get('product_id', False))], limit=1)
            val.update({'product_tmpl_id': product_id.product_tmpl_id.id})
        return super(ProductSupplierInfo, self).create(val)

#----------------------------------------------------------
# Products PriceList
#----------------------------------------------------------
class ProductPriceListCurrency(models.Model):
    _name = 'product.pricelist.currency'
    _description = u"产品外币价格表"

    product_tmpl_id = fields.Many2one('product.template', string=u'产品模板', ondelete='cascade', index=True, copy=False)
    product_id = fields.Many2one('product.product', string=u'产品', ondelete='cascade', index=True, copy=False)
    currency_id = fields.Many2one('res.currency', string=u'币种', required=True, ondelete='cascade')
    price = fields.Float(string=u'价格', default=0)

    _sql_constraints = [
        ('product_currency_uniq', 'unique (product_id,currency_id)', u'每种商品价格表币种不能重复 !')
    ]

    @api.model
    def create(self, val):
        if val.get('product_tmpl_id', False) and not val.get('product_id', False):
            product_id = self.env['product.template'].browse(val.get('product_tmpl_id', False))
            val.update({'product_id': product_id.product_variant_id.id})
        elif not val.get('product_tmpl_id', False) and val.get('product_id', False):

            product_id = self.env['product.product'].browse(val.get('product_id', False))
            val.update({'product_tmpl_id': product_id.product_tmpl_id.id})
        return super(ProductPriceListCurrency, self).create(val)

#----------------------------------------------------------
# Products CostList
#----------------------------------------------------------
class ProductCostListCurrency(models.Model):
    _name = 'product.costlist.currency'
    _description = u"产品外币成本表"

    product_tmpl_id = fields.Many2one('product.template', string=u'产品模板', ondelete='cascade', index=True, copy=False)
    product_id = fields.Many2one('product.product', string=u'产品', ondelete='cascade', index=True, copy=False)
    currency_id = fields.Many2one('res.currency', string=u'币种', required=True, ondelete='cascade')
    price = fields.Float(string=u'成本', default=0)

    _sql_constraints = [
        ('product_currency_uniq', 'unique (product_id,currency_id)', u'每种商品成本表币种不能重复 !')
    ]

    @api.model
    def create(self, val):
        if val.get('product_tmpl_id', False) and not val.get('product_id', False):
            product_id = self.env['product.template'].browse(val.get('product_tmpl_id', False))
            val.update({'product_id': product_id.product_variant_id.id})
        elif not val.get('product_tmpl_id', False) and val.get('product_id', False):
            product_id = self.env['product.product'].browse(val.get('product_id', False))
            val.update({'product_tmpl_id': product_id.product_tmpl_id.id})
        return super(ProductCostListCurrency, self).create(val)

class ProductSyncBatch(models.TransientModel):
    _name = 'product.sync.batch'

    import_binary = fields.Binary(string=u'同步SKU文件', help='Excel格式', required=True)

    @api.multi
    def action_sync(self):
        excel = xlrd.open_workbook(file_contents=base64.decodestring(self.import_binary))
        sheet = excel.sheet_by_index(0)
        cols_title = self.get_title_field_dict(sheet)
        nrows = sheet.nrows
        product_model = self.env['product.product']
        skus = []
        for row in range(1, nrows):
            sku = sheet.cell(row, cols_title.get('sku', 0)).value
            skus.append(sku)
        skus = list(set(skus))
        product_ids = product_model.search([('default_code', 'in', skus)])
        if len(product_ids) != len(skus):
            codes = product_ids.mapped('default_code')
            no_skus = list(set(skus) - set(codes))
            raise UserError(u'下列SKU不存在:%s'%','.join(no_skus))
        if self.env.context.get('other_odoo', False):
            product_ids.sync_product_update_other_odoo()
        else:
            product_ids.sync_product_update()

        return True

    @api.model
    def get_title_field_dict(self, sheet):
        sh = sheet
        ncols = sh.ncols

        cols = {}
        for ncol in range(0, ncols):
            cell_col = sh.cell(0, ncol).value
            cols.update({cell_col: ncol})
        return cols