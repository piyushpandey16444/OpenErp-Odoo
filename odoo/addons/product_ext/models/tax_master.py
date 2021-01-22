import itertools
import psycopg2
from odoo import api, fields, models, tools, _
from odoo.exceptions import ValidationError, RedirectWarning, except_orm
from odoo.tools import pycompat
from odoo.addons import decimal_precision as dp
from datetime import datetime
import re



class TaxMaster(models.Model):
    _name = "tax.master"
    _description = "Tax Master"

    @api.multi
    @api.constrains('name')
    def _check_unique_name(self):
        """
        Check Name should be unique
        """
        for line in self:
            all_temp_list = []
            # all_temp = line.env['product.uom'].search(
            #     [('company_id', '=', line.env.user.company_id.id)])
            # print ("both copanyyyyyyyy", line.company_id.name, line.env.user.company_id.name)
            all_temp = line.env['tax.master'].search(
                [('company_id', '=', line.company_id.id)])
            if all_temp:
                all_temp_list = [temp_val.name.lower().lstrip().rstrip() for temp_val in all_temp]
            name = line.name.lower().lstrip().rstrip()
            if name in all_temp_list:
                if all_temp_list.count(name) > 1:
                    raise ValidationError(
                        _('HSN Code : %s already exist for company : %s !') % (name, line.company_id.name))

    name = fields.Char('Tax Master HSN')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)

    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)

    template_id = fields.Many2one('product.template', string='Tax Details')
    hsn_code = fields.Char('HSN Code')
    tax_master_id = fields.One2many('tax.master.details', 'tax_master_details_id', string='Tax Details')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('used', 'Used in Product'),
    ], "Status", track_visibility='onchange', default='draft', )
    active = fields.Boolean('Active', default=True)
    description = fields.Text('Description')

    @api.multi
    @api.depends('hsn_code')
    def name_get(self):
        res = []
        for record in self:
            if record.hsn_code:
                name = record.hsn_code
            else:
                name = '/'
            res.append((record.id, name))
        return res

    @api.model
    def create(self, vals):
        if 'hsn_code' in vals:
            vals['name'] = vals['hsn_code']
        res = super(TaxMaster, self).create(vals)
        return res

    @api.multi
    def write(self, vals):
        if 'hsn_code' in vals:
            vals['name'] = vals['hsn_code']
        res = super(TaxMaster, self).write(vals)
        return res

    # Duplicate Taxes of same Date comparison in taxes
    # 	@api.model
    # 	def create(self, vals):
    # 		res = super(TaxMaster, self).create (vals)
    # 		val1 = []
    # 		val2 = []
    # 		if res.tax_master_id:
    # 			for val in res.tax_master_id:
    # 				val1.append(val.tax_id)
    # 				val2.append(val.from_date)
    # 				dictt = dict(zip(val1,val2))
    # 				for val1, val2 in dictt.items ():
    # 						rev_multidict.setdefault (val2, set ()).add (val1)
    # 				print("Dict", dict)
    # 	if val.from_date == val.from_date:
    # 		raise ValidationError("Lines Cannot have same Date")
    # return res

    # @api.multi
    # def write(self, vals):
    # 	res = super (TaxMaster, self).write(vals)
    #
    # 	if res.tax_master_id:
    # 		for val in res.tax_master_id:
    # 			print("VALLLLLLLLLL", val.tax_id)
    # 			print("VALLLLLLLLLL2222", val.from_date)
    # 		# if res.hsn_code:
    # 		# 	print("HHHHHHHHHHHHHHHHHH", hsn_code)
    # 		# 	tax_details = []
    # 		# 	for val in res.tax_master_details_id:
    # 		# 		if val.from_date > val.cr_date:
    # 		# 			print("HHHHHHHHHHHH", tax_details)
    # 		# 			raise ValidationError ("Check the dates")
    # 		# 		tax_details.append (val.id)
    # 		# 		print("HHHHHHHHHHHH", tax_details)
    # 		# 		if res.from_date > res.cr_date:
    # 		# 			raise ValidationError (
    # 		# 				'No two taxes with same dates !')
    # 		# 		else:
    # 		# 			raise ValidationError ('Define HSN first')
    # 			return res

    # HSN Code Validation and Unique check
    @api.multi
    @api.constrains('hsn_code')
    def _check_unique_hsn(self):
        # company_id = self.env.user.company_id.id
        if self.hsn_code:
            if len(self.hsn_code) > 8 or len(self.hsn_code) < 2:
                raise ValidationError(_(' HSN Code should not be less than 2 digits and greater than 8 digits and !'))
            if not self.hsn_code.isdigit():
                raise ValidationError(_(' HSN Code contains only Integers!'))

    @api.multi
    @api.onchange('hsn_code')
    def _onchange_hsn_code(self):
        for temp in self:
            all_temp = self.env['tax.master'].search(
                [('hsn_code', '=', temp.hsn_code)])
            if len(all_temp) > 1:
                raise ValidationError(_('Taxes already defined for HSN Code : %s ') % temp.hsn_code)

    def update_hsn_account(self):
        var = self.env['account.tax'].search([])
        for i in var:
            var1 = self.env['tax.master.details'].search([('tax_id', '=', i.id)])
            for j in var1:
                dict = {
                    'income_account': i.income_account_id.id,
                    'income_account_export': i.income_account_export_id.id,
                    'expense_account': i.expense_account_id.id,
                }
                j.write(dict)
        varr = self.env['tax.master.details'].search([])
        for k in varr:
            var2 = self.env['customer.tax.line'].search([('tax_master_detail_id', '=', k.id)])
            var3 = self.env['vendor.tax.line'].search([('tax_master_detail_id', '=', k.id)])
            for a in var2:
                dict = {
                    'income_account': k.income_account.id,
                    'income_account_export': k.income_account_export.id,
                    'expense_account': k.expense_account.id,
                }
                a.write(dict)
            for b in var3:
                dict = {
                    'income_account': k.income_account.id,
                    'income_account_export': k.income_account_export.id,
                    'expense_account': k.expense_account.id,
                }
                b.write(dict)

class TaxMasterDetails(models.Model):
    _name = "tax.master.details"
    _description = "Tax Master"

    # @api.model
    # def _default_tax_group(self):
    # 	return self.env['account.tax.group'].search (['id', '=', self.tax_id.tax_group_id.id])

    tax_id = fields.Many2one('account.tax', string='Tax Name', required='True')
    cr_date = fields.Date(string='Create Date', required=True, readonly=True, index=True, copy=False,
                          default=fields.Datetime.now)
    tax_group_id = fields.Many2one('account.tax.group', string="Tax Type", required=True)
    # Aman 15/10/2020 Made tax_percentage field float
    tax_percentage = fields.Float('Percentage')
    label = fields.Char('Label')
    from_date = fields.Date('From Date')
    to_date = fields.Date('To Date')
    template_id = fields.Many2one('product.template', string='Tax Details')
    hsn_code = fields.Char('HSN Code')
    inactive = fields.Boolean('In-active')
    inactive_date = fields.Date('In-active From')
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    tax_master_details_id = fields.Many2one('tax.master', string="Tax Details")
    # state = fields.Selection('State',related='tax_master_details_id.state',default='draft')
    state = fields.Selection([
        ('draft', 'Draft'),
        ('used', 'Used in Product'),
    ], "Status", track_visibility='onchange', default='draft', )
    type_tax_use = fields.Selection([('sale', 'Sales'), ('purchase', 'Purchases'), ('none', 'None')],
                                    string='Tax Scope', required=True, default="sale",
                                    help="Determines where the tax is selectable. Note : 'None' means a tax can't be used by itself, however it can still be used in a group.")
    updated_date = fields.Datetime(string='Updated Date', readonly=True, index=True, copy=False,
                                   default=fields.Datetime.now)
    # Aman 18/08/2020 added 3 fields to enter income account and expense account in tree view. Made these fields
    # related through account.tax table
    # Ticket - 353 Aman 17/12/2020 Need to remove logic of relation fields of Income account and expense accounts between Taxes to
    # HSN and HSN to product because it is impacting vice versa
    # income_account = fields.Many2one(string='Income Account', related='tax_id.income_account_id')
    # income_account_export = fields.Many2one(string='Income Account Export', related='tax_id.income_account_export_id')
    # expense_account = fields.Many2one(string='Expense Account', related='tax_id.expense_account_id')
    income_account = fields.Many2one('account.account', string='Income Account')
    income_account_export = fields.Many2one('account.account', string='Income Account Export')
    expense_account = fields.Many2one('account.account', string='Expense Account')

    # Aman end

    @api.multi
    @api.onchange('inactive_date', 'from_date')
    # @api.depends('inactive','inactive_date','from_date')
    def inactive_date_check(self):
        if self.inactive_date:
            if self.from_date:
                if self.inactive_date <= self.from_date:
                    raise ValidationError("Tax's In-active Date can not be more than Tax's From Date")

    @api.multi
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
            self.type_tax_use = self.tax_id.type_tax_use
            # Aman 18/08/2020 Set the value of account on selection of tax
            self.income_account = self.tax_id.income_account_id
            self.income_account_export = self.tax_id.income_account_export_id
            self.expense_account = self.tax_id.expense_account_id
            # Aman end

    # Validation On Taxes 26 March 2019
    @api.model
    def create(self, vals):
        # print ("vals in tax master detauls vals",vals)
        if 'tax_id' in vals:
            # print ("tax iddddddddddd in create",vals,vals['tax_master_details_id'])
            tax_master_id_check = self.env['tax.master.details'].search(
                [('tax_id', '=', vals['tax_id']), ('tax_master_details_id', '=', vals['tax_master_details_id'])],
                order="from_date asc")
            print("tax_master_id_checkkkkkkkkkkkkk", tax_master_id_check)
            if tax_master_id_check:
                for val in tax_master_id_check:
                    # print ("HHHHHHHHHH",val.from_date , vals['from_date'])
                    if val.from_date > vals['from_date']:
                        raise ValidationError("From Date of the new tax has to be more than the last valid Date.")
        if 'tax_group_id' in vals and 'type_tax_use' in vals:
            # print ("tax iddddddddddd in create",vals,vals['tax_master_details_id'])
            tax_master_id_check = self.env['tax.master.details'].search(
                [('tax_group_id', '=', vals['tax_group_id']), ('type_tax_use', '=', vals['type_tax_use']),
                 ('tax_master_details_id', '=', vals['tax_master_details_id'])],
                order="from_date asc")
            # print("tax_master_id_checkkkkkkkkkkkkk", tax_master_id_check)
            if tax_master_id_check:
                for val in tax_master_id_check:
                    # print ("HHHHHHHHHH",val.from_date , vals['from_date'])
                    if vals['from_date'] and val.from_date > vals['from_date']:
                        raise ValidationError("From Date of the new tax has to be more than the last valid Date.")
        # print ("aaaaaaaaaaaa", a)
        res = super(TaxMasterDetails, self).create(vals)

        # list1 = tax_master_id_check.ids
        # if len(tax_master_id_check) > 1:
        # 	raise ValidationError(_('Kindly check your Taxes Validity !'))
        # if 'tax_id' in vals and vals['tax_id']:
        # 	tax_ids = self.env['tax.master.details'].browse(vals['tax_id'])
        # 	vals['tax_id'] = tax_ids
        # 	vals['from_date'] = tax_ids.from_date
        # 	print("Runningggg ",vals['from_date'],vals['tax_id'])
        return res

    @api.multi
    def write(self, vals):
        # print ("valsssssssssssss",vals)
        if 'inactive' in vals or 'from_date' in vals:
            vals['updated_date'] = datetime.now()

        res = super(TaxMasterDetails, self).write(vals)
        if 'tax_id' in vals and 'from_date' in vals:
            # tax_master_id_check = self.env['tax.master.details'].search (
            # 	[('tax_id', '=', vals['tax_id']), ('tax_master_details_id', '=', vals['tax_master_details_id'])],
            # 	order="from_date asc", limit=100)
            tax_master_id_check = self.env['tax.master.details'].search(
                [('tax_id', '=', vals['tax_id']), ('tax_master_details_id', '=', self.tax_master_details_id.id)],
                order="from_date asc")
            # print("tax_master_id_checkkkkkkkkkkkkk", tax_master_id_check)
            if tax_master_id_check:
                for val in tax_master_id_check:
                    # print ("HHHHHHHHHH", val.from_date, vals['from_date'])
                    if val.from_date > vals['from_date']:
                        raise ValidationError("From Date of the new tax has to be more than the last valid Date.")
        elif 'tax_id' in vals:
            # tax_master_id_check = self.env['tax.master.details'].search (
            # 	[('tax_id', '=', vals['tax_id']), ('tax_master_details_id', '=', vals['tax_master_details_id'])],
            # 	order="from_date asc", limit=100)
            tax_master_id_check = self.env['tax.master.details'].search(
                [('tax_id', '=', vals['tax_id']), ('tax_master_details_id', '=', self.tax_master_details_id.id)],
                order="from_date asc")
            # print("tax_master_id_checkkkkkkkkkkkkk", tax_master_id_check)
            if tax_master_id_check:
                for val in tax_master_id_check:
                    # print ("HHHHHHHHHH", val.from_date, vals['from_date'])
                    if val.from_date > self.from_date:
                        raise ValidationError("From Date of the new tax has to be more than the last valid Date.")
        if 'from_date' in vals:
            # tax_master_id_check = self.env['tax.master.details'].search (
            # 	[('tax_id', '=', vals['tax_id']), ('tax_master_details_id', '=', vals['tax_master_details_id'])],
            # 	order="from_date asc", limit=100)
            tax_master_id_check = self.env['tax.master.details'].search(
                [('tax_id', '=', self.tax_id.id), ('tax_master_details_id', '=', self.tax_master_details_id.id)],
                order="from_date asc")
            print("tax_master_id_checkkkkkkkkkkkkk", tax_master_id_check)
            if tax_master_id_check:
                for val in tax_master_id_check:
                    print("HHHHHHHHHH", val.from_date, vals['from_date'])
                    if val.from_date > vals['from_date']:
                        raise ValidationError("From Date of the new tax has to be more than the last valid Date.")
        if 'tax_group_id' in vals and 'type_tax_use' in vals:
            # print ("tax iddddddddddd in create",vals,vals['tax_master_details_id'])
            # tax_master_id_check = self.env['tax.master.details'].search(
            # 	[('tax_group_id', '=', vals['tax_group_id']), ('type_tax_use', '=', vals['type_tax_use']),
            # 	 ('tax_master_details_id', '=', vals['tax_master_details_id'])],
            # 	order="from_date asc")
            tax_master_id_check = self.env['tax.master.details'].search(
                [('tax_group_id', '=', vals['tax_group_id']), ('type_tax_use', '=', vals['type_tax_use']),
                 ('tax_master_details_id', '=', self.tax_master_details_id.id)],
                order="from_date asc")
            print("tax_master_id_checkkkkkkkkkkkkk", tax_master_id_check)
            if tax_master_id_check:
                for val in tax_master_id_check:
                    # print ("HHHHHHHHHH",val.from_date , vals['from_date'])
                    if val.from_date > self.from_date:
                        raise ValidationError("From Date of the new tax has to be more than the last valid Date.")
        elif 'tax_group_id' in vals:
            # print ("tax iddddddddddd in create",vals,vals['tax_master_details_id'])
            # tax_master_id_check = self.env['tax.master.details'].search(
            # 	[('tax_group_id', '=', vals['tax_group_id']), ('type_tax_use', '=', self.type_tax_use),
            # 	 ('tax_master_details_id', '=', vals['tax_master_details_id'])],
            # 	order="from_date asc")
            tax_master_id_check = self.env['tax.master.details'].search(
                [('tax_group_id', '=', vals['tax_group_id']), ('type_tax_use', '=', self.type_tax_use),
                 ('tax_master_details_id', '=', self.tax_master_details_id.id)],
                order="from_date asc")
            print("tax_master_id_checkkkkkkkkkkkkk", tax_master_id_check)
            if tax_master_id_check:
                for val in tax_master_id_check:
                    # print ("HHHHHHHHHH",val.from_date , vals['from_date'])
                    if val.from_date > self.from_date:
                        raise ValidationError("From Date of the new tax has to be more than the last valid Date.")
        elif 'type_tax_use' in vals:
            # print ("tax iddddddddddd in create",vals,vals['tax_master_details_id'])
            # tax_master_id_check = self.env['tax.master.details'].search(
            # 	[('tax_group_id', '=', self.tax_group_id), ('type_tax_use', '=', vals['type_tax_use']),
            # 	 ('tax_master_details_id', '=', vals['tax_master_details_id'])],
            # 	order="from_date asc")
            tax_master_id_check = self.env['tax.master.details'].search(
                [('tax_group_id', '=', self.tax_group_id), ('type_tax_use', '=', vals['type_tax_use']),
                 ('tax_master_details_id', '=', self.tax_master_details_id.id)],
                order="from_date asc")
            print("tax_master_id_checkkkkkkkkkkkkk", tax_master_id_check)
            if tax_master_id_check:
                for val in tax_master_id_check:
                    # print ("HHHHHHHHHH",val.from_date , vals['from_date'])
                    if val.from_date > self.from_date:
                        raise ValidationError("From Date of the new tax has to be more than the last valid Date.")

                        # list1 = tax_master_id_check.ids
                        # if len(tax_master_id_check) > 1:
                        # 	raise ValidationError(_('Kindly check your Taxes Validity !'))
                        # if 'tax_id' in vals and vals['tax_id']:
                        # 	tax_ids = self.env['tax.master.details'].browse(vals['tax_id'])
                        # 	vals['tax_id'] = tax_ids
                        # 	vals['from_date'] = tax_ids.from_date
                        # 	print("Runningggg ",vals['from_date'],vals['tax_id'])
        return res
