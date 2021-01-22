# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import fields, models, api, _
from odoo.addons.base.res.res_partner import WARNING_MESSAGE, WARNING_HELP
from odoo.exceptions import ValidationError
import re


class ResPartner(models.Model):
    _inherit = 'res.partner'

    sale_order_count = fields.Integer(compute='_compute_sale_order_count', string='# of Sales Order')
    sale_order_ids = fields.One2many('sale.order', 'partner_id', 'Sales Order')
    sale_warn = fields.Selection(WARNING_MESSAGE, 'Sales Order', default='no-message', help=WARNING_HELP, required=True)
    sale_warn_msg = fields.Text('Message for Sales Order')
    # new sale product lines
    customer_product_pricelist_lines = fields.One2many('product.customer.info', 'name', 'Customer Items')
    vendor_product_pricelist_lines = fields.One2many('product.supplierinfo', 'name', 'Vendor Items')

    def _compute_sale_order_count(self):
        # retrieve all children partners and prefetch 'parent_id' on them
        all_partners = self.search([('id', 'child_of', self.ids)])
        all_partners.read(['parent_id'])

        sale_order_groups = self.env['sale.order'].read_group(
            domain=[('partner_id', 'in', all_partners.ids)],
            fields=['partner_id'], groupby=['partner_id']
        )
        for group in sale_order_groups:
            partner = self.browse(group['partner_id'][0])
            while partner:
                if partner in self:
                    partner.sale_order_count += group['partner_id_count']
                partner = partner.parent_id

    # Gaurav 3march20 for unique name of customer
    @api.multi
    @api.constrains('name')
    def _check_unique_name(self):
        """
        Check Name should be unique
        """
        for line in self:
            all_temp_list = []
            all_temp = line.env['res.partner'].search(
                [('company_id', '=', line.env.user.company_id.id)])
            if all_temp:
                all_temp_list = [temp_val.name.lower().lstrip().rstrip() for temp_val in all_temp]
            name = line.name.lower().lstrip().rstrip()
            print("name................", name,all_temp_list.count(name))
            if name in all_temp_list:
                if all_temp_list.count(name) > 1:
                    raise ValidationError(_('Customer already exist !'))

    # Gaurav end

    # Gaurav 17/3/20 GST validation
    @api.constrains('vat')
    def _validate_gstin(self):
        for val in self:
            if self.vat:
                if not re.search("\d{2}[A-Z]{5}\d{4}[A-Z]{1}[A-Z\d]{1}[Z]{1}[A-Z\d]{1}", self.vat):
                    raise ValidationError(_('Invalid Entry of GSTIN.\n'
                                            'It should contain first 2 digits as state code, next 10 digits will be PAN number of taxpayer !!\n'
                                            'e.g. 07AAFFD3743A1ZY'))
            if val.vat:
                gst = val.vat
                if val.state_id:
                    if val.state_id.l10n_in_tin != gst[:2] or len(gst) != 15:
                        raise ValidationError(_('GST number is not valid!!'))
                else:
                    raise ValidationError(_('Please Select valid State'))
                    # Gaurav end

    # Gaurav commented for unique constrains
    # validations for duplicate customer creation
    # @api.model
    # def create(self, vals):
    #
    #     # conditon to validate the duplicate product creation
    #     all_product = self.env['res.partner'].search([('customer', '=', True)])
    #     print('all_product', all_product)
    #     print('self.env.user.company_id.id', self.env.user.company_id.id)
    #     for value in all_product:
    #         value_name = value.name
    #         print('value_name', value_name)
    #         current_product_name = vals.get('name')
    #         lower_value_name = value_name.lower()
    #         lower_current_product_name = current_product_name.lower()
    #         print('ghhhhhhhhhhhhh', value_name)
    #         print('ghhhhhhhhhhhhh', current_product_name)
    #         if lower_value_name == lower_current_product_name:
    #             raise ValidationError(_('The Customer is Already Exist'))
    #     # print(A)
    #     res = super(ResPartner, self).create(vals)
    #     return res

    # @api.multi
    # def write(self, vals):
    #     # conditon to validate the duplicate product creation
    #     all_product2 = self.env['res.partner'].search([('customer', '=', True)])
    #     print('all_product', all_product2)
    #     for value in all_product2:
    #         value_name = value.name
    #         print('value_name',value_name)
    #         current_product_name = vals.get('name')
    #         if value_name and current_product_name:
    #             lower_value_name = value_name.lower()
    #             lower_current_product_name = current_product_name.lower()
    #             print('ghhhhhhhhhhhhh w', lower_value_name)
    #             print('ghhhhhhhhhhhhh w', lower_current_product_name)
    #             if lower_value_name == lower_current_product_name:
    #                 raise ValidationError(_('The Customer is Already Exist'))
    #     # print(A)
    #     res = super(ResPartner, self).write(vals)
    #     return res



class ProductCustomerInfo(models.Model):
    _name = "product.customer.info"
    _description = "Information about a product Customer"
    _order = 'sequence, min_qty desc, price'



    name = fields.Many2one('res.partner', 'Customer',domain=[('customer', '=', True),('parent_id','=',False)], ondelete='cascade', required=True,help="Customer of this product")
    product_name = fields.Char('Customer Product Name',help="This customer's product name will be used when printing a request for quotation. Keep empty to use the internal one.")
    product_code = fields.Char('Customer Product Code',help="This customer's product code will be used when printing a request for quotation. Keep empty to use the internal one.")
    sequence = fields.Integer('Sequence', default=1, help="Assigns the priority to the list of product Customer.")
    product_uom = fields.Many2one('product.uom', 'Customer Unit of Measure',readonly="1", related='product_tmpl_id.uom_po_id',help="This comes from the product form.")
    min_qty = fields.Float('Minimal Quantity', default=0.0,help="The minimal quantity to purchase from this vendor, expressed in the Customer Product Unit of Measure if not any, in the default unit of measure of the product otherwise.")
    price = fields.Float('Price', default=0.0, help="The price to purchase a product")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,default=lambda self: self.env.user.company_id.id)
    currency_id = fields.Many2one('res.currency', 'Currency',default=lambda self: self.env.user.company_id.currency_id.id,required=True)
    date_start = fields.Date('Start Date', help="Start date for this customer price")
    date_end = fields.Date('End Date', help="End date for this customer price")
    product_id = fields.Many2one('product.product', 'Product Variant',help="If not set, the vendor price will apply to all variants of this products.")
    product_tmpl_id = fields.Many2one('product.template', 'Product Template',index=True, ondelete='cascade', oldname='product_id')
    product_variant_count = fields.Integer('Variant Count', related='product_tmpl_id.product_variant_count')
    delay = fields.Integer('Delivery Lead Time', default=1,help="Lead time in days between the confirmation of the purchase order and the receipt of the products in your warehouse. Used by the scheduler for automatic computation of the purchase order planning.")
    descrep = fields.Char(string='Desc')
    remarks = fields.Char(string='Remarks')

    customer_info_id = fields.Many2one('product.customer.info', 'Customer info')
    customer_info_ids = fields.One2many('product.customer.info', 'customer_info_id', string="Customer info")

    child = fields.Boolean('Child', help="True: If One2many Records are added")
    active = fields.Boolean('Active', default=True)
    active1 = fields.Boolean('Active', default=True)
    red_flag = fields.Boolean('Red Flag', default=False)
    active_hist_text = fields.Text('Active/Inactive History')
    red_flag_hist_text = fields.Text('Red Flag On/Off History')
    categ_id = fields.Many2one('product.category', 'Category')
    product_form = fields.Boolean('Product Form')
    customer_form = fields.Boolean('Customer Form')




class SupplierInfo(models.Model):
    _name = "product.supplierinfo"
    _description = "Information about a product vendor"
    _order = 'sequence, min_qty desc, price'

    name = fields.Many2one(
        'res.partner', 'Vendor',
        domain=[('supplier', '=', True)], ondelete='cascade', required=True, readonly=True,
        help="Vendor of this product")
    product_name = fields.Char(
        'Vendor Product Name',
        help="This vendor's product name will be used when printing a request for quotation. Keep empty to use the internal one.")
    product_code = fields.Char(
        'Vendor Product Code',
        help="This vendor's product code will be used when printing a request for quotation. Keep empty to use the internal one.")
    sequence = fields.Integer(
        'Sequence', default=1, help="Assigns the priority to the list of product vendor.")
    product_uom = fields.Many2one(
        'product.uom', 'Vendor Unit of Measure',
        readonly="1", related='product_tmpl_id.uom_po_id',
        help="This comes from the product form.")
    min_qty = fields.Float(
        'Minimal Quantity', default=0.0,
        help="The minimal quantity to purchase from this vendor, expressed in the vendor Product Unit of Measure if not any, in the default unit of measure of the product otherwise.")
    price = fields.Float(
        'Price', default=0.0,
        help="The price to purchase a product")
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env.user.company_id.id, index=1)
    currency_id = fields.Many2one(
        'res.currency', 'Currency',
        default=lambda self: self.env.user.company_id.currency_id.id,
        required=True)
    date_start = fields.Date('Start Date', help="Start date for this vendor price")
    date_end = fields.Date('End Date', help="End date for this vendor price")
    product_id = fields.Many2one(
        'product.product', 'Product Variant',
        help="If not set, the vendor price will apply to all variants of this products.")
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product Template',
        index=True, ondelete='cascade', oldname='product_id')
    product_variant_count = fields.Integer('Variant Count', related='product_tmpl_id.product_variant_count')
    delay = fields.Integer(
        'Delivery Lead Time', default=1, required=True,
        help="Lead time in days between the confirmation of the purchase order and the receipt of the products in your warehouse. Used by the scheduler for automatic computation of the purchase order planning.")