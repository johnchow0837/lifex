# -*- coding: utf-8 -*-

from odoo import api, fields, models, _
from odoo.exceptions import UserError
import odoo.addons.decimal_precision as dp

from lxml import etree
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


#----------------------------------------------------------
# Procurement Set Partner Wizard
#----------------------------------------------------------
class ProcurementSetPartnerWizard(models.TransientModel):
    _name = 'procurement.set.partner.wizard'
    _description = u'采购需求设置供应商'

    supplier_partner_id = fields.Many2one('res.partner', string=u'供应商', required=True)
    supplier_delay = fields.Float(string=u'供应商货期', default=0)

    @api.model
    def fields_view_get(self, view_id=None, view_type='form', toolbar=False, submenu=False):
        res = super(ProcurementSetPartnerWizard, self).fields_view_get(
            view_id=view_id, view_type=view_type, toolbar=toolbar, submenu=submenu)
        if self._context.get('supplier_partner_id'):
            doc = etree.XML(res['arch'])
            for node in doc.xpath("//field[@name='supplier_partner_id']"):
                node.set('domain', "[('id', '=', %s)]"%self._context.get('supplier_partner_id', []))

            res['arch'] = etree.tostring(doc)
        return res

    @api.multi
    def action_set_partner(self):
    	procurement_ids = self.env['procurement.order'].browse(self.env.context.get('active_ids', []))

    	if any(self.supplier_partner_id.id not in s.product_id.seller_ids.mapped('name').ids for s in procurement_ids):
    		raise UserError(u'所选择的供应商没有被需求设置')

        val = {'supplier_partner_id': self.supplier_partner_id.id}

        if self.supplier_delay > 0:
            val.update({'supplier_delay': self.supplier_delay})

        _logger.info(val)

    	procurement_ids.write(val)

        procurement_ids.with_context(manu_set=True).set_sup_info()

    	return True

