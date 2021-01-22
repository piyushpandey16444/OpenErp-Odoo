import json
import re
import uuid
from functools import partial
from datetime import datetime
from datetime import timedelta
import time
from lxml import etree
from dateutil.relativedelta import relativedelta
from werkzeug.urls import url_encode

from odoo import api, exceptions, fields, models, _
from odoo.tools import float_is_zero, float_compare, pycompat
from odoo.tools.misc import formatLang

from odoo.exceptions import AccessError, UserError, RedirectWarning, ValidationError, Warning

from odoo.addons import decimal_precision as dp
import logging


def check_vat(vat):
    if vat:
        return True
    else:
        return False

def check_state(check_cmpy_state, check_custmr_state):
    if check_cmpy_state == check_custmr_state:
        return True
    else:
        return False

# Aman 9/10/2020 added this function to check discount
def check_disct(self):
    if self.discount > 99 or self.discount < 0:
        raise ValidationError(_('Discount must be greater than 0% and less than 100%'))

# Aman 09/10/2020 Added a function to change the state to lost order
def state_lost(self):
    self.state = 'lost'

# Aman 17/10/2020 Added function to calculate taxes to display on table below products table
def check_line(line, tax, currency_id, partner_id, product_qty):
    tax_dict = {}
    if tax and line.product_id:
        price_unit = line.price_unit * (1 - (line.discount or 0.0) / 100.0)
        taxes = tax.compute_all(price_unit, currency_id,
                                          product_qty,
                                          product=line.product_id,
                                          partner=partner_id)
        for t in taxes.get('taxes', []):
            if t.get('id') in tax_dict.keys():
                tax_dict[t.get('id')] = tax_dict.get(t.get('id')) + t.get('amount', 0.0)
            else:
                tax_dict[t.get('id')] = t.get('amount', 0.0)
    return tax_dict

# Aman 17/10/2020 Added function to calculate values to display on table below products table
def detail_table(self, lines, tax_dict, disc_amount, basic_amount, round_off=False):
    charges_data_list = []
    tax_data_list = []
    i = 1
    tax_env = self.env['account.tax']
    # Basic Amount
    if lines:
        charges_data = (0, False, {
            "serial_no": int(i),
            "category": "Basic Amount",
            "label": "Basic Amount",
            # "amount": self.amount_untaxed + amt,
            "amount": basic_amount,
        })
        charges_data_list.append(charges_data)
        i = i + 1
    # Discounted Amount
    if lines:
        if disc_amount != 0:
            charges_data = (0, False, {
                "serial_no": int(i),
                "category": "Discounted Amount",
                "label": "Discounted Amount",
                "amount": disc_amount,
            })
            charges_data_list.append(charges_data)
            i = i + 1
    # Subtotal
    price_subtotal = 0
    if lines:
        for l in lines:
            if l.product_id:
                price_subtotal += l.price_subtotal
        charges_data = (0, False, {
            "serial_no": int(i),
            "category": "Subtotal",
            "label": "Subtotal",
            "amount": price_subtotal,
            #"amount": self.amount_untaxed,
        })
        charges_data_list.append(charges_data)
        i = i + 1
    # Taxes
    if tax_dict:
        for tax_val in tax_dict:
            tax_id_browse = tax_env.browse(tax_val)
            tax_data = (0, False, {
                "serial_no": int(i),
                "category": "Taxes",
                "label": tax_id_browse.name,
                "amount": tax_dict[tax_val],
            })
            tax_data_list.append(tax_data)
            i = i + 1
        charges_data_list = charges_data_list + tax_data_list
    # Round off only for invoicing
    if lines:
        if round_off:
            charges_data = (0, False, {
                "serial_no": int(i),
                "label": "Round Off",
                "amount": round_off,
            })
            charges_data_list.append(charges_data)
            i = i + 1
    # Total Amount
    if lines:
        charges_data = (0, False, {
            "serial_no": int(i),
            "category": "Total Amount",
            "label": "Total Amount",
            "amount": self.amount_total,
        })
        charges_data_list.append(charges_data)
    return charges_data_list

# Aman 20/10/2020 Added function for lost order functionality
def check_dispatch(self):
    for rec in self.dispatch_ids:
        if rec.state == 'bill_pending':
            raise UserError(
                _('Unable to cancel sale order %s as some delivery orders have already been bill pending.') % (
                    self.name))


def get_max_percentage(self, so, po, rfq, sq, cust_invoice, vendor_bill):
    tax_perc = []
    if so:
        for line in self.order_id.order_line:
            for l in line.tax_id:
                tax_perc.append(l.amount)
    if po:
        for line in self.order_id.order_line:
            for l in line.taxes_id:
                tax_perc.append(l.amount)
    if rfq:
        for line in self.rfq_id.rfq_line_ids:
            for l in line.taxes_id:
                tax_perc.append(l.amount)
    if sq:
        for line in self.quotation_id.quotation_lines:
            for l in line.tax_id:
                tax_perc.append(l.amount)
    if cust_invoice or vendor_bill:
        for line in self.invoice_id.invoice_line_ids:
            for l in line.invoice_line_tax_ids:
                tax_perc.append(l.amount)
    max_percentage = max(tax_perc)
    return max_percentage


def get_taxes(self, product, group_type, so=False, po=False, rfq=False, sq=False, cust_invoice=False, vendor_bill=False):
    tax_percentage = get_max_percentage(self, so, po, rfq, sq, cust_invoice, vendor_bill)
    if so or sq or cust_invoice:
        tax = self.env['customer.tax.line'].search(
            [('tax_group_id', 'in', group_type), ('template_id', '=', product.product_tmpl_id.id),
             ('tax_percentage', '=', tax_percentage)])
    if po or rfq or vendor_bill:
        tax = self.env['vendor.tax.line'].search(
            [('tax_group_id', 'in', group_type), ('template_id', '=', product.product_tmpl_id.id),
             ('tax_percentage', '=', tax_percentage)])
    taxes_cust = []
    for i in tax:
        taxes_cust.append(i.tax_id.id)
    return taxes_cust


# Aman 26/12/2020 Added validations to check if Item without HSN code is last item
def check_hsn_disable(self, lines):
    if lines:
        no_hsn = [line.product_id.hsn_disable for line in lines]
        for i in range(len(no_hsn) - 1):
            if no_hsn[i] == True:
                raise ValidationError(_('Item without HSN code should be last item!!'))
# Aman end


