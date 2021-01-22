from odoo import api, fields, models, tools, _
from odoo.http import Controller, request
import time, datetime
from odoo.exceptions import UserError
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.exceptions import ValidationError, RedirectWarning, except_orm
from odoo.addons import decimal_precision as dp
from odoo.tools.float_utils import float_is_zero, float_compare
from odoo.tools import pycompat
from odoo.tools.float_utils import float_round
from datetime import timedelta
import datetime
import dateutil.relativedelta
from datetime import datetime as dt
from lxml import etree
from threading import Timer


class TallyProductCategory(models.Model):
    _description = "Product Category"
    _name = "tally.product.category"

    name = fields.Char('Tally Category Name',size=512)
    # guid = fields.Char('GUID',size=512)
    tally_guid = fields.Char('GUID',size=512)
    parent_id = fields.Char('Parent Category')
    sequence_code = fields.Char('Sequence Code')
    tally_active = fields.Boolean('Tally Active')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    type = fields.Char('Type')


#shubham Dated : 11/2/19
class TallyGodowns(models.Model):
    _description = "Tally Godowns"
    _name = "tally.stock.location"

    name = fields.Char('Tally Category Name',size=512)
    usage = fields.Char('Usage')
    location_id = fields.Many2one('tally.stock.location', string="Location")
    # guid = fields.Char('GUID',size=512)
    guid = fields.Char('GUID',size=512)
    # parent_id = fields.Char('Parent Category')
    # sequence_code = fields.Char('Sequence Code')
    # tally_active = fields.Boolean('Tally Active')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    # type = fields.Char('Type')



class TallyProductTemplate(models.Model):
    _description = "Product Template and Product"
    _name = "tally.product.template"

    name = fields.Char('Tally Product Name',size=512)
    guid = fields.Char('GUID',size=512)
    categ_id = fields.Char('Category')
    sequence_code = fields.Char('Sequence Code')
    uom_id = fields.Char('Primary UOM')
    uom_po_id = fields.Char('Secondary UOM')
    uom_secondary_id = fields.Char('Secondary UOM')
    qty_on_hand = fields.Float('Current Stock')
    product_type = fields.Char('Product Type')
    hsn_code = fields.Char('HSN code')
    tracking = fields.Char('Tracking')
    product_route = fields.Char('Routes')
    purchase_ok = fields.Boolean('Raw material')
    sale_ok = fields.Boolean('Finish Good')
    qty_multiple = fields.Char('Qty Multiple')
    arc_item = fields.Boolean('ARC Item')
    tolerance = fields.Char('Tolerance')
    min_stock_level = fields.Char('Min Stock Level')
    cost_price = fields.Char('Cost Price')
    sale_price = fields.Char('Sale Price')
    standard_price = fields.Char('Standard Price')
    product_description = fields.Char('Description')
    tally_active = fields.Boolean('Tally Active')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cost_method = fields.Char('Cost Method')


# shubham
class TallyProductProduct(models.Model):
    _description = "Product"
    _name = "tally.product.product"

    name = fields.Char('Tally Product Name',size=512)
    guid = fields.Char('GUID',size=512)
    category_id = fields.Char('Category')
    sequence_code = fields.Char('Sequence Code')
    uom_id = fields.Char('Primary UOM')
    uom_secondary_id = fields.Char('Secondary UOM')
    qty_on_hand = fields.Float('Current Stock')
    product_type = fields.Char('Product Type')
    hsn_code = fields.Char('HSN code')
    tracking = fields.Char('Tracking')
    product_route = fields.Char('Routes')
    purchase_ok = fields.Boolean('Raw material')
    sale_ok = fields.Boolean('Finish Good')
    qty_multiple = fields.Char('Qty Multiple')
    arc_item = fields.Boolean('ARC Item')
    tolerance = fields.Char('Tolerance')
    min_stock_level = fields.Char('Min Stock Level')
    cost_price = fields.Char('Cost Price')
    sale_price = fields.Char('Sale Price')
    standard_price = fields.Char('Standard Price')
    product_description = fields.Char('Description')
    tally_active = fields.Boolean('Tally Active')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    cost_method = fields.Char('Cost Method')


class TallyProductUOM(models.Model):
    _description = "Tally Product UOM"
    _name = "tally.product.uom"

    name = fields.Char('Tally UOM Name',size=512)
    guid = fields.Char('GUID',size=512)
    uom_category = fields.Char('UOM Category')
    tally_active = fields.Boolean('Tally Active')
    uom_type = fields.Char('UOM Type')
    uom_ratio = fields.Char('UOM Ration')
    uom_rounding_precision = fields.Char('Rounding Precision')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)

class TallyPartnerCustomer(models.Model):
    _description = "Tally Partner Customer"
    _name = "tally.partner.customer"

    name = fields.Char('Tally Customer Name',size=512)
    guid = fields.Char('GUID',size=512)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)


class TallyPartnerVendor(models.Model):
    _description = "Tally Partner Vendor"
    _name = "tally.partner.vendor"

    name = fields.Char('Tally Vendor Name',size=512)
    guid = fields.Char('GUID',size=512)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)

class TallyAccountType(models.Model):
    _description = "Tally Account Type"
    _name = "tally.account.type"

    name = fields.Char('Tally Account Type',size=512)
    guid = fields.Char('GUID',size=512)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)

class TallyCompany(models.Model):
    _description = "Tally Company"
    _name = "tally.company"

    name = fields.Char('Tally Company',size=512)
    guid = fields.Char('GUID',size=512)
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)


class ProductCategory(models.Model):
    _inherit = "product.category"

    tally_category_id = fields.Many2one('tally.product.category','Tally Category Link')
    stock_in_tally=fields.Boolean(default = True, string="Should quantity of Item affect the stock")

class ProductTemplate(models.Model):
    _inherit = "product.template"

    tally_product_id = fields.Many2one('tally.product.template','Tally Product Link')

class ProductUOM(models.Model):
    _inherit = "product.uom"

    tally_uom_id = fields.Many2one('tally.product.uom','Tally Product UOM Link')

class ResPartner(models.Model):
    _inherit = "res.partner"

    tally_customer_id = fields.Many2one('tally.partner.customer','Tally Customer Link')
    tally_vendor_id = fields.Many2one('tally.partner.vendor', 'Tally Vendor Link')


class VoucherType(models.Model):
    _description = "Voucher Types"
    _name = 'voucher.type'

    name = fields.Char("Name")
    code = fields.Char("Code")
    tally_link = fields.Many2one("Tally Link")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)

class TallyVoucherType(models.Model):
    _name = 'tally.voucher.type'

    name = fields.Char('Name')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)

class AccountAccount(models.Model):
    _inherit='account.account'

    tally_account_type_id = fields.Many2one('tally.account.type','Tally Account Type')

class ResCompany(models.Model):
    _inherit='res.company'

    tally_company_id = fields.Many2one('tally.company','Tally Company')
    tally_migration = fields.Boolean('Tally Migration',default=False)
    auto_import_tally = fields.Boolean('Auto Import in Tally(By Scheduler)', default=False)
    auto_import_tally_url=fields.Char('Auto Import in Tally Url')
