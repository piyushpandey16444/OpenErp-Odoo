import json
import re
import uuid
from functools import partial

from lxml import etree
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _
from odoo.tools import float_is_zero, float_compare, pycompat
from odoo.tools.misc import formatLang
from odoo.addons.account.models import genric

from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning

from odoo.addons import decimal_precision as dp


class AccountInvoiceLine(models.Model):
    _inherit = "account.invoice.line"


    def _set_taxes(self):
        """ Used in on_change to set taxes and price."""
        # print ("set account account taxessssssssss")
        # Gaurav 12/3/20 added code for default tax state wise
        check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
        check_custmr_state = self.env['res.partner'].search(
            [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
        print("partner_shipping_id", self.invoice_id.partner_shipping_id)
        # getting and checking whether invoice type is out=sale or in=purchase
        if self.invoice_id.type in ('out_invoice', 'out_refund'):
            #Jatin change for taxes to pick from customer_tax_lines on 11-07-2020
            filter_tax = []
            for val in self:
                check = val.product_id.customer_tax_lines
                print("check", check)
                for rec in check:
                    tax_check = rec.tax_id.id
                    print(tax_check)
                    filter_tax.append(tax_check)
                print('filter_tax', filter_tax)

            print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
            print("print_tax in function", print_tax)
            taxes = print_tax or self.account_id.tax_ids
            #end Jatin

            account_type = 'sale'
            state_type=self.invoice_id.partner_shipping_id.state_id
        else:
            #Jatin change for taxes to pick from customer_tax_lines on 11-07-2020
            filter_tax = []
            for val in self:
                check = val.product_id.vendor_tax_lines
                print("check", check)
                for rec in check:
                    tax_check = rec.tax_id.id
                    print(tax_check)
                    filter_tax.append(tax_check)
                print('filter_tax', filter_tax)

            print_tax = self.env['account.tax'].search([('id', 'in', filter_tax)])
            print("print_tax in function", print_tax)
            taxes = print_tax or self.account_id.tax_ids
            # end Jatin
            # taxes = self.product_id.supplier_taxes_id or self.account_id.tax_ids or self.product_id.taxes_id
            account_type = 'purchase'
            state_type = check_custmr_state.state_id

        # taxes = self.product_id.taxes_id.filtered(lambda r: not self.company_id or r.company_id == self.company_id)

        # Keep only taxes of the company
        company_id = self.company_id or self.env.user.company_id
        taxes = taxes.filtered(lambda r: r.company_id == company_id)

        taxes_ids_list = taxes.ids



        if check_cmpy_state.state_id == state_type:
            print("state_type_id", state_type)
            print("same all account_type",account_type)
            self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='%s' AND tax_group_id not in (2,3) and company_id='%s'""" % (account_type,self.env.user.company_id.id,))
            csgst_taxes = self.env.cr.dictfetchall()
            final = [taxes_ids_list.remove(val.get('id')) for val in csgst_taxes if val.get('id') in taxes_ids_list if csgst_taxes]
            # tax_list = []
            # # tax_id_list = [tax.id for tax in taxes_id]
            # tax_id_list = taxes.ids
            # if csgst_taxes:
            #     for val in csgst_taxes:
            #         tax_detail_id = val.get('id')
            #         tax_list.append(tax_detail_id)
            # print("the all value int eh tax ilist", tax_list)
            # for value in tax_list:
            #     if value in tax_id_list:
            #         tax_id_list.remove(value)
            #         print("all tax", tax_id_list)
            # # for value in tax_id_list:
            # #     if value in tax_list:
            # #         tax_id_list.remove(value)
            # #         print("tax",tax_id_list)
            # print("account all finalvvvvvvvvvvvvvvvv", tax_id_list)
            print(" account account finalvvvvvvvvvvvvvvvv",final)

            self.invoice_line_tax_ids = taxes_ids_list

        elif check_cmpy_state.state_id != state_type:
            print("state_type_id", state_type)
            print("diff account_type",account_type)
            self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='%s' AND tax_group_id!=4 and company_id='%s'""" % (account_type,self.env.user.company_id.id,))
            igst_taxes = self.env.cr.dictfetchall()
            final = [taxes_ids_list.remove(val.get('id')) for val in igst_taxes if val.get('id') in taxes_ids_list if igst_taxes]
            print(" account account finalvvvvvvvvvvvvvvvv",final)

            self.invoice_line_tax_ids = taxes_ids_list


        # self.invoice_line_tax_ids = fp_taxes = self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id, self.invoice_id.partner_id)
        fp_taxes=self.invoice_id.fiscal_position_id.map_tax(taxes, self.product_id, self.invoice_id.partner_id)
        # self.invoice_line_tax_ids=[]
        fix_price = self.env['account.tax']._fix_tax_included_price
        if self.invoice_id.type in ('in_invoice', 'in_refund'):
            prec = self.env['decimal.precision'].precision_get('Product Price')
            if not self.price_unit or float_compare(self.price_unit, self.product_id.standard_price, precision_digits=prec) == 0:
                self.price_unit = fix_price(self.product_id.standard_price, taxes, fp_taxes)
                # self.price_unit = fix_price(self.product_id.standard_price, taxes)
                self._set_currency()
        else:
            self.price_unit = fix_price(self.product_id.lst_price, taxes, fp_taxes)
            # self.price_unit = fix_price(self.product_id.lst_price, taxes)
            self._set_currency()

        # Gaurav return domain
        return {'domain': {'invoice_line_tax_ids': [final]}}



    @api.onchange('product_id')
    def _onchange_product_id(self):
        # Aman 30/12/2020 Added condition and user error to check if product with
        # hsn_disable = True is selected in last or not
        if self.invoice_id.invoice_line_ids:
            if self.product_id:
                if self.invoice_id.invoice_line_ids[0].product_id.hsn_disable == True:
                    raise UserError(_("This item should be selected in the end!!"))
        # Aman end
        print ("DDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDDD")
        domain = {}
        result={}
        if not self.invoice_id:
            return

        self.invoice_line_tax_ids=''

        part = self.invoice_id.partner_id
        fpos = self.invoice_id.fiscal_position_id
        company = self.invoice_id.company_id
        currency = self.invoice_id.currency_id
        type = self.invoice_id.type

        if not part:
            warning = {
                    'title': _('Warning!'),
                    'message': _('You must first select a partner!'),
                }
            return {'warning': warning}

        if not self.product_id:
            if type not in ('in_invoice', 'in_refund'):
                self.price_unit = 0.0
            domain['uom_id'] = []
        else:
            if part.lang:
                product = self.product_id.with_context(lang=part.lang)
            else:
                product = self.product_id

            self.name = product.partner_ref
            # account = self.get_invoice_line_account(type, product, fpos, company)
            # if account:
            #     self.account_id = account.id

            # Gaurav commented _set_taxes function for GST validation and used below with changes in function itself
            # self._set_taxes()

            if type in ('in_invoice', 'in_refund'):
                if product.description_purchase:
                    self.name += '\n' + product.description_purchase
            else:
                if product.description_sale:
                    self.name += '\n' + product.description_sale

            if not self.uom_id or product.uom_id.category_id.id != self.uom_id.category_id.id:
                self.uom_id = product.uom_id.id
            domain['uom_id'] = [('category_id', '=', product.uom_id.category_id.id)]

            # Gaurav commented _set_taxes function for GST validation and used below with changes in function itself

            check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            check_custmr_state = self.env['res.partner'].search(
                [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            print("partner_shipping_id", self.invoice_id.partner_shipping_id)
            check_partner = self.env['res.partner'].search([('id', '=', self.partner_id.id)])

            print("self.env.user.company_id.vattttttttttttttttttttttt", check_partner.name, check_partner.vat)

            if self.invoice_id.type in ('out_invoice', 'out_refund'):
                account_type = 'sale'
                state_type = self.invoice_id.partner_shipping_id.state_id

                # Gaurav 12/3/20 added validation for GST check (if company is unregistered then don't add taxes if registered then add taxes state wise)
                if self.env.user.company_id.vat:

                    # check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
                    # check_custmr_state = self.env['res.partner'].search(
                    #     [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
                    # print("partner_shipping_id", self.invoice_id.partner_shipping_id)
                    #
                    # if self.invoice_id.type in ('out_invoice', 'out_refund'):
                    #     account_type = 'sale'
                    #     state_type = self.invoice_id.partner_shipping_id.state_id
                    # else:
                    #     account_type = 'purchase'
                    #     state_type = check_custmr_state.state_id

                    # GST present , company registered
                    # Gaurav 12/3/20 added code for default tax state wise
                    # check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
                    # check_custmr_state = self.env['res.partner'].search(
                    #     [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
                    # checking company state and customer state is same or not
                    if check_cmpy_state.state_id == state_type:
                        # Aman 30/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                        # of the item with greatest tax
                        if product.hsn_disable == True:
                            group_type = ('CGST', 'SGST')
                            taxes_cust = genric.get_taxes(self, product, group_type, cust_invoice=True)
                            self.invoice_line_tax_ids = taxes_cust
                        # Aman end
                        else:
                            print("new func same")
                            # if same states show taxes like CGST SGST GST
                            self.env.cr.execute(
                                """select id from account_tax where active=True and type_tax_use='%s' and tax_group_id!=4 and company_id='%s'""" % (
                                account_type, self.env.user.company_id.id,))
                            csgst_taxes = self.env.cr.dictfetchall()
                            print("new all account account csgst_taxessssss", csgst_taxes)
                            self._set_taxes()
                            cs_tax_list = []
                            if csgst_taxes:
                                for val in csgst_taxes:
                                    tax_detail_idcs = val.get('id')
                                    aa = self.env['account.tax'].browse(tax_detail_idcs)
                                    print("AAAAAAAAAAAAAAAAAAAAAAAA", aa.type_tax_use)
                                    cs_tax_list.append(tax_detail_idcs)
                                    print("latest new cs_tax_listttt", cs_tax_list)
                                    self.invoice_line_tax_new_ids = cs_tax_list
                                    # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                                    result = {'domain': {'invoice_line_tax_ids': [('id', 'in', cs_tax_list)]}}

                    elif check_cmpy_state.state_id != state_type:
                        # Aman 30/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                        # of the item with greatest tax
                        if product.hsn_disable == True:
                            group_type = ('IGST')
                            taxes_cust = genric.get_taxes(self, product, group_type, cust_invoice=True)
                            self.invoice_line_tax_ids = taxes_cust
                        # Aman end
                        else:
                            print("new func diff")
                            # if different states show taxes like IGST
                            self.env.cr.execute(
                                """ select id from account_tax where active=True and type_tax_use='%s' and tax_group_id not in (2,3) and company_id='%s'""" % (
                                account_type, self.env.user.company_id.id,))
                            igst_taxes = self.env.cr.dictfetchall()
                            self._set_taxes()
                            i_tax_list = []
                            if igst_taxes:
                                for val in igst_taxes:
                                    tax_detail_idi = val.get('id')
                                    i_tax_list.append(tax_detail_idi)
                                    print("latest new account account i_tax_listtttt", i_tax_list)
                                    self.invoice_line_tax_new_ids = i_tax_list

                                    result = {'domain': {'invoice_line_tax_ids': [('id', 'in', i_tax_list)]}}


            else:
                account_type = 'purchase'
                state_type = check_custmr_state.state_id

                # Gaurav 12/3/20 added validation for GST check (if company is unregistered then don't add taxes if registered then add taxes state wise)
                if check_partner.vat:

                    # check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
                    # check_custmr_state = self.env['res.partner'].search(
                    #     [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
                    # print("partner_shipping_id", self.invoice_id.partner_shipping_id)
                    #
                    # if self.invoice_id.type in ('out_invoice', 'out_refund'):
                    #     account_type = 'sale'
                    #     state_type = self.invoice_id.partner_shipping_id.state_id
                    # else:
                    #     account_type = 'purchase'
                    #     state_type = check_custmr_state.state_id

                    # GST present , company registered
                    # Gaurav 12/3/20 added code for default tax state wise
                    # check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
                    # check_custmr_state = self.env['res.partner'].search(
                    #     [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
                    # checking company state and customer state is same or not
                    if check_cmpy_state.state_id == state_type:
                        # Aman 30/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                        # of the item with greatest tax
                        if product.hsn_disable == True:
                            group_type = ('CGST', 'SGST')
                            taxes_cust = genric.get_taxes(self, product, group_type, vendor_bill=True)
                            self.invoice_line_tax_ids = taxes_cust
                        # Aman end
                        else:
                            print("new func same")
                            # if same states show taxes like CGST SGST GST
                            self.env.cr.execute(
                                """select id from account_tax where active=True and type_tax_use='%s' and tax_group_id!=4 and company_id='%s'""" % (
                                account_type, self.env.user.company_id.id,))
                            csgst_taxes = self.env.cr.dictfetchall()
                            print("new all account account csgst_taxessssss", csgst_taxes)
                            self._set_taxes()
                            cs_tax_list = []
                            if csgst_taxes:
                                for val in csgst_taxes:
                                    tax_detail_idcs = val.get('id')
                                    aa = self.env['account.tax'].browse(tax_detail_idcs)
                                    print("AAAAAAAAAAAAAAAAAAAAAAAA", aa.type_tax_use)
                                    cs_tax_list.append(tax_detail_idcs)
                                    print("latest new cs_tax_listttt", cs_tax_list)
                                    self.invoice_line_tax_new_ids = cs_tax_list
                                    # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                                    result = {'domain': {'invoice_line_tax_ids': [('id', 'in', cs_tax_list)]}}

                    elif check_cmpy_state.state_id != state_type:
                        # Aman 30/12/2020 Added condition to check if product with hsn_disable = True must pick tax
                        # of the item with greatest tax
                        if product.hsn_disable == True:
                            group_type = ('IGST')
                            taxes_cust = genric.get_taxes(self, product, group_type, vendor_bill=True)
                            self.invoice_line_tax_ids = taxes_cust
                        # Aman end
                        else:
                            print("new func diff")
                            # if different states show taxes like IGST
                            self.env.cr.execute(
                                """ select id from account_tax where active=True and type_tax_use='%s' and tax_group_id not in (2,3) and company_id='%s'""" % (
                                account_type, self.env.user.company_id.id,))
                            igst_taxes = self.env.cr.dictfetchall()
                            self._set_taxes()
                            i_tax_list = []
                            if igst_taxes:
                                for val in igst_taxes:
                                    tax_detail_idi = val.get('id')
                                    i_tax_list.append(tax_detail_idi)
                                    print("latest new account account i_tax_listtttt", i_tax_list)
                                    self.invoice_line_tax_new_ids = i_tax_list

                                    result = {'domain': {'invoice_line_tax_ids': [('id', 'in', i_tax_list)]}}

                else:
                    # checking company state and customer state is same or not
                    if check_cmpy_state.state_id == state_type:
                        # if same states show taxes like CGST SGST GST
                        self.env.cr.execute(
                            """select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id!=4 and company_id='%s'""" % (
                                self.env.user.company_id.id,))
                        csgst_taxes = self.env.cr.dictfetchall()
                        print("purchase csgst_taxessssss", csgst_taxes)
                        # self._set_taxes()
                        # self._compute_purchase_tax()
                        cs_tax_list = []
                        if csgst_taxes:
                            for val in csgst_taxes:
                                tax_detail_idcs = val.get('id')
                                cs_tax_list.append(tax_detail_idcs)
                                print("cs_tax_listttt", cs_tax_list)
                                # self.update({'tax_id': [(6, 0, cs_tax_list)]})
                                result = {'domain': {'invoice_line_tax_ids': [('id', 'in', cs_tax_list)]}}


                    elif check_cmpy_state.state_id != state_type:
                        # if different states show taxes like IGST
                        self.env.cr.execute(
                            """ select id from account_tax where active=True and type_tax_use='purchase' and tax_group_id not in (2,3) and company_id='%s'""" % (
                                self.env.user.company_id.id,))
                        igst_taxes = self.env.cr.dictfetchall()
                        # self._set_taxes()
                        # self._compute_purchase_tax()
                        i_tax_list = []
                        if igst_taxes:
                            for val in igst_taxes:
                                tax_detail_idi = val.get('id')
                                i_tax_list.append(tax_detail_idi)
                                print("purchase i_tax_listtttt", i_tax_list)
                                result = {'domain': {'invoice_line_tax_ids': [('id', 'in', i_tax_list)]}}

            # # Gaurav 12/3/20 added validation for GST check (if company is unregistered then don't add taxes if registered then add taxes state wise)
            # if self.env.user.company_id.vat:
            #
            #     # check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            #     # check_custmr_state = self.env['res.partner'].search(
            #     #     [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            #     # print("partner_shipping_id", self.invoice_id.partner_shipping_id)
            #     #
            #     # if self.invoice_id.type in ('out_invoice', 'out_refund'):
            #     #     account_type = 'sale'
            #     #     state_type = self.invoice_id.partner_shipping_id.state_id
            #     # else:
            #     #     account_type = 'purchase'
            #     #     state_type = check_custmr_state.state_id
            #
            #     # GST present , company registered
            #     # Gaurav 12/3/20 added code for default tax state wise
            #     # check_cmpy_state = self.env['res.company'].search([('partner_id', '=', self.env.user.company_id.id)])
            #     # check_custmr_state = self.env['res.partner'].search(
            #     #     [('id', '=', self.partner_id.id), ('company_id', '=', self.env.user.company_id.id)])
            #     # checking company state and customer state is same or not
            #     if check_cmpy_state.state_id == state_type:
            #         print("new func same")
            #         # if same states show taxes like CGST SGST GST
            #         self.env.cr.execute("""select id from account_tax where active=True and type_tax_use='%s' and tax_group_id!=4 and company_id='%s'""" % (account_type,self.env.user.company_id.id,))
            #         csgst_taxes = self.env.cr.dictfetchall()
            #         print("new all account account csgst_taxessssss", csgst_taxes)
            #         self._set_taxes()
            #         cs_tax_list = []
            #         if csgst_taxes:
            #             for val in csgst_taxes:
            #                 tax_detail_idcs = val.get('id')
            #                 aa = self.env['account.tax'].browse(tax_detail_idcs)
            #                 print ("AAAAAAAAAAAAAAAAAAAAAAAA",aa.type_tax_use)
            #                 cs_tax_list.append(tax_detail_idcs)
            #                 print("latest new cs_tax_listttt", cs_tax_list)
            #                 self.invoice_line_tax_new_ids = cs_tax_list
            #                 # self.update({'tax_id': [(6, 0, cs_tax_list)]})
            #                 result= {'domain': {'invoice_line_tax_ids': [('id', 'in', cs_tax_list)]}}
            #
            #     elif check_cmpy_state.state_id != state_type:
            #         print("new func diff")
            #         # if different states show taxes like IGST
            #         self.env.cr.execute(""" select id from account_tax where active=True and type_tax_use='%s' and tax_group_id not in (2,3) and company_id='%s'""" % (account_type,self.env.user.company_id.id,))
            #         igst_taxes = self.env.cr.dictfetchall()
            #         self._set_taxes()
            #         i_tax_list = []
            #         if igst_taxes:
            #             for val in igst_taxes:
            #                 tax_detail_idi = val.get('id')
            #                 i_tax_list.append(tax_detail_idi)
            #                 print("latest new account account i_tax_listtttt", i_tax_list)
            #                 self.invoice_line_tax_new_ids=i_tax_list
            #
            #                 result= {'domain': {'invoice_line_tax_ids': [('id', 'in', i_tax_list)]}}

            # Gaurav end
            account = self.get_invoice_line_account(type, product, fpos, company)
            if account:
                self.account_id = account.id
            if company and currency:

                if self.uom_id and self.uom_id.id != product.uom_id.id:
                    self.price_unit = product.uom_id._compute_price(self.price_unit, self.uom_id)
        # return {'domain': domain}
        print("account ext return account main",result)
        return result

class AccountAccount(models.Model):
    _inherit='account.account'

    gst_applicable = fields.Boolean('Is GST Applicable')
    taxes = fields.Many2one('account.tax')
    nat_trans=fields.Many2one('nature.transaction')
    check_group_id=fields.Boolean()

    @api.onchange('group_id','user_type_id','gst_applicable')
    def check_for_nature(self):
        self.nat_trans=False
        if self.group_id:
            if self.group_id.name =='Duties & Taxes':
                self.check_group_id = True

class NatureTransaction(models.Model):
    _name = 'nature.transaction'

    name = fields.Char(string='Name')
    # group_id=fields.Many2many('account.group')
    # account_type=fields.Many2many('account.account.type')
