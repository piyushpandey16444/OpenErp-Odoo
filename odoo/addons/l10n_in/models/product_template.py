# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import models, fields,api
from odoo.exceptions import AccessError, UserError


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    l10n_in_hsn_code = fields.Char(string="HSN/SAC Code", help="Harmonized System Nomenclature/Services Accounting Code")

    # ravi start at 7/2/2020 for validation of hsn code
    @api.model
    def create(self, vals):
        res = super(ProductTemplate, self).create(vals)
        if res.l10n_in_hsn_code:
            if len(res.l10n_in_hsn_code) < 2 or len(res.l10n_in_hsn_code) > 8 or not(res.l10n_in_hsn_code.isnumeric()):
                raise UserError("HSN Code can't be smaller then 2 digits and more than 8 digits and should be a number")
        return res

    @api.multi
    def write(self, vals):
        res = super(ProductTemplate, self).write(vals)
        if self.l10n_in_hsn_code:
            if len(self.l10n_in_hsn_code) < 2 or len(self.l10n_in_hsn_code) > 8 or not(self.l10n_in_hsn_code.isnumeric()):
                raise UserError("HSN Code can't be smaller then 2 digits and more than 8 digits")
        return res
    # ravi end
