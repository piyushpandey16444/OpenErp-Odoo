# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import itertools
import psycopg2

from odoo.addons import decimal_precision as dp

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, except_orm
from odoo.tools import pycompat


class ProductTemplate(models.Model):
    _name = "product.template"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Product Template"
    _order = "name"

    # Shivam 02/12/20 code for adding header button on product.template(written 3 function to filter the 'can be sold' and 'can be purchased' item.
    def all_product_show(self):
        result = {}
        all = []
        all_data = self.env['product.template'].search([('id', '>', 0)])
        if all_data:
            all = all_data.ids
        action = self.env.ref('stock.product_template_action_product')
        result = action.read()[0]
        res = self.env.ref('product.product_template_tree_view', False)
        res_form = self.env.ref('product.product_template_only_form_view', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all))]
        result['target'] = 'main'
        result['view_type'] = 'tree'
        result['view_mode'] = 'tree,form'
        return result

    def sold_product_show(self):
        result = {}
        all = []
        all_data = self.env['product.template'].search([('id', '>', 0), ('sale_ok', '=', True)])
        if all_data:
            all = all_data.ids
        action = self.env.ref('stock.product_template_action_product')
        result = action.read()[0]
        res = self.env.ref('product.product_template_tree_view', False)
        res_form = self.env.ref('product.product_template_only_form_view', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all))]
        result['target'] = 'main'
        result['view_type'] = 'tree'
        result['view_mode'] = 'tree,form'
        return result

    def purchased_product_show(self):
        result = {}
        all = []
        all_data = self.env['product.template'].search([('id', '>', 0), ('purchase_ok', '=', True)])
        if all_data:
            all = all_data.ids
        action = self.env.ref('stock.product_template_action_product')
        result = action.read()[0]
        res = self.env.ref('product.product_template_tree_view', False)
        res_form = self.env.ref('product.product_template_only_form_view', False)
        result['views'] = [(res and res.id or False, 'list'), (res_form and res_form.id or False, 'form')]
        result['domain'] = [('id', 'in', tuple(all))]
        result['target'] = 'main'
        result['view_type'] = 'tree'
        result['view_mode'] = 'tree,form'
        return result

    # shivam end

    # Piyush: onchange on category id for categ name 25-04-2020
    @api.onchange("categ_id")
    def categ_id_to_name(self):
        if self.categ_id:
            self.categ_name = self.categ_id.name
    # code ends here

    def _get_default_category_id(self):
        if self._context.get('categ_id') or self._context.get('default_categ_id'):
            return self._context.get('categ_id') or self._context.get('default_categ_id')
        category = self.env.ref('product.product_category_all', raise_if_not_found=False)
        if not category:
            category = self.env['product.category'].search([], limit=1)
        if category:
            return category.id
        else:
            err_msg = _('You must define at least one product category in order to be able to create products.')
            redir_msg = _('Go to Internal Categories')
            raise RedirectWarning(err_msg, self.env.ref('product.product_category_action_form').id, redir_msg)

    def _get_default_uom_id(self):
        return self.env["product.uom"].search([], limit=1, order='id').id

    # Gaurav 3march20 for unique name of product
    @api.multi
    @api.constrains('name')
    def _check_unique_name(self):
        """
        Check Name should be unique
        """
        for line in self:
            all_temp_list = []
            all_temp = line.env['product.template'].search(
                [('company_id', '=', line.env.user.company_id.id)])
            if all_temp:
                all_temp_list = [temp_val.name.lower().lstrip().rstrip() for temp_val in all_temp]
            name = line.name.lower().lstrip().rstrip()
            print("name................", name, all_temp_list.count(name))
            if name in all_temp_list:
                if all_temp_list.count(name) > 1:
                    raise ValidationError(_('Product already exist !'))


    # Gaurav end

    name = fields.Char('Name', index=True, required=True, translate=True)
    sequence = fields.Integer('Sequence', default=1, help='Gives the sequence order when displaying a product list')
    description = fields.Text(
        'Description', translate=True,
        help="A precise description of the Product, used only for internal information purposes.")
    description_purchase = fields.Text(
        'Purchase Description', translate=True,
        help="A description of the Product that you want to communicate to your vendors. "
             "This description will be copied to every Purchase Order, Receipt and Vendor Bill/Credit Note.")
    description_sale = fields.Text(
        'Sale Description', translate=True,
        help="A description of the Product that you want to communicate to your customers. "
             "This description will be copied to every Sales Order, Delivery Order and Customer Invoice/Credit Note")
    type = fields.Selection([
        ('consu', 'Consumable'),
        ('service', 'Service')], string='Product Type', default='consu', required=True,
        help='A stockable product is a product for which you manage stock. The "Inventory" app has to be installed.\n'
             'A consumable product, on the other hand, is a product for which stock is not managed.\n'
             'A service is a non-material product you provide.\n'
             'A digital content is a non-material product you sell online. The files attached to the products are the one that are sold on '
             'the e-commerce such as e-books, music, pictures,... The "Digital Product" module has to be installed.')
    rental = fields.Boolean('Can be Rent')
    categ_id = fields.Many2one(
        'product.category', 'Internal Category',
        change_default=True, default=_get_default_category_id,
        required=True, help="Select category for the current product")
    # Piyush: code for adding in individual_box_item in in prod.packaging 25-04-2020
    categ_name = fields.Char("Category Name")
    packaging_ids_check = fields.Boolean('Check_P', default=True)
    # code ends here
    currency_id = fields.Many2one(
        'res.currency', 'Currency', compute='_compute_currency_id')
    cost_currency_id = fields.Many2one(
        'res.currency', 'Cost Currency', compute='_compute_cost_currency_id')

    #Himanshu : 27-07-2020 This boolean field is for making tracebility to no travking when it's true in the function change_val()
    check1=fields.Boolean()
    #end Himanshu

    # price fields
    price = fields.Float(
        'Price', compute='_compute_template_price', inverse='_set_template_price',
        digits=dp.get_precision('Product Price'))
    list_price = fields.Float(
        'Sales Price', default=1.0,
        digits=dp.get_precision('Product Price'),
        help="Base price to compute the customer price. Sometimes called the catalog price.")
    lst_price = fields.Float(
        'Public Price', related='list_price',
        digits=dp.get_precision('Product Price'))
    standard_price = fields.Float(
        'Cost', compute='_compute_standard_price',
        inverse='_set_standard_price', search='_search_standard_price',
        digits=dp.get_precision('Product Price'), groups="base.group_user",
        help = "Cost used for stock valuation in standard price and as a first price to set in average/fifo. "
               "Also used as a base price for pricelists. "
               "Expressed in the default unit of measure of the product. ")

    volume = fields.Float(
        'Volume', compute='_compute_volume', inverse='_set_volume',
        help="The volume in m3.", store=True)
    weight = fields.Float(
        'Weight', compute='_compute_weight', digits=dp.get_precision('Stock Weight'),
        inverse='_set_weight', store=True,
        help="The weight of the contents in Kg, not including any packaging, etc.")

    sale_ok = fields.Boolean(
        'Can be Sold', default=True,
        help="Specify if the product can be selected in a sales order line.")
    purchase_ok = fields.Boolean('Can be Purchased', default=True)

    pricelist_id = fields.Many2one(
        'product.pricelist', 'Pricelist', store=False,
        help='Technical field. Used for searching on pricelists, not stored in database.')
    uom_id = fields.Many2one(
        'product.uom', 'Primary UOM',
        default=_get_default_uom_id, required=True,
        help="Default Unit of Measure used for all stock operation.")
    uom_po_id = fields.Many2one(
        'product.uom', 'Secondary UOM',
        default=_get_default_uom_id, required=True,
        help="Default Unit of Measure used for purchase orders. It must be in the same category than the default unit "
             "of measure.")

    # Piyush: code for adding conversion factor 24-04-2020
    conversion_factor = fields.Float('Conversion Factor', track_visibility='onchange', help="Used when Primary & "
                                                                                            "Secondary UOM are "
                                                                                            "different",
                                     digits=dp.get_precision('Product Unit of Measure'))
    conversion_factor_visible = fields.Boolean(compute='_conversion_factor_visible', string="Con Factor "
                                                                                            "Visible/Invisible",
                                               store=True, help="If value is True then Conversion factor is Visible "
                                                                "on form")

    # code ends here

    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get('product.template'), index=1)
    packaging_ids = fields.One2many(
        'product.packaging', string="Product Packages", compute="_compute_packaging_ids", inverse="_set_packaging_ids",
        help="Gives the different ways to package the same product.")
    seller_ids = fields.One2many('product.supplierinfo', 'product_tmpl_id', 'Vendors')
    variant_seller_ids = fields.One2many('product.supplierinfo', 'product_tmpl_id')

    # Gaurav 24/4/20 adds saledetail_id for product.saledetail
    saledetail_id = fields.One2many('product.saledetail', 'product_detail_tmpl_id', 'Sale product detail')
    purchasedetail_id = fields.One2many('product.purchasedetail', 'product_detail_pur_tmpl_id', 'Purchase product detail')
    # Gaurav end

    active = fields.Boolean('Active', default=True, help="If unchecked, it will allow you to hide the product without removing it.")
    color = fields.Integer('Color Index')

    is_product_variant = fields.Boolean(string='Is a product variant', compute='_compute_is_product_variant')
    attribute_line_ids = fields.One2many('product.attribute.line', 'product_tmpl_id', 'Product Attributes')
    product_variant_ids = fields.One2many('product.product', 'product_tmpl_id', 'Products', required=True)
    # performance: product_variant_id provides prefetching on the first product variant only
    product_variant_id = fields.Many2one('product.product', 'Product', compute='_compute_product_variant_id')

    product_variant_count = fields.Integer(
        '# Product Variants', compute='_compute_product_variant_count')

    # related to display product product information if is_product_variant
    barcode = fields.Char('Barcode', oldname='ean13', related='product_variant_ids.barcode')
    default_code = fields.Char(
        'Internal Reference', compute='_compute_default_code',
        inverse='_set_default_code', store=True)

    item_ids = fields.One2many('product.pricelist.item', 'product_tmpl_id', 'Pricelist Items')

    # Piyush: added field for holding image of original quality for migration on 29-09-2020
    full_quality_image = fields.Binary(string="Image", attachment=True)

    # image: all image fields are base64 encoded and PIL-supported
    image = fields.Binary(
        "Image", attachment=True,
        help="This field holds the image used as image for the product, limited to 1024x1024px.")
    image_medium = fields.Binary(
        "Medium-sized image", attachment=True,
        help="Medium-sized image of the product. It is automatically "
             "resized as a 128x128px image, with aspect ratio preserved, "
             "only when the image exceeds one of those sizes. Use this field in form views or some kanban views.")
    image_small = fields.Binary(
        "Small-sized image", attachment=True,
        help="Small-sized image of the product. It is automatically "
             "resized as a 64x64px image, with aspect ratio preserved. "
             "Use this field anywhere a small image is required.")

    # flag for check product in use or not
    product_transaction = fields.Boolean(string="Product Transaction")
    # negative and positive setting option
    positive_stock = fields.Boolean("Positive Stock")
 # Piyush: added migrate_data field for making default code req for migrations on 03-09-2020
    migrate_data = fields.Boolean(string="Migrate", default=False)

    # Aman 22/12/2020 Added field to disable hsn_code field
    hsn_disable = fields.Boolean(string="HSN not applicable", default=False)

    # Aman 22/12/2020 Added function to remove hsn_code field value
    @api.onchange('hsn_disable')
    def check_hsn_disable(self):
        if self.hsn_disable == True:
            self.hsn_id = False
            self.customer_tax_lines_dupl = [(5, 0, 0)]
            self.vendor_tax_lines_dupl = [(5, 0, 0)]

    # Aman end

#Himanshu : 27-07-2020 when category is Packing Material then tracing should be no tracking only
    @api.onchange('categ_id')
    def change_val(self):

        if self.categ_id.name == "Packing Material":
            self.check1=True
        else:
            self.check1=False
#End Himanshu

    @api.depends('product_variant_ids')
    def _compute_product_variant_id(self):
        for p in self:
            p.product_variant_id = p.product_variant_ids[:1].id

    @api.multi
    def _compute_currency_id(self):
        try:
            main_company = self.sudo().env.ref('base.main_company')
        except ValueError:
            main_company = self.env['res.company'].sudo().search([], limit=1, order="id")
        for template in self:
            template.currency_id = template.company_id.sudo().currency_id.id or main_company.currency_id.id

    def _compute_cost_currency_id(self):
        for template in self:
            template.cost_currency_id = self.env.user.company_id.currency_id.id

    @api.multi
    def _compute_template_price(self):
        prices = {}
        pricelist_id_or_name = self._context.get('pricelist')
        if pricelist_id_or_name:
            pricelist = None
            partner = self._context.get('partner')
            quantity = self._context.get('quantity', 1.0)

            # Support context pricelists specified as display_name or ID for compatibility
            if isinstance(pricelist_id_or_name, pycompat.string_types):
                pricelist_data = self.env['product.pricelist'].name_search(pricelist_id_or_name, operator='=', limit=1)
                if pricelist_data:
                    pricelist = self.env['product.pricelist'].browse(pricelist_data[0][0])
            elif isinstance(pricelist_id_or_name, pycompat.integer_types):
                pricelist = self.env['product.pricelist'].browse(pricelist_id_or_name)

            if pricelist:
                quantities = [quantity] * len(self)
                partners = [partner] * len(self)
                prices = pricelist.get_products_price(self, quantities, partners)

        for template in self:
            template.price = prices.get(template.id, 0.0)

    @api.multi
    def _set_template_price(self):
        if self._context.get('uom'):
            for template in self:
                value = self.env['product.uom'].browse(self._context['uom'])._compute_price(template.price,
                                                                                            template.uom_id)
                template.write({'list_price': value})
        else:
            self.write({'list_price': self.price})

    @api.depends('product_variant_ids', 'product_variant_ids.standard_price')
    def _compute_standard_price(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.standard_price = template.product_variant_ids.standard_price
        for template in (self - unique_variants):
            template.standard_price = 0.0

    @api.one
    def _set_standard_price(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.standard_price = self.standard_price

    def _search_standard_price(self, operator, value):
        products = self.env['product.product'].search([('standard_price', operator, value)], limit=None)
        return [('id', 'in', products.mapped('product_tmpl_id').ids)]

    @api.depends('product_variant_ids', 'product_variant_ids.volume')
    def _compute_volume(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.volume = template.product_variant_ids.volume
        for template in (self - unique_variants):
            template.volume = 0.0

    @api.one
    def _set_volume(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.volume = self.volume

    @api.depends('product_variant_ids', 'product_variant_ids.weight')
    def _compute_weight(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.weight = template.product_variant_ids.weight
        for template in (self - unique_variants):
            template.weight = 0.0

    def _compute_is_product_variant(self):
        for template in self:
            template.is_product_variant = False

    @api.one
    def _set_weight(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.weight = self.weight

    @api.one
    @api.depends('product_variant_ids.product_tmpl_id')
    def _compute_product_variant_count(self):
        # do not pollute variants to be prefetched when counting variants
        self.product_variant_count = len(self.with_prefetch().product_variant_ids)

    @api.depends('product_variant_ids', 'product_variant_ids.default_code')
    def _compute_default_code(self):
        unique_variants = self.filtered(lambda template: len(template.product_variant_ids) == 1)
        for template in unique_variants:
            template.default_code = template.product_variant_ids.default_code
        for template in (self - unique_variants):
            template.default_code = False

    @api.one
    def _set_default_code(self):
        if len(self.product_variant_ids) == 1:
            self.product_variant_ids.default_code = self.default_code

    @api.depends('product_variant_ids', 'product_variant_ids.packaging_ids')
    def _compute_packaging_ids(self):
        for p in self:
            if len(p.product_variant_ids) == 1:
                p.packaging_ids = p.product_variant_ids.packaging_ids

    def _set_packaging_ids(self):
        for p in self:
            if len(p.product_variant_ids) == 1:
                p.product_variant_ids.packaging_ids = p.packaging_ids

    # Piyush: commented on 24-04-2020 @api.constrains('uom_id', 'uom_po_id') def _check_uom(self): if any(
    # template.uom_id and template.uom_po_id and template.uom_id.category_id != template.uom_po_id.category_id for
    # template in self): raise ValidationError(_('Error: The default Unit of Measure and the purchase Unit of Measure
    # must be in the same category.')) return True

    @api.onchange('uom_id')
    def _onchange_uom_id(self):
        if self.uom_id:
            self.uom_po_id = self.uom_id.id

    # Piyush: for conversion factor visibility 24-04-2020
    @api.depends('uom_id', 'uom_po_id')
    def _conversion_factor_visible(self):
        """
        If "Primary UOM" & "Secondary UOM" are not same then
        this boolean field is True and "Conversion Factor" visible on form
        """
        for line in self:
            conversion_factor_visible = uom_categ_id = uom_po_categ_id = False
            if line.uom_id:
                # uom_id = line.uom_id and line.uom_id.id or False
                uom_categ_id = line.uom_id and line.uom_id.category_id.id or False
            if line.uom_po_id:
                # uom_po_id = line.uom_po_id and line.uom_po_id.id or False
                uom_po_categ_id = line.uom_po_id and line.uom_po_id.category_id.id or False
            if uom_categ_id and uom_po_categ_id:
                if uom_categ_id != uom_po_categ_id:
                    conversion_factor_visible = True
                else:
                    conversion_factor_visible = False
                    line.conversion_factor = 0

            line.conversion_factor_visible = conversion_factor_visible

    # code for conversion_factor value check
    @api.multi
    @api.constrains('conversion_factor')
    def _check_conversion_factor(self):
        """
        Quantity Multiple can not be less than 1
        """
        for line in self:
            if line.conversion_factor_visible and line.conversion_factor <= 0:
                raise ValidationError(_('Conversion Factor Should be greater than zero !'))

    # code ends here

    @api.model
    def create(self, vals):
        ''' Store the initial standard price in order to be able to retrieve the cost of a product template for a given date'''
        # TDE FIXME: context brol
        # Commented for duplicate constrains
        # # conditon to validate the duplicate product creation
        # all_product = self.env['product.template'].search([('company_id', '=', self.env.user.company_id.id)])
        # print('all_product', all_product)
        # for value in all_product:
        #     value_name = value.name
        #     print('value_name', value_name)
        #     current_product_name = vals.get('name')
        #     lower_value_name = value_name.lower()
        #     lower_current_product_name = current_product_name.lower()
        #     print('ghhhhhhhhhhhhh', value_name)
        #     print('ghhhhhhhhhhhhh', current_product_name)
        #     if lower_value_name == lower_current_product_name:
        #         raise ValidationError(_('The Product is Already Exist'))


        tools.image_resize_images(vals)
        template = super(ProductTemplate, self).create(vals)
        # Piyush: code for making check false after create function 25-04-2020
        if template.packaging_ids_check:
            template.packaging_ids_check = False
        # code ends here

        if "create_product_product" not in self._context:
            template.with_context(create_from_tmpl=True).create_variant_ids()

        # This is needed to set given values to first variant after creation
        related_vals = {}
        if vals.get('barcode'):
            related_vals['barcode'] = vals['barcode']
        if vals.get('default_code'):
            related_vals['default_code'] = vals['default_code']
        if vals.get('standard_price'):
            related_vals['standard_price'] = vals['standard_price']
        if vals.get('volume'):
            related_vals['volume'] = vals['volume']
        if vals.get('weight'):
            related_vals['weight'] = vals['weight']
        # Please do forward port
        if vals.get('packaging_ids'):
            related_vals['packaging_ids'] = vals['packaging_ids']
        if related_vals:
            template.write(related_vals)

        # validating for sale and buy option
        # Piyush: code for checking module installed ecom_integration on 25-10-2020
        module_check = self.env['ir.module.module'].search([('name', '=', 'ecom_integration'),
                                                            ('state', '=', 'installed')])
        if not vals.get('sale_ok') and not vals.get('purchase_ok') and not module_check:
            raise ValidationError(_('Please Select The Type of Product'))

        return template


    @api.multi
    def write(self, vals):
        tools.image_resize_images(vals)
        # Commented for duplicate constrains
        # # conditon to validate the duplicate product creation
        # all_product = self.env['product.template'].search([('company_id', '=', self.env.user.company_id.id)])
        # for value in all_product:
        #     value_name = value.name
        #     current_product_name = vals.get('name')
        #     if value_name and current_product_name:
        #         lower_value_name = value_name.lower()
        #         lower_current_product_name = current_product_name.lower()
        #         print('ghhhhhhhhhhhhh w', lower_value_name)
        #         print('ghhhhhhhhhhhhh w', lower_current_product_name)
        #         if lower_value_name == lower_current_product_name:
        #             raise ValidationError(_('The Product is Already Exist'))

        res = super(ProductTemplate, self).write(vals)

        if 'attribute_line_ids' in vals or vals.get('active'):
            self.create_variant_ids()
        if 'active' in vals and not vals.get('active'):
            self.with_context(active_test=False).mapped('product_variant_ids').write({'active': vals.get('active')})

        # validating for sale and buy option
        # Piyush: code for checking module installed ecom_integration on 25-10-2020
        module_check = self.env['ir.module.module'].search([('name', '=', 'ecom_integration'),
                                                            ('state', '=', 'installed')])
        if not self.sale_ok and not self.purchase_ok and not module_check:
            raise ValidationError(_('Please Select The Type of Product'))
        return res

    @api.multi
    def copy(self, default=None):
        # TDE FIXME: should probably be copy_data
        self.ensure_one()
        if default is None:
            default = {}
        if 'name' not in default:
            default['name'] = _("%s (copy)") % self.name
            #Jatin added code for adding taxes in vendoe and customer taxes lines 14-07-2020
            copy_tax_lines= self.tax_hsn_code_id()
            default['customer_tax_lines']= copy_tax_lines[0]
            default['vendor_tax_lines']= copy_tax_lines[1]
            #end Jatin
        return super(ProductTemplate, self).copy(default=default)

    # Jatin added code for adding taxes in vendoe and customer taxes lines 14-07-2020
    def tax_hsn_code_id(self):
        tax_list = []
        data_hsn_all = self.env['tax.master'].search([('id', '=', self.hsn_id.id)])
        if data_hsn_all:
            data_hsn_all_ids = data_hsn_all.ids
            if self.hsn_id:
                for val in data_hsn_all:
                    hsn_code = self.hsn_id.hsn_code
                    self.env.cr.execute(""" select id from tax_master_details a
                                                                    where a.company_id = %s and a.hsn_code like %s and (a.tax_group_id|| a.type_tax_use) in
                                                                    (select distinct ( b.tax_group_id||b.type_tax_use ) from account_tax b
                                                                    where  a.from_date <= current_date and
                                                                    a.from_date = (select max(from_date)
                                                                    from tax_master_details c
                                                                    where a.hsn_code = c.hsn_code and
                                                                    a.company_id = c.company_id and
                                                                    c.from_date <= current_date and
                                                                    (c.inactive_date >= current_date or c.inactive_date is null) and a.tax_group_id|| a.type_tax_use =
                                                                    c.tax_group_id|| c.type_tax_use) and a.tax_id not in ( select d.tax_id
                                                                    from tax_master_details d
                                                                    where d.inactive = true and
                                                                    d.inactive_date < current_date and
                                                                    d.company_id =b.company_id))""",
                                        (self.env.user.company_id.id, hsn_code,),
                                        data_hsn_all_ids)
                    all_taxes = self.env.cr.dictfetchall()
                    if all_taxes:
                        for val in all_taxes:
                            tax_detail_id = val.get('id')
                            tax_list.append(tax_detail_id)
                vendor_tax_tup_list = [(5,0,0)]
                customer_tax_tup_list = [(5,0,0)]
                for line in self.env['tax.master.details'].browse(tax_list):
                    if self.purchase_ok and line.tax_id.type_tax_use == 'purchase':
                        vendor_taxes_tup = (0, False, {
                            'tax_id': line.tax_id.id,
                            'tax_group_id': line.tax_group_id.id,
                            'tax_percentage': line.tax_percentage,
                            'label': line.label,
                            'from_date': line.from_date,
                            'tax_master_detail_id': line.id or False,
                        })
                        vendor_tax_tup_list.append(vendor_taxes_tup)
                    if self.sale_ok and line.tax_id.type_tax_use == 'sale':
                        cust_taxes_tup = (0, False, {
                            'tax_id': line.tax_id.id,
                            'tax_group_id': line.tax_group_id.id,
                            'tax_percentage': line.tax_percentage,
                            'label': line.label,
                            'from_date': line.from_date,
                            'tax_master_detail_id': line.id or False,
                        })
                        customer_tax_tup_list.append(cust_taxes_tup)
                tax_lines_duplicate=[]
                tax_lines_duplicate.append(customer_tax_tup_list)
                tax_lines_duplicate.append(vendor_tax_tup_list)
        return tax_lines_duplicate
    #end Jatin

    @api.multi
    def name_get(self):
        # Prefetch the fields used by the `name_get`, so `browse` doesn't fetch other fields
        self.read(['name', 'default_code'])
        return [(template.id, '%s%s' % (template.default_code and '[%s] ' % template.default_code or '', template.name))
                for template in self]

    @api.model
    def name_search(self, name='', args=None, operator='ilike', limit=100):
        # Only use the product.product heuristics if there is a search term and the domain
        # does not specify a match on `product.template` IDs.
        if not name or any(term[0] == 'id' for term in (args or [])):
            return super(ProductTemplate, self).name_search(name=name, args=args, operator=operator, limit=limit)

        Product = self.env['product.product']
        templates = self.browse([])
        while True:
            domain = templates and [('product_tmpl_id', 'not in', templates.ids)] or []
            args = args if args is not None else []
            products_ns = Product.name_search(name, args + domain, operator=operator)
            products = Product.browse([x[0] for x in products_ns])
            templates |= products.mapped('product_tmpl_id')
            if (not products) or (limit and (len(templates) > limit)):
                break

        # re-apply product.template order + name_get
        return super(ProductTemplate, self).name_search(
            '', args=[('id', 'in', list(set(templates.ids)))],
            operator='ilike', limit=limit)

    @api.multi
    def price_compute(self, price_type, uom=False, currency=False, company=False):
        # TDE FIXME: delegate to template or not ? fields are reencoded here ...
        # compatibility about context keys used a bit everywhere in the code
        if not uom and self._context.get('uom'):
            uom = self.env['product.uom'].browse(self._context['uom'])
        if not currency and self._context.get('currency'):
            currency = self.env['res.currency'].browse(self._context['currency'])

        templates = self
        if price_type == 'standard_price':
            # standard_price field can only be seen by users in base.group_user
            # Thus, in order to compute the sale price from the cost for users not in this group
            # We fetch the standard price as the superuser
            templates = self.with_context(force_company=company and company.id or self._context.get('force_company',
                                                                                                    self.env.user.company_id.id)).sudo()

        prices = dict.fromkeys(self.ids, 0.0)
        for template in templates:
            prices[template.id] = template[price_type] or 0.0

            if uom:
                prices[template.id] = template.uom_id._compute_price(prices[template.id], uom)

            # Convert from current user company currency to asked one
            # This is right cause a field cannot be in more than one currency
            if currency:
                prices[template.id] = template.currency_id.compute(prices[template.id], currency)

        return prices

    # compatibility to remove after v10 - DEPRECATED
    @api.model
    def _price_get(self, products, ptype='list_price'):
        return products.price_compute(ptype)

    @api.multi
    def create_variant_ids(self):
        Product = self.env["product.product"]
        AttributeValues = self.env['product.attribute.value']
        for tmpl_id in self.with_context(active_test=False):
            # adding an attribute with only one value should not recreate product
            # write this attribute on every product to make sure we don't lose them
            variant_alone = tmpl_id.attribute_line_ids.filtered(
                lambda line: line.attribute_id.create_variant and len(line.value_ids) == 1).mapped('value_ids')
            for value_id in variant_alone:
                updated_products = tmpl_id.product_variant_ids.filtered(
                    lambda product: value_id.attribute_id not in product.mapped('attribute_value_ids.attribute_id'))
                updated_products.write({'attribute_value_ids': [(4, value_id.id)]})

            # iterator of n-uple of product.attribute.value *ids*
            variant_matrix = [
                AttributeValues.browse(value_ids)
                for value_ids in itertools.product(*(line.value_ids.ids for line in tmpl_id.attribute_line_ids if
                                                     line.value_ids[:1].attribute_id.create_variant))
            ]

            # get the value (id) sets of existing variants
            existing_variants = {
                frozenset(variant.attribute_value_ids.filtered(lambda r: r.attribute_id.create_variant).ids) for variant
                in tmpl_id.product_variant_ids}
            # -> for each value set, create a recordset of values to create a
            #    variant for if the value set isn't already a variant
            to_create_variants = [
                value_ids
                for value_ids in variant_matrix
                if set(value_ids.ids) not in existing_variants
            ]

            # check product
            variants_to_activate = self.env['product.product']
            variants_to_unlink = self.env['product.product']
            for product_id in tmpl_id.product_variant_ids:
                if not product_id.active and product_id.attribute_value_ids.filtered(
                        lambda r: r.attribute_id.create_variant) in variant_matrix:
                    variants_to_activate |= product_id
                elif product_id.attribute_value_ids.filtered(
                        lambda r: r.attribute_id.create_variant) not in variant_matrix:
                    variants_to_unlink |= product_id
            if variants_to_activate:
                variants_to_activate.write({'active': True})

            # create new product
            for variant_ids in to_create_variants:
                new_variant = Product.create({
                    'product_tmpl_id': tmpl_id.id,
                    'attribute_value_ids': [(6, 0, variant_ids.ids)]
                })

            # unlink or inactive product
            for variant in variants_to_unlink:
                try:
                    with self._cr.savepoint(), tools.mute_logger('odoo.sql_db'):
                        variant.unlink()
                # We catch all kind of exception to be sure that the operation doesn't fail.
                except (psycopg2.Error, except_orm):
                    variant.write({'active': False})
                    pass
        return True
