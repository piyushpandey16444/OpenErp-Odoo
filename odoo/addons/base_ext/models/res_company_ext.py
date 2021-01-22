# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import os
import re

from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, UserError


class ResCompany(models.Model):
    _inherit = "res.company"

    show_transfer_master = fields.Boolean(string='Transfer Master', default=False)

    def create(self, vals):

        company = super(ResCompany, self).create(vals)

        # Show transfer master button after saving the company settings

        company.show_transfer_master = True
        print("hello",company.show_transfer_master)
        # print(a)



        return company

    def action_transfer_master_data(self):
        view = self.env.ref('base_ext.view_action_transfer_master_data')
        return {
            'name': _('Transfer Master Data'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'company.datatransfer',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            # 'res_id': self.id,
        }



class CompanyDataTransfer(models.TransientModel):
    _name = "company.datatransfer"

    want_vendors = fields.Boolean(string='Vendor Master', default=False)
    want_customers = fields.Boolean(string='Customer Master', default=False)
    want_products = fields.Boolean(string='Product Master', default=False)
    want_uom = fields.Boolean(string='Unit of Measure', default=False)
    # dup_company_id = fields.Many2one('res.company', 'Company', default= lambda self: self.env.user.company_id.id)

    import_company_id = fields.Many2one('res.company', 'Import Company', required=True)
    to_company_id = fields.Many2one('res.company', 'To Company')

    @api.model
    def default_get(self, fields):
        # getting the current form company using context as active ids
        active_ids = self._context['active_ids']

        res = super(CompanyDataTransfer, self).default_get(fields)
        if active_ids:
            browseable_active_ids = self.env['res.company'].browse(active_ids)

            if 'to_company_id' in fields and 'to_company_id' not in res:
                res['to_company_id'] = browseable_active_ids.id

        return res

    # Function transfer data called for data transfer as per selected checkbox on forms(products/customer /vendors)
    def action_transfer_data(self):

        if self.import_company_id:
            # if import company is there
            if self.want_uom == True:
                # check selected box product/uom
                # getting all data from categ table from company id
                all_from_company_uom_categ = self.env['product.uom.categ'].search([('company_id', '=', self.import_company_id.id)])
                # if data is there
                if all_from_company_uom_categ:
                    # create the data in new table
                    for categ in all_from_company_uom_categ:
                        # print("uom",uom)

                        self.env['product.uom.categ'].create({
                            'company_id' : self.to_company_id.id,
                            'name' : categ.name or '',

                                                    })

                all_from_company_uom = self.env['product.uom'].search([('company_id','=',self.import_company_id.id)])

                if all_from_company_uom:

                    for uom in all_from_company_uom:
                        all_to_company_uom_categ = self.env['product.uom.categ'].search(
                            [('name', '=', uom.category_id.name),
                                ('company_id', '=', self.to_company_id.id)])
                        category_id=False

                        print("all_to_company_uom_categ",all_to_company_uom_categ)
                        if all_to_company_uom_categ:

                            category_id = all_to_company_uom_categ[0].id or False


                        # print("uom",uom)

                        self.env['product.uom'].create({
                            'company_id' : self.to_company_id.id,
                            'name' : uom.name or '',
                            'category_id' : category_id or False,
                            'uom_type' : uom.uom_type or '',
                            'rounding' : uom.rounding or 0.0,
                                                    })

        #                 Using minus function in  sql query to check whether data already present or not
        #  validations for and on transfer button for multiple clicks


        return True





    # import_company_id = fields.Many2one('res.company', 'Import Company', compute='compute_company_domain')
    # def compute_company_domain(self):
    #
    #     result={}
    #     want_removed_company = self.dup_company_id
    #     self.env.cr.execute(""" select id from res.company""")
    #     company_dict = self.env.cr.dictfetchall()    #
    #     company_list = []
    #     if company_dict:
    #         for val in company_dict:
    #             company_list_id = val.get('id')
    #             company_list.append(company_list_id)
    #             print("company_list_listtt", company_list)    #
    #         for value in company_list:    #
    #             if value == want_removed_company.id:    #
    #                 company_list.remove(value)    #
    #                 self.import_company_id = company_list  #    #
    #                 result = {'domain': {'import_company_id': [('id', 'in', company_list)]}}
    #
    #     return result







