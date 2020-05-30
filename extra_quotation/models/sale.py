# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)

#----------------------------------------------------------
# Sale Order Line
#----------------------------------------------------------
class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'
    _description = u"销售单明细"

    external_comments = fields.Char(string=u'外部备注')

