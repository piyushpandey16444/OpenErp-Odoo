# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _


class Routing(models.Model):
    """ Specifies routings of work centers """
    _name = 'routing'
    _rec_name = 'process_name'

    process_name = fields.Char('Process Name', required=True)

# Piyush: code further requires inheriting the fields of process master when mrp is installed
# else only one field is visible.


# class MrpRoutingInherit(models.Model):
#     _inherit = 'mrp.routing'
