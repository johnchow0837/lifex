# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Res Currency
#----------------------------------------------------------
class ResCurrency(models.Model):
    _inherit = "res.currency"
    _description = u"货币"

    manu_rate = fields.Float(string=u'汇率', requierd=True, default=0)


class ProductCategory(models.Model):
    _inherit = 'product.category'
    
    property_valuation = fields.Selection(default='real_time')
    property_cost_method = fields.Selection(default='real')


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    property_valuation = fields.Selection(default='real_time')
    property_cost_method = fields.Selection(default='real')

    @api.one
    @api.depends('property_valuation', 'categ_id.property_valuation')
    def _compute_valuation_type(self):
        self.valuation = 'real_time'

    @api.one
    @api.depends('property_cost_method', 'categ_id.property_cost_method')
    def _compute_cost_method(self):
        self.cost_method = 'real'