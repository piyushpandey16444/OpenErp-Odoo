from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError
import re

class ProductUoM(models.Model):
    _inherit = 'product.uom'

    @api.constrains('name')
    def name_validation(self):
        print("heelllllomaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaan")
        regex = re.compile('[ ()}{,+-=/&<>*~?;]')
        string = self.name
        if string:
            if regex.search(string) != None:
                val = regex.search(string).group()
                if val == ' ':
                    val = 'whitespace'
                raise ValidationError(_("UOM don't accept %s") % (val))

            check_available = self.check_same_name(string)

            if check_available:
                print("iiiiii mmmmmmmmmmmmmm innnnnnnnnnnnn")
                raise ValidationError(_("Uom with similar name already exists"))

    def check_same_name(self,string):
        print("")
        alp = ""
        white = " "
        for char in string:
            if char.isalnum() or char == white:
                alp += char
        print("alpalpalpalpalpalp", alp)
        check_available = self.env['product.uom'].search([('name', '=', alp), ('id', '!=', self.id)])
        print("check_availablecheck_availablecheck_available", check_available)
        return check_available

class ResConfigSettings(models.TransientModel):
    _inherit = 'res.config.settings'

    tally_transfer_type=fields.Selection([
        ('account_wise','Value Wise'),
        ('product_wise','Product Wise'),
    ],string='Tally Transfer Type')

    def set_values(self):
        super(ResConfigSettings, self).set_values()
        set_param = self.env['ir.config_parameter'].sudo().set_param
        set_param('tally_validations.tally_transfer_type', self.tally_transfer_type)

    @api.model
    def get_values(self):
        res = super(ResConfigSettings, self).get_values()
        get_param = self.env['ir.config_parameter'].sudo().get_param
        res.update(
            tally_transfer_type=get_param('tally_validations.tally_transfer_type'),
        )
        return res