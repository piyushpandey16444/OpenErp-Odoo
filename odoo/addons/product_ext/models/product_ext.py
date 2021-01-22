import itertools
import psycopg2
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, except_orm
from odoo.tools import pycompat
from odoo.addons import decimal_precision as dp
from datetime import datetime
import re
from datetime import timedelta


class ProductTemplate(models.Model):
    _inherit = "product.template"

    vendor_tax_lines = fields.One2many('vendor.tax.line', 'template_id', string='Vendor Taxes')
    # Aman 22/12/2020 Added 2 fields to get add item button when hsn field is disablesd
    vendor_tax_lines_dupl = fields.One2many('vendor.tax.line', 'template_id', string='Vendor Taxes')
    customer_tax_lines = fields.One2many('customer.tax.line', 'template_id', string='Customer Taxes')
    customer_tax_lines_dupl = fields.One2many('customer.tax.line', 'template_id', string='Customer Taxes')
    #Himanshu: 25-07-2020 changed the String name to HSN/SAC CODE
    hsn_id = fields.Many2one('tax.master', track_visibility='onchange', string='Hsn/Sac Code')
    #End Himanshu


    #Jatin added code to add taxes on onchange of sale and purchase checkbox on 05-07-2020
    @api.multi
    @api.onchange('sale_ok')
    def _onchange_sale_ok(self):
        if self.sale_ok:
            if self.hsn_id:
                current_date = str(datetime.now().date())
                data = []
                tax_list = []
                data_hsn_all = self.env['tax.master'].search([('id', '=', self.hsn_id.id)])
                if data_hsn_all:
                    data_hsn_all_ids = data_hsn_all.ids
                    if self.hsn_id:
                        for val in data_hsn_all:
                            hsn_code = self.hsn_id.hsn_code
                            self.env.cr.execute(""" select id from tax_master_details a
                                                                                           where a.hsn_code like %s and (a.tax_group_id|| a.type_tax_use) in
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
                                                (hsn_code,),
                                                data_hsn_all_ids)
                            all_taxes = self.env.cr.dictfetchall()
                            # print("ALL TAXES after query", all_taxes)
                            if all_taxes:
                                for val in all_taxes:
                                    tax_detail_id = val.get('id')
                                    tax_list.append(tax_detail_id)
                        # print("TAXXXXXXXXXXX",tax_list)
                        # self.vendor_tax_lines=[(6, 0, tax_list)]
                        vendor_tax_tup_list = [(5, 0, 0)]
                        customer_tax_tup_list = [(5, 0, 0)]
                        for line in self.env['tax.master.details'].browse(tax_list):
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
                        # print ("vedor tax linessssssssssss",vendor_tax_tup_list,self.hsn_id.hsn_code,customer_tax_tup_list)
                        # ravi at 11/5/2019 start
                        if self.sale_ok:
                            self.customer_tax_lines = customer_tax_tup_list

    @api.multi
    @api.onchange('purchase_ok')
    def _onchange_purchase_ok(self):
        if self.purchase_ok:
            if self.hsn_id:
                current_date = str(datetime.now().date())
                data = []
                tax_list = []
                data_hsn_all = self.env['tax.master'].search([('id', '=', self.hsn_id.id)])
                if data_hsn_all:
                    data_hsn_all_ids = data_hsn_all.ids
                    if self.hsn_id:
                        for val in data_hsn_all:
                            hsn_code = self.hsn_id.hsn_code
                            self.env.cr.execute(""" select id from tax_master_details a
                                                                                        where a.hsn_code like %s and (a.tax_group_id|| a.type_tax_use) in
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
                                                (hsn_code,),
                                                data_hsn_all_ids)
                            all_taxes = self.env.cr.dictfetchall()
                            # print("ALL TAXES after query", all_taxes)
                            if all_taxes:
                                for val in all_taxes:
                                    tax_detail_id = val.get('id')
                                    tax_list.append(tax_detail_id)
                        # print("TAXXXXXXXXXXX",tax_list)
                        # self.vendor_tax_lines=[(6, 0, tax_list)]
                        vendor_tax_tup_list = [(5, 0, 0)]
                        customer_tax_tup_list = []
                        for line in self.env['tax.master.details'].browse(tax_list):
                            if line.tax_id.type_tax_use == 'purchase':
                                vendor_taxes_tup = (0, False, {
                                    'tax_id': line.tax_id.id,
                                    'tax_group_id': line.tax_group_id.id,
                                    'tax_percentage': line.tax_percentage,
                                    'label': line.label,
                                    'from_date': line.from_date,
                                    'tax_master_detail_id': line.id or False,
                                })
                                vendor_tax_tup_list.append(vendor_taxes_tup)
                        # print ("vedor tax linessssssssssss",vendor_tax_tup_list,self.hsn_id.hsn_code,customer_tax_tup_list)
                        # ravi at 11/5/2019 start
                        if self.purchase_ok:
                            self.vendor_tax_lines = vendor_tax_tup_list
     #end Jatin
    @api.onchange('hsn_id')
    def _onchange_hsn_code_id(self):
        current_date = str(datetime.now().date())
        data = []
        tax_list = []
        data_hsn_all = self.env['tax.master'].search([('id', '=', self.hsn_id.id)])
        if data_hsn_all:
            data_hsn_all_ids = data_hsn_all.ids
            # print("LINES DATA", data_hsn_all_ids)
            if self.hsn_id:
                for val in data_hsn_all:
                    # print("TAX MASTER HSN CODE", val.hsn_code)
                    # if len (self.l10n_in_hsn_code) > 2 or len (self.l10n_in_hsn_code) > 4 or len (self.l10n_in_hsn_code) > 6
                    #           or len (self.l10n_in_hsn_code) > 8:
                    # hsn_code = self.l10n_in_hsn_code
                    hsn_code = self.hsn_id.hsn_code
                    # print ("hsn code",hsn_code,type(hsn_code))
                    # self.env.cr.execute(""" select id from tax_master_details a where a.hsn_code like %s
                    #                                             and a.tax_group_id in (
                    #                                             select distinct ( b.tax_group_id ) from account_tax b
                    #                                             where  a.from_date <= current_date
                    #                                             and a.from_date = (select max(from_date) from tax_master_details c
                    #                                             where a.hsn_code = c.hsn_code
                    #                                             and a.company_id = c.company_id
                    #                                             and c.from_date <= current_date
                    #                                             and a.tax_group_id = c.tax_group_id)
                    #                                             and a.tax_id not in ( select d.tax_id from tax_master_details d
                    #                                             where d.inactive = true
                    #                                             and d.inactive_date < current_date
                    #                                             and d.company_id = b.company_id
                    #                                             ) )""", (hsn_code,), data_hsn_all_ids)
                    # print ("hsn codeeeeeeeeeee",hsn_code,data_hsn_all_ids)
                    ##### abhishek 25-2-2020 c.inactive = false replaced by (c.inactive_date >= current_date or c.inactive_date is null)
                    # self.env.cr.execute(""" select id from tax_master_details a
                    #                         where a.hsn_code like %s and (a.tax_group_id|| a.type_tax_use) in
                    #                         (select distinct ( b.tax_group_id||b.type_tax_use ) from account_tax b
                    #                         where  a.from_date <= current_date and
                    #                         a.from_date = (select max(from_date)
                    #                         from tax_master_details c
                    #                         where a.hsn_code = c.hsn_code and
                    #                         a.company_id = c.company_id and
                    #                         c.from_date <= current_date and
                    #                         c.inactive = false and a.tax_group_id|| a.type_tax_use =
                    #                         c.tax_group_id|| c.type_tax_use) and a.tax_id not in ( select d.tax_id
                    #                         from tax_master_details d
                    #                         where d.inactive = true and
                    #                         d.inactive_date < current_date and
                    #                         d.company_id =b.company_id))""", (hsn_code,),data_hsn_all_ids)

                    #####abhishek 30-4-2020 Set company_id = %s due to multi company validation record error
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
                    # data_hsn_all_ids['tax_group_id']
                    # print("DATA HSN IDS",data_hsn_all_ids)
                    all_taxes = self.env.cr.dictfetchall()
                    # print("ALL TAXES after query", all_taxes)
                    if all_taxes:
                        for val in all_taxes:
                            tax_detail_id = val.get('id')
                            tax_list.append(tax_detail_id)
                # print("TAXXXXXXXXXXX",tax_list)
                # self.vendor_tax_lines=[(6, 0, tax_list)]
                #Jatin code changes to pass(5,0,0) to empty the previous list 08-07-2020
                vendor_tax_tup_list = [(5,0,0)]
                customer_tax_tup_list = [(5,0,0)]
                #end Jatin
                for line in self.env['tax.master.details'].browse(tax_list):
                    if self.purchase_ok and line.tax_id.type_tax_use == 'purchase':
                        vendor_taxes_tup = (0, False, {
                            'tax_id': line.tax_id.id,
                            'tax_group_id': line.tax_group_id.id,
                            'tax_percentage': line.tax_percentage,
                            'label': line.label,
                            # Aman 18/08/2020 set value in tree view of customer tax
                            'income_account': line.income_account.id,
                            'income_account_export': line.income_account_export.id,
                            'expense_account': line.expense_account.id,
                            # Aman end
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
                            # Aman 18/08/2020 set value in tree view of customer tax
                            'income_account': line.income_account.id,
                            'income_account_export': line.income_account_export.id,
                            'expense_account': line.expense_account.id,
                            # Aman end
                            'from_date': line.from_date,
                            'tax_master_detail_id': line.id or False,
                        })
                        customer_tax_tup_list.append(cust_taxes_tup)
                # print ("vedor tax linessssssssssss",vendor_tax_tup_list,self.hsn_id.hsn_code,customer_tax_tup_list)
                # ravi at 11/5/2019 start
                if self.purchase_ok:
                    self.vendor_tax_lines = vendor_tax_tup_list
                if self.sale_ok:
                    self.customer_tax_lines = customer_tax_tup_list
                # ravi at 11/5/2019 end

                self.l10n_in_hsn_code = self.hsn_id.hsn_code
                # End of Auto flow of taxes from Tax Master to Item Master
        else:
            vendor_tax_tup_list=[(5,0,0)]
            customer_tax_tup_list=[(5,0,0)]
            self.vendor_tax_lines = vendor_tax_tup_list
            self.customer_tax_lines = customer_tax_tup_list


    # @api.multi
    # @api.onchange('purchase_ok')
    # def _onchange_purchase_ok(self):
    #     if self.purchase_ok:
    #         if self.hsn_id:
    #             current_date = str(datetime.now().date())
    #             data = []
    #             tax_list = []
    #             data_hsn_all = self.env['tax.master'].search([('id', '=', self.hsn_id.id)])
    #             if data_hsn_all:
    #                 data_hsn_all_ids = data_hsn_all.ids
    #                 if self.hsn_id:
    #                     for val in data_hsn_all:
    #                         hsn_code = self.hsn_id.hsn_code
    #
    #                         self.env.cr.execute(""" select id from tax_master_details a
    #                                                                                where a.hsn_code like %s and (a.tax_group_id|| a.type_tax_use) in
    #                                                                                (select distinct ( b.tax_group_id||b.type_tax_use ) from account_tax b
    #                                                                                where  a.from_date <= current_date and
    #                                                                                a.from_date = (select max(from_date)
    #                                                                                from tax_master_details c
    #                                                                                where a.hsn_code = c.hsn_code and
    #                                                                                a.company_id = c.company_id and
    #                                                                                c.from_date <= current_date and
    #                                                                                (c.inactive_date >= current_date or c.inactive_date is null) and a.tax_group_id|| a.type_tax_use =
    #                                                                                c.tax_group_id|| c.type_tax_use) and a.tax_id not in ( select d.tax_id
    #                                                                                from tax_master_details d
    #                                                                                where d.inactive = true and
    #                                                                                d.inactive_date < current_date and
    #                                                                                d.company_id =b.company_id))""",
    #                                             (hsn_code,),
    #                                             data_hsn_all_ids)
    #                         all_taxes = self.env.cr.dictfetchall()
    #                         # print("ALL TAXES after query", all_taxes)
    #                         if all_taxes:
    #                             for val in all_taxes:
    #                                 tax_detail_id = val.get('id')
    #                                 tax_list.append(tax_detail_id)
    #                     # print("TAXXXXXXXXXXX",tax_list)
    #                     # self.vendor_tax_lines=[(6, 0, tax_list)]
    #                     vendor_tax_tup_list = []
    #                     customer_tax_tup_list = []
    #                     for line in self.env['tax.master.details'].browse(tax_list):
    #                         if line.tax_id.type_tax_use == 'purchase':
    #                             vendor_taxes_tup = (0, False, {
    #                                 'tax_id': line.tax_id.id,
    #                                 'tax_group_id': line.tax_group_id.id,
    #                                 'tax_percentage': line.tax_percentage,
    #                                 'label': line.label,
    #                                 'from_date': line.from_date,
    #                                 'tax_master_detail_id': line.id or False,
    #                             })
    #                             vendor_tax_tup_list.append(vendor_taxes_tup)
    #                     # print ("vedor tax linessssssssssss",vendor_tax_tup_list,self.hsn_id.hsn_code,customer_tax_tup_list)
    #                     # ravi at 11/5/2019 start
    #                     if self.purchase_ok:
    #                         self.vendor_tax_lines = vendor_tax_tup_list


class ProductProduct(models.Model):
    _inherit = "product.product"

    vendor_tax_lines = fields.One2many(
        'vendor.tax.line', string="Vendor Taxes", compute="_compute_vendor_tax_ids", )
    customer_tax_lines = fields.One2many(
        'customer.tax.line', string="Customer Taxes", compute="_compute_customer_tax_ids", )


    @api.depends('product_tmpl_id', 'product_tmpl_id.vendor_tax_lines')
    def _compute_vendor_tax_ids(self):
        for p in self:
            if p.product_tmpl_id.vendor_tax_lines :
                tax_list=[]
                print ("p.product_tmpl_id.vendor_tax_lines",p.product_tmpl_id.vendor_tax_lines)
                for tax in p.product_tmpl_id.vendor_tax_lines :
                    tax_list.append(tax.id)
                # p.vendor_tax_lines = p.product_tmpl_id.vendor_tax_lines
                p.vendor_tax_lines = [(6,0,tax_list)]

    @api.depends('product_tmpl_id', 'product_tmpl_id.customer_tax_lines')
    def _compute_customer_tax_ids(self):
        for p in self:
            if p.product_tmpl_id.customer_tax_lines:
                tax_list = []
                print ("p.product_tmpl_id.customer_tax_lines", p.product_tmpl_id.customer_tax_lines)
                for tax in p.product_tmpl_id.customer_tax_lines:
                    tax_list.append(tax.id)
                # p.vendor_tax_lines = p.product_tmpl_id.vendor_tax_lines
                p.customer_tax_lines = [(6, 0, tax_list)]


class VendorTaxLine(models.Model):
    _name = 'vendor.tax.line'

    @api.model
    def _default_tax_group(self):
        # print("HHHHHHHHHHHHHHHHH", self.env['account.tax'].search(['id','=',self.tax_id.tax_group_id.id], limit=1))
        return self.env['account.tax.group'].search(['id','=',self.tax_id.tax_group_id.id])

    tax_id = fields.Many2one('account.tax', string='Tax Name', required='True')
    tax_group_id = fields.Many2one('account.tax.group', string="Tax Type", required=True)
    # Aman 15/10/2020 Made tax_percentage field float
    tax_percentage = fields.Float('Percentage')
    label = fields.Char('Label')
    # Aman 18/08/2020 Added these fields to show in product form in receivables tree view. Made these fields related
    # through tax.master.details table
    # Ticket - 353 Aman 17/12/2020 Need to remove logic of relation fields of Income account and expense accounts between Taxes to
    # HSN and HSN to product because it is impacting vice versa
    # income_account = fields.Many2one(string='Income Account', related='tax_id.income_account_id')
    # income_account_export = fields.Many2one(string='Income Account Export', related='tax_id.income_account_export_id')
    # expense_account = fields.Many2one(string='Expense Account', related='tax_id.expense_account_id')
    income_account = fields.Many2one('account.account', string='Income Account')
    income_account_export = fields.Many2one('account.account', string='Income Account Export')
    expense_account = fields.Many2one('account.account', string='Expense Account')
    # Aman end
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    template_id = fields.Many2one('product.template',  string='Tax Details')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                  default = lambda self: self.env.user.company_id.id)
    tax_master_detail_id = fields.Many2one('tax.master.details', string='Tax Master Detail')

    @api.onchange('tax_id')
    def onchange_tax_percentage(self):
        if self.tax_id:
            if self.tax_id.amount_type == 'percent':
                self.tax_percentage = self.tax_id.amount
            if self.tax_id.children_tax_ids:
                percent = 0.0
                for val in self.tax_id.children_tax_ids:
                    if val.amount_type == 'percent':
                        percent = val.amount
                self.tax_percentage = percent
            self.label = self.tax_id.name
            self.tax_group_id = self.tax_id.tax_group_id
            # Aman 22/12/2020 Assign accounts value from hsn table
            self.income_account = self.tax_id.income_account_id
            self.income_account_export = self.tax_id.income_account_export_id
            self.expense_account = self.tax_id.expense_account_id
            self.from_date = datetime.now()
            # Aman end

    @api.model
    def create(self, vals):
        res = super(VendorTaxLine, self).create(vals)
        if res.tax_master_detail_id:
            res.tax_master_detail_id.write({'state': 'used'})
        return res

class CustomerTaxLine(models.Model):
    _name = 'customer.tax.line'

    @api.model
    def _default_tax_group(self):
        return self.env['account.tax.group'].search ([], limit=1)

    @api.model
    def _default_tax_group(self):
        return self.env['account.tax'].search(['id','=',self.tax_id.tax_group_id.id], limit=1)

    tax_id = fields.Many2one('account.tax', string='Tax Name',required='True')
    tax_group_id = fields.Many2one('account.tax.group', string="Tax Type",  required=True)
    # Aman 15/10/2020 Made tax_percentage field float
    tax_percentage = fields.Float('Percentage')
    label = fields.Char('Label')
    # Aman 18/08/2020 Added these fields to show in product form in payables tree view. Made these fields related
    # through tax.master.details table
    # Ticket - 353 Aman 17/12/2020 Need to remove logic of relation fields of Income account and expense accounts between Taxes to
    # HSN and HSN to product because it is impacting vice versa
    # income_account = fields.Many2one(string='Income Account', related='tax_id.income_account_id')
    # income_account_export = fields.Many2one(string='Income Account Export', related='tax_id.income_account_export_id')
    # expense_account = fields.Many2one(string='Expense Account', related='tax_id.expense_account_id')
    income_account = fields.Many2one('account.account', string='Income Account')
    income_account_export = fields.Many2one('account.account', string='Income Account Export')
    expense_account = fields.Many2one('account.account', string='Expense Account')
    # Aman end
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    template_id = fields.Many2one('product.template', string='Tax Details')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                  default = lambda self: self.env.user.company_id.id)
    tax_master_detail_id = fields.Many2one('tax.master.details', string='Tax Master Detail')

    @api.onchange ('tax_id')
    def onchange_tax_percentage(self):
        if self.tax_id:
            if self.tax_id.amount_type == 'percent':
                # print ('JJJJJJJJJJJJJJJJJJ', self.tax_id.amount, self.tax_id)
                self.tax_percentage = self.tax_id.amount
            if self.tax_id.children_tax_ids:
                percent = 0.0
                for val in self.tax_id.children_tax_ids:
                    if val.amount_type == 'percent':
                        percent = val.amount
                self.tax_percentage = percent
            self.label = self.tax_id.name
            self.tax_group_id = self.tax_id.tax_group_id
            # Aman 22/12/2020 Assign accounts value from hsn table
            self.income_account = self.tax_id.income_account_id
            self.income_account_export = self.tax_id.income_account_export_id
            self.expense_account = self.tax_id.expense_account_id
            self.from_date = datetime.now()
            # Aman end

    @api.model
    def create(self, vals):
        res = super(CustomerTaxLine, self).create(vals)
        if res.tax_master_detail_id:
            res.tax_master_detail_id.write({'state': 'used'})
        return res
