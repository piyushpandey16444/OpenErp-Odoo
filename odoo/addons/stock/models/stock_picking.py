# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import namedtuple
import json
import time
import math

from itertools import groupby

#import dp as dp

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from odoo.exceptions import UserError, ValidationError
from odoo.addons.stock.models.stock_move import PROCUREMENT_PRIORITIES
from operator import itemgetter


class PickingType(models.Model):
    _name = "stock.picking.type"
    _description = "The operation type determines the picking view"
    _order = 'sequence, id'

    name = fields.Char('Operation Types Name', required=True, translate=True)
    color = fields.Integer('Color')
    sequence = fields.Integer('Sequence', help="Used to order the 'All Operations' kanban view")
    sequence_id = fields.Many2one('ir.sequence', 'Reference Sequence', required=True)
    default_location_src_id = fields.Many2one(
        'stock.location', 'Default Source Location',
        help="This is the default source location when you create a picking manually with this operation type. It is possible however to change it or that the routes put another location. If it is empty, it will check for the supplier location on the partner. ")
    default_location_dest_id = fields.Many2one(
        'stock.location', 'Default Destination Location',
        help="This is the default destination location when you create a picking manually with this operation type. It is possible however to change it or that the routes put another location. If it is empty, it will check for the customer location on the partner. ")
    code = fields.Selection([('incoming', 'Vendors'), ('outgoing', 'Customers'), ('internal', 'Internal')], 'Type of Operation', required=True)
    return_picking_type_id = fields.Many2one('stock.picking.type', 'Operation Type for Returns')
    show_entire_packs = fields.Boolean('Allow moving packs', help="If checked, this shows the packs to be moved as a whole in the Operations tab all the time, even if there was no entire pack reserved.")
    warehouse_id = fields.Many2one(
        'stock.warehouse', 'Warehouse', ondelete='cascade',
        default=lambda self: self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1))
    active = fields.Boolean('Active', default=True)
    use_create_lots = fields.Boolean(
        'Create New Lots/Serial Numbers', default=True,
        help="If this is checked only, it will suppose you want to create new Lots/Serial Numbers, so you can provide them in a text field. ")
    use_existing_lots = fields.Boolean(
        'Use Existing Lots/Serial Numbers', default=True,
        help="If this is checked, you will be able to choose the Lots/Serial Numbers. You can also decide to not put lots in this operation type.  This means it will create stock with no lot or not put a restriction on the lot taken. ")
    show_operations = fields.Boolean(
        'Show Detailed Operations', default=False,
        help="If this checkbox is ticked, the pickings lines will represent detailed stock operations. If not, the picking lines will represent an aggregate of detailed stock operations.")
    show_reserved = fields.Boolean(
        'Show Reserved', default=True, help="If this checkbox is ticked, Odoo will show which products are reserved (lot/serial number, source location, source package).")

    # Statistics for the kanban view
    last_done_picking = fields.Char('Last 10 Done Pickings', compute='_compute_last_done_picking', )
    count_picking_draft = fields.Integer(compute='_compute_picking_count')
    count_picking_ready = fields.Integer(compute='_compute_picking_count')
    count_picking = fields.Integer(compute='_compute_picking_count')
    count_picking_waiting = fields.Integer(compute='_compute_picking_count')
    count_picking_late = fields.Integer(compute='_compute_picking_count')
    count_picking_backorders = fields.Integer(compute='_compute_picking_count')
    rate_picking_late = fields.Integer(compute='_compute_picking_count')
    rate_picking_backorders = fields.Integer(compute='_compute_picking_count')

    barcode_nomenclature_id = fields.Many2one(
        'barcode.nomenclature', 'Barcode Nomenclature')


    @api.one
    def _compute_last_done_picking(self):
        # TDE TODO: true multi
        tristates = []
        for picking in self.env['stock.picking'].search([('picking_type_id', '=', self.id), ('state', '=', 'done')], order='date_done desc', limit=10):
            if picking.date_done > picking.date:
                tristates.insert(0, {'tooltip': picking.name or '' + ": " + _('Late'), 'value': -1})
            elif picking.backorder_id:
                tristates.insert(0, {'tooltip': picking.name or '' + ": " + _('Backorder exists'), 'value': 0})
            else:
                tristates.insert(0, {'tooltip': picking.name or '' + ": " + _('OK'), 'value': 1})
        self.last_done_picking = json.dumps(tristates)

    def _compute_picking_count(self):
        # TDE TODO count picking can be done using previous two
        domains = {
            'count_picking_draft': [('state', '=', 'draft')],
            'count_picking_waiting': [('state', 'in', ('confirmed', 'waiting'))],
            'count_picking_ready': [('state', '=', 'assigned')],
            'count_picking': [('state', 'in', ('assigned', 'waiting', 'confirmed'))],
            'count_picking_late': [('scheduled_date', '<', time.strftime(DEFAULT_SERVER_DATETIME_FORMAT)), ('state', 'in', ('assigned', 'waiting', 'confirmed'))],
            'count_picking_backorders': [('backorder_id', '!=', False), ('state', 'in', ('confirmed', 'assigned', 'waiting'))],
        }
        for field in domains:
            data = self.env['stock.picking'].read_group(domains[field] +
                [('state', 'not in', ('done', 'cancel')), ('picking_type_id', 'in', self.ids)],
                ['picking_type_id'], ['picking_type_id'])
            count = {
                x['picking_type_id'][0]: x['picking_type_id_count']
                for x in data if x['picking_type_id']
            }
            for record in self:
                record[field] = count.get(record.id, 0)
        for record in self:
            record.rate_picking_late = record.count_picking and record.count_picking_late * 100 / record.count_picking or 0
            record.rate_picking_backorders = record.count_picking and record.count_picking_backorders * 100 / record.count_picking or 0

    def name_get(self):
        """ Display 'Warehouse_name: PickingType_name' """
        # TDE TODO remove context key support + update purchase
        res = []

        for picking_type in self:
            if self.env.context.get('special_shortened_wh_name'):
                if picking_type.warehouse_id:
                    name = picking_type.warehouse_id.name
                else:
                    name = _('Customer') + ' (' + picking_type.name + ')'
            elif picking_type.warehouse_id:
                name = picking_type.warehouse_id.name + ': ' + picking_type.name
            else:
                name = picking_type.name
            res.append((picking_type.id, name))
        return res

    @api.model
    def name_search(self, name, args=None, operator='ilike', limit=100):
        args = args or []
        domain = []
        if name:
            domain = ['|', ('name', operator, name), ('warehouse_id.name', operator, name)]
        picks = self.search(domain + args, limit=limit)
        return picks.name_get()

    @api.onchange('code')
    def onchange_picking_code(self):
        if self.code == 'incoming':
            self.default_location_src_id = self.env.ref('stock.stock_location_suppliers').id
            self.default_location_dest_id = self.env.ref('stock.stock_location_stock').id
        elif self.code == 'outgoing':
            self.default_location_src_id = self.env.ref('stock.stock_location_stock').id
            self.default_location_dest_id = self.env.ref('stock.stock_location_customers').id

    @api.onchange('show_operations')
    def onchange_show_operations(self):
        if self.show_operations is True:
            self.show_reserved = True

    def _get_action(self, action_xmlid):
        # TDE TODO check to have one view + custo in methods
        action = self.env.ref(action_xmlid).read()[0]
        if self:
            action['display_name'] = self.display_name
        return action

    def get_action_picking_tree_late(self):
        return self._get_action('stock.action_picking_tree_late')

    def get_action_picking_tree_backorder(self):
        return self._get_action('stock.action_picking_tree_backorder')

    def get_action_picking_tree_waiting(self):
        return self._get_action('stock.action_picking_tree_waiting')

    def get_action_picking_tree_ready(self):
        return self._get_action('stock.action_picking_tree_ready')

    def get_stock_picking_action_picking_type(self):
        return self._get_action('stock.stock_picking_action_picking_type')


class Picking(models.Model):
    _name = "stock.picking"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Transfer"
    # Gaurav commenting and edit for order date desc
    # _order = "priority desc, date asc, id desc"
    _order = "priority desc, date desc, id desc"

    # end
    # Gaurav 5/3/20 added default function on picking_type_id for Operation type(Delivery order and Receipt)
    # Gaurav modified 7/3/20 added default context on picking_type_name for Operation type(Transfer/internal)
    @api.model
    def _default_picking_type(self):
        picking_type_code = ''
        type_obj = self.env['stock.picking.type']
        company_id = self.env.user.company_id.id
        if 'default_picking_type_code' in self._context:
            picking_type_code = self._context.get('default_picking_type_code')
            # print('picking codeeeeeeeeeeeeeeeeeeee',picking_type_code)
        if 'default_picking_type_name' in self._context:
            picking_type_id_name = self._context.get('default_picking_type_name')
            # print('picking codeeeeeeeeeeeeeeeeeeee',picking_type_id_name)
        if picking_type_code == 'internal':
            if picking_type_id_name=='transfer':
                types = type_obj.search([('code', '=', 'internal'), ('name', '=', 'Transfer'), ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search([('code', '=', 'internal'), ('name', '=', 'Transfer'), ('warehouse_id', '=', False)])
            else:
                types = type_obj.search([('code', '=', 'internal'), ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search([('code', '=', 'internal'), ('warehouse_id', '=', False)])
        elif picking_type_code == 'outgoing':
            types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id.company_id', '=', company_id)])
            if not types:
                types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id', '=', False)])
        else:
            types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)])
            if not types:
                types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
        return types[:1]

    # Piyush: code for invoice count on 15-07-2020
    # P: changes with respect to invoice_ids is done

    @api.multi
    def _compute_invoice_count(self):
        sale_order = self.sale_id
        invoice_count = 0
        for invoice_num in sale_order:
            invoice_count = len(invoice_num.invoice_ids)
        self.customer_invoice_count = invoice_count
    # code ends here

    # Piyush: code for check of invoices to be created or not on 22-07-2020
    @api.multi
    def _create_invoice_visibility_check(self):
        if self.picking_type_code == "outgoing":
            sale_order = self.sale_id
            created_invoice = self.env['account.invoice'].search([('dispatch_ids', '=', self.id),
                                                                  ('sale_id', '=', sale_order.id)])
            if created_invoice:
                self.view_invoice_visibility = True
            else:
                self.create_invoice_visibility = True

    # code ends here

    # Piyush: code commented as new values given
    # name = fields.Char(
    #     'Reference', default='/',
    #     copy=False, index=True,
    #     states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})

    name = fields.Char('Reference', required=True, index=True, copy=False, default=lambda self: _('New'),
                       states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    # Piyush: code for adding new invoices ids and count on 15-07-2020
    customer_invoice_count = fields.Integer(compute="_compute_invoice_count", string='Invoices')
    # Piyush: code for adding new compute field on 22-07-2020
    create_invoice_visibility = fields.Boolean(compute="_create_invoice_visibility_check", string="invoice visibility",
                                               help="Button to allow invoices creation if already not there otherwise open already created invoices")
    view_invoice_visibility = fields.Boolean(compute="_create_invoice_visibility_check", string="View Invoice")
    # invoice_ids = fields.Many2many('account.invoice', string='Bills', copy=False,
    #                                store=True)
    # code ends here
    origin = fields.Char(
        'Source Document', index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Reference of the document")
    note = fields.Text('Notes')

    backorder_id = fields.Many2one(
        'stock.picking', 'Back Order of',
        copy=False, index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="If this shipment was split, then this field links to the shipment which contains the already processed part.")

    move_type = fields.Selection([
        ('direct', 'As soon as possible'), ('one', 'When all products are ready')], 'Shipping Policy',
        default='direct', required=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="It specifies goods to be deliver partially or all at once")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting'),
        ('assigned', 'Ready'),
        ('done', 'Done'),
        # Gaurav 5/6/20 added short close state
        ('short_close', 'Short Close'),
        ('bill_pending', 'Bill Pending'),
        # Gaurav end
        ('cancel', 'Cancelled'),
    ], string='Status', compute='_compute_state',
        copy=False, index=True, readonly=True, store=True, track_visibility='onchange',
        help=" * Draft: not confirmed yet and will not be scheduled until confirmed.\n"
             " * Waiting Another Operation: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows).\n"
             " * Waiting: if it is not ready to be sent because the required products could not be reserved.\n"
             " * Ready: products are reserved and ready to be sent. If the shipping policy is 'As soon as possible' this happens as soon as anything is reserved.\n"
             " * Done: has been processed, can't be modified or cancelled anymore.\n"
             " * Cancelled: has been cancelled, can't be confirmed anymore.")

    group_id = fields.Many2one(
        'procurement.group', 'Procurement Group',
        readonly=True, related='move_lines.group_id', store=True)

    priority = fields.Selection(
        PROCUREMENT_PRIORITIES, string='Priority',
        compute='_compute_priority', inverse='_set_priority', store=True,
        # default='1', required=True,  # TDE: required, depending on moves ? strange
        index=True, track_visibility='onchange',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Priority for this picking. Setting manually a value here would set it as priority for all the moves")
    scheduled_date = fields.Datetime(
        'Scheduled Date', compute='_compute_scheduled_date', inverse='_set_scheduled_date', store=True,
        index=True, track_visibility='onchange',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Scheduled time for the first part of the shipment to be processed. Setting manually a value here would set it as expected date for all the stock moves.")
    date = fields.Datetime(
        'Creation Date',
        default=fields.Datetime.now, index=True, track_visibility='onchange',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Creation Date, usually the time of the order")
    date_done = fields.Datetime('Date of Transfer', copy=False, readonly=True, help="Completion Date of Transfer")


    location_id = fields.Many2one(
        'stock.location', "Source Location",
        default=lambda self: self.env['stock.picking.type'].browse(
            self._context.get('default_picking_type_id')).default_location_src_id,
    )

    location_dest_id = fields.Many2one(
        'stock.location', "Destination Location",
        default=lambda self: self.env['stock.picking.type'].browse(
            self._context.get('default_picking_type_id')).default_location_dest_id,
        readonly=True, required=True,
        states={'draft': [('readonly', False)]})
    move_lines = fields.One2many('stock.move', 'picking_id', string="Stock Moves", copy=True)
    has_scrap_move = fields.Boolean(
        'Has Scrap Moves', compute='_has_scrap_move')
    # Gaurav added 5/3/20 default function
    # picking_type_id = fields.Many2one(
    #     'stock.picking.type', 'Operation Type',
    #     required=True,
    #     readonly=True,
    #     states={'draft': [('readonly', False)]}, )
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',
        readonly=True,
        default=_default_picking_type, )
    # Gaurav end
    picking_type_code = fields.Selection([
        ('incoming', 'Vendors'),
        ('outgoing', 'Customers'),
        ('internal', 'Internal')], related='picking_type_id.code',
        readonly=True)
    picking_type_entire_packs = fields.Boolean(related='picking_type_id.show_entire_packs',
                                               readonly=True)

    partner_id = fields.Many2one(
        'res.partner', 'Partner',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get('stock.picking'),
        index=True, required=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})

    move_line_ids = fields.One2many('stock.move.line', 'picking_id', 'Operations')

    move_line_exist = fields.Boolean(
        'Has Pack Operations', compute='_compute_move_line_exist',
        help='Check the existence of pack operation on the picking')

    has_packages = fields.Boolean(
        'Has Packages', compute='_compute_has_packages',
        help='Check the existence of destination packages on move lines')

    entire_package_ids = fields.One2many('stock.quant.package', compute='_compute_entire_package_ids',
                                         help='Those are the entire packages of a picking shown in the view of operations')
    entire_package_detail_ids = fields.One2many('stock.quant.package', compute='_compute_entire_package_ids',
                                                help='Those are the entire packages of a picking shown in the view of detailed operations')

    show_check_availability = fields.Boolean(
        compute='_compute_show_check_availability',
        help='Technical field used to compute whether the check availability button should be shown.')
    show_mark_as_todo = fields.Boolean(
        compute='_compute_show_mark_as_todo',
        help='Technical field used to compute whether the mark as todo button should be shown.')
    show_validate = fields.Boolean(
        compute='_compute_show_validate',
        help='Technical field used to compute whether the validate should be shown.')

    owner_id = fields.Many2one(
        'res.partner', 'Owner',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Default Owner")
    printed = fields.Boolean('Printed')
    is_locked = fields.Boolean(default=True, help='When the picking is not done this allows changing the '
                               'initial demand. When the picking is done this allows '
                               'changing the done quantities.')
    # Used to search on pickings
    product_id = fields.Many2one('product.product', 'Product', related='move_lines.product_id')
    show_operations = fields.Boolean(compute='_compute_show_operations')
    show_lots_text = fields.Boolean(compute='_compute_show_lots_text')
    has_tracking = fields.Boolean(compute='_compute_has_tracking')

    # Gaurav start at 14/2/2020 for scheduling selection
    order_scheduling_id = fields.Many2one('order.scheduling', 'Scheduled Order')
    sale_order_scheduling_id = fields.Many2one('sale.order.scheduling', 'Scheduled Sale Order', index=True, limit=1)
    sale_id = fields.Many2one('sale.order', 'Sale Order')
    # ravi end

    # ravi Added these Fields
    lr_no = fields.Char("LR No")
    lr_date = fields.Date(string="LR Date")
    delivered_date = fields.Date("Delivered Date")
    scr_of_delivery_proof = fields.Binary("Delivery Proof")
    cust_transport_id = fields.Char(string='Transporter')

    eway_bill_no = fields.Char("Eway Bill No")
    eway_proof = fields.Binary("Eway Bill Attachment")
    invoice_no = fields.Char("Invoice No")
    delivery_invoice_date = fields.Datetime("Invoice Date")
    invoice_attach = fields.Binary("Invoice Attach")


    # End

    # Gaurav started for schedule date validation and 4/3/20 source and dest company
    doc_crnt_generation = fields.Datetime("DOC Date", default=fields.Date.today, store=True, force_save=True)
    source_cmpy = fields.Many2one('res.company', 'Source Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    destination_cmpy = fields.Many2one(
        'res.company', 'Destination Company',
        default=lambda self: self.env['res.company']._company_default_get('stock.picking'),
        index=True, required=True,
        )
    # Gaurav 5/3/20 for checking transfer validate
    transfer_made = fields.Boolean('Made in Transfer', default=False)

    # Gaurav 22/4/20 added fields for scheduling form (Gaurav for dispatch)
    sale_scheduling_id = fields.Many2one('sale.order.scheduling', 'Sale Order Scheduling')
    sale_scheduling_line_id = fields.Many2one('sale.order.scheduling.line', 'Sale Order Scheduling Line')
    sale_scheduling_detail_line_id = fields.Many2one('scheduling.sale.order', 'Sale Scheduling Detail')
    # so_type_dup = fields.Selection("So type", related = 'sale_id.so_type')
    # Piyush: code for adding new so type i.e. direct on 22-07-2020
    so_type = fields.Selection([('adhoc', 'Adhoc Order'),('arc', 'Arc'),
                                ('open_order', 'Open Order'), ('direct', 'Direct')], string="Order Type", default="adhoc")
    # check_scheduled = fields.Boolean("check schedule", related = 'sale_id.check_scheduled')
    check_scheduled = fields.Boolean("As per scheduled", store=True, default=False)


    # Gaurav commented for unique error, deleted from the database too..
    # _sql_constraints = [
    #     ('name_uniq', 'unique(name, company_id)', 'Reference must be unique per company!'),
    # ]

    # Gaurav end
    purchase_id = fields.Many2one('purchase.order', clickable=True, string='Purchase Order', copy=False)

    # Piyush: added field in tree 27-03-2020
    as_per_schedule = fields.Boolean(compute='as_per_schedule_data', string='As Per Schedule')
    order_type = fields.Selection([
        ('direct', 'Direct'),
        ('open', 'Open'),
        ('arc', 'Arc'),
    ], string='Order Type')

    # Himanshu SO 2-12-2020 added the address field to show the address of the customer
    address = fields.Text(String="Address", readonly=True)

    # Aman 6/11/2020 Added a date field to get delivery date of sale order
    delivery_date = fields.Date('Delivery Date', copy=False, readonly=True)

    # avinash:21/11/20
    from_bill = fields.Boolean("From dispatch or from receipt", default=False)
    # end avinash

    # Piyush: code for as per schedule check on 27-06-2020
    @api.multi
    def as_per_schedule_data(self):
        for check in self:
            as_per_schedule_check = False
            if check.sale_id and check.sale_id.check_scheduled:
                as_per_schedule_check = True
            elif check.sale_id:
                as_per_schedule_check = False
            check.as_per_schedule = as_per_schedule_check

    # code ends here

    @api.onchange('order_scheduling_id')
    def _onchange_order_scheduling_id(self):
        result = {}
        self.move_lines = []
        all_schedule_product = []
        if self.order_scheduling_id and \
                (self.order_scheduling_id.purchase_id.order_type == 'open' or
                 self.order_scheduling_id.purchase_id.as_per_schedule == True):
            if self.move_lines:
                for val in self.move_lines:
                    sch_list = []
                    scheduling_line = self.env['order.scheduling.line'].search(
                        [('product_id', '=', val.product_id.id),
                         ('order_scheduling_id', '=', self.order_scheduling_id.id), ('product_qty', '>', 0)])
                    # print('scheduling_line', scheduling_line)
                    if len(scheduling_line) > 0:
                        # Piyush: changes to get correct data 22-04-2020
                        val.order_scheduling_id = self.order_scheduling_id.id
                        val.order_scheduling_line_id = scheduling_line[0].id
                        val.product_id = scheduling_line.product_id.id
                        val.product_uom_qty = scheduling_line.po_qty
                        val.pending_qty = scheduling_line.pending_qty
                        val.product_qty = scheduling_line.product_qty
                        # code ends here
                        scheduling_detail = self.env['order.scheduling.detail.line'].search(
                            [('order_scheduling_line_id', '=', scheduling_line[0].id),
                             ('company_id', '=', self.env.user.company_id.id)])
                        # print('scheduling_detail',scheduling_detail)
                        if scheduling_detail:
                            val.order_scheduling_detail_line_id = scheduling_detail[0].id
                            val.show_scheduling_detail = True
                    else:
                        val.show_scheduling_detail = False
                        val.order_scheduling_id = ''
                        val.order_scheduling_line_id = ''
                        val.order_scheduling_detail_line_id = ''

        return result


    # Gaurav 21/4/20 edit for onchange sale scheduling for details and button scheduling

    @api.onchange('sale_order_scheduling_id')
    def _onchange_sale_order_scheduling_id(self):
        self.move_lines=[]
        result = {}
        all_schedule_product = []
        # print ("on chage order schuduleeeeeeee",self.sale_order_scheduling_id,
        #        self.sale_order_scheduling_id.sale_id.so_type, self.sale_order_scheduling_id.sale_id.check_scheduled)
        # Condition: if sales scheduling exists and sale order type is open or as per scheduled is enabled
        if self.sale_order_scheduling_id and \
                (self.sale_order_scheduling_id.sale_id.so_type == 'open_order'
                 or self.sale_order_scheduling_id.sale_id.check_scheduled == True):

            if self.move_lines:
                for val in self.move_lines:

                    sch_list = []
                    # Getting scheduling details
                    scheduling_line = self.env['sale.order.scheduling.line'].search(
                        [('product_id', '=', val.product_id.id),
                         ('schedule_ord_id', '=', self.sale_order_scheduling_id.id), ('pending_sch_qty', '>', 0)])
                    # print('scheduling_line', scheduling_line.product_id, scheduling_line.so_qty, scheduling_line.schedule_qty)
                    if len(scheduling_line) > 0:
                        # Updating values
                        val.product_id = scheduling_line.product_id.id
                        val.product_uom_qty = scheduling_line.so_qty
                        val.pending_qty = scheduling_line.pending_qty
                        val.quantity_done = scheduling_line.schedule_qty
                        val.sale_order_scheduling_id = self.sale_order_scheduling_id.id
                        val.sale_scheduling_line_id = scheduling_line[0].id
                        scheduling_detail = self.env['scheduling.sale.order'].search(
                            [('schedule_line_id', '=', scheduling_line[0].id),
                             ('company_id', '=', self.env.user.company_id.id)])
                        # print('scheduling_detail', scheduling_detail)
                        if scheduling_detail:
                            val.sale_scheduling_detail_line_id = scheduling_detail[0].id
                            val.show_scheduling_detail = True
                    else:
                        val.show_scheduling_detail = False
                        val.sale_order_scheduling_id = ''
                        val.sale_scheduling_line_id = ''
                        val.sale_scheduling_detail_line_id = ''

        return result
    # Gaurav end

    # @api.onchange('order_scheduling_id')
    # def _onchange_order_scheduling_id(self):
    #     result = {}
    #     all_schedule_product = []
    #     # print ("on chage order schuduleeeeeeee",self)
    #     if self.order_scheduling_id and self.order_scheduling_id.purchase_id.order_type == 'open':
    #         if self.move_lines:
    #             for val in self.move_lines:
    #                 sch_list = []
    #                 scheduling_line = self.env['order.scheduling.line'].search(
    #                     [('product_id', '=', val.product_id.id),
    #                      ('order_scheduling_id', '=', self.order_scheduling_id.id), ('product_qty', '>', 0)])
    #                 # print('scheduling_line', scheduling_line)
    #                 if len(scheduling_line) > 0:
    #                     val.order_scheduling_id = self.order_scheduling_id.id
    #                     val.order_scheduling_line_id = scheduling_line[0].id
    #                     scheduling_detail = self.env['order.scheduling.detail.line'].search(
    #                         [('order_scheduling_line_id', '=', scheduling_line[0].id),
    #                          ('company_id', '=', self.env.user.company_id.id)])
    #                     print('scheduling_detail', scheduling_detail)
    #                     if scheduling_detail:
    #                         val.order_scheduling_detail_line_id = scheduling_detail[0].id
    #                         val.show_scheduling_detail = True
    #                 else:
    #                     val.show_scheduling_detail = False
    #                     val.order_scheduling_id = ''
    #                     val.order_scheduling_line_id = ''
    #                     val.order_scheduling_detail_line_id = ''
    #
    #     return result


    def _compute_has_tracking(self):
        for picking in self:
            picking.has_tracking = any(m.has_tracking != 'none' for m in picking.move_lines)

    # Gaurav 7/3/20 added function for transit to destination location for stock move(add)
    # {Gaurav: In case of intercompany transfer stock should move like ||company A(call location)-> transit location and then transit location-> Company B(call location)|| }

    def _transit_move_destination_cmpy(self):

        if self.destination_cmpy:
            stock_destination = self.env['stock.location'].search(
                [('name', '=', "Stock"), ('company_id', '=', self.destination_cmpy.id)])
            if stock_destination:
                stock_destination_data = stock_destination[0].id

                for val in self:
                    stock_move_transfer = val.copy({
                        'location_id': self.location_dest_id.id,
                        'location_dest_id': stock_destination_data,
                        'state': 'assigned'
                    })

        stock_move_transfer.action_confirm()
        stock_move_transfer.action_done()

        # if self.destination_cmpy:
        #     stock_destination = self.env['stock.location'].search(
        #         [('name', '=', "Stock"), ('company_id', '=', self.destination_cmpy.id)])
        #     print('update_dest iddddddddddddddddd',stock_destination,stock_destination.id)
        #     print('update_dest nameeeeeeeeeeeee',stock_destination.name)
        #     if len(stock_destination) > 0:
        #         self.location_dest_id=stock_destination.id

    # Gaurav end

    @api.depends('picking_type_id.show_operations')
    def _compute_show_operations(self):
        for picking in self:
            if self.env.context.get('force_detailed_view'):
                picking.show_operations = True
                continue
            if picking.picking_type_id.show_operations:
                if (picking.state == 'draft' and not self.env.context.get('planned_picking')) or picking.state != 'draft':
                    picking.show_operations = True
                else:
                    picking.show_operations = False
            else:
                picking.show_operations = False

    @api.depends('move_line_ids', 'picking_type_id.use_create_lots', 'picking_type_id.use_existing_lots', 'state')
    def _compute_show_lots_text(self):
        group_production_lot_enabled = self.user_has_groups('stock.group_production_lot')
        for picking in self:
            if not picking.move_line_ids:
                picking.show_lots_text = False
            elif group_production_lot_enabled and picking.picking_type_id.use_create_lots \
                    and not picking.picking_type_id.use_existing_lots and picking.state != 'done':
                picking.show_lots_text = True
            else:
                picking.show_lots_text = False

    @api.depends('move_type', 'move_lines.state', 'move_lines.picking_id')
    @api.one
    def _compute_state(self):
        ''' State of a picking depends on the state of its related stock.move
        - Draft: only used for "planned pickings"
        - Waiting: if the picking is not ready to be sent so if
          - (a) no quantity could be reserved at all or if
          - (b) some quantities could be reserved and the shipping policy is "deliver all at once"
        - Waiting another move: if the picking is waiting for another move
        - Ready: if the picking is ready to be sent so if:
          - (a) all quantities are reserved or if
          - (b) some quantities could be reserved and the shipping policy is "as soon as possible"
        - Done: if the picking is done.
        - Cancelled: if the picking is cancelled
        '''
        if not self.move_lines:
            self.state = 'draft'
        elif any(move.state == 'draft' for move in self.move_lines):  # TDE FIXME: should be all ?
            self.state = 'draft'
        elif all(move.state == 'cancel' for move in self.move_lines):
            self.state = 'cancel'
        elif all(move.state in ['cancel', 'done'] for move in self.move_lines):
            self.state = 'done'
        else:
            relevant_move_state = self.move_lines._get_relevant_state_among_moves()
            if relevant_move_state == 'partially_available':
                self.state = 'assigned'
            else:
                self.state = relevant_move_state

    @api.one
    @api.depends('move_lines.priority')
    def _compute_priority(self):
        if self.mapped('move_lines'):
            priorities = [priority for priority in self.mapped('move_lines.priority') if priority] or ['1']
            self.priority = max(priorities)
        else:
            self.priority = '1'

    @api.one
    def _set_priority(self):
        self.move_lines.write({'priority': self.priority})

    @api.one
    @api.depends('move_lines.date_expected')
    def _compute_scheduled_date(self):
        if self.move_type == 'direct':
            self.scheduled_date = min(self.move_lines.mapped('date_expected') or [fields.Datetime.now()])
        else:
            self.scheduled_date = max(self.move_lines.mapped('date_expected') or [fields.Datetime.now()])

    @api.one
    def _set_scheduled_date(self):
        self.move_lines.write({'date_expected': self.scheduled_date})

    @api.one
    def _has_scrap_move(self):
        # TDE FIXME: better implementation
        self.has_scrap_move = bool(self.env['stock.move'].search_count([('picking_id', '=', self.id), ('scrapped', '=', True)]))

    @api.one
    def _compute_move_line_exist(self):
        self.move_line_exist = bool(self.move_line_ids)

    @api.one
    def _compute_has_packages(self):
        self.has_packages = self.move_line_ids.filtered(lambda ml: ml.result_package_id)

    def _compute_entire_package_ids(self):
        """ This compute method populate the two one2Many containing all entire packages of the picking.
            An entire package is a package that is entirely reserved to be moved from a location to another one.
        """
        for picking in self:
            packages = self.env['stock.quant.package']
            packages_to_check = picking.move_line_ids \
                .filtered(lambda ml: ml.result_package_id and ml.package_id.id == ml.result_package_id.id) \
                .mapped('package_id')
            for package_to_check in packages_to_check:
                if picking.state in ('done', 'cancel') or picking._check_move_lines_map_quant_package(package_to_check):
                    packages |= package_to_check
            picking.entire_package_ids = packages
            picking.entire_package_detail_ids = packages

    @api.multi
    def _compute_show_check_availability(self):
        for picking in self:
            has_moves_to_reserve = any(
                move.state in ('waiting', 'confirmed', 'partially_available') and
                float_compare(move.product_uom_qty, 0, precision_rounding=move.product_uom.rounding)
                for move in picking.move_lines
            )
            picking.show_check_availability = picking.is_locked and picking.state in (
                'confirmed', 'waiting', 'assigned') and has_moves_to_reserve

    @api.multi
    @api.depends('state', 'move_lines')
    def _compute_show_mark_as_todo(self):
        for picking in self:
            if not picking.move_lines:
                picking.show_mark_as_todo = False
            elif self._context.get('planned_picking') and picking.state == 'draft':
                picking.show_mark_as_todo = True
            elif picking.state != 'draft' or not picking.id:
                picking.show_mark_as_todo = False
            else:
                picking.show_mark_as_todo = True

    @api.multi
    @api.depends('state', 'is_locked')
    def _compute_show_validate(self):
        for picking in self:
            # Piyush: code for making validate button visibility false in state other bill pending in dispatches on 11-07-2020
            if self.picking_type_code == 'outgoing':
                if self._context.get('planned_picking') and picking.state == 'draft':
                    picking.show_validate = False
                elif picking.state in ('draft', 'waiting', 'confirmed', 'assigned', 'done') or not picking.is_locked:
                    picking.show_validate = False
                else:
                    picking.show_validate = True
                # code ends here

            elif self.picking_type_code == 'incoming':
                if self._context.get('planned_picking') and picking.state == 'draft':
                    picking.show_validate = False
                #     Gaurav 9/6/20 added for state bill pending
                elif picking.state not in ('draft', 'waiting', 'confirmed', 'assigned','bill_pending') or not picking.is_locked:
                    picking.show_validate = False
                #     Gaurav end
                else:
                    picking.show_validate = True

    @api.onchange('picking_type_id', 'partner_id')
    def onchange_picking_type(self):
        if self.picking_type_id:
            if self.picking_type_id.default_location_src_id:
                location_id = self.picking_type_id.default_location_src_id.id
            elif self.partner_id:
                location_id = self.partner_id.property_stock_supplier.id
            else:
                customerloc, location_id = self.env['stock.warehouse']._get_partner_locations()

            if self.picking_type_id.default_location_dest_id:
                location_dest_id = self.picking_type_id.default_location_dest_id.id
            elif self.partner_id:
                location_dest_id = self.partner_id.property_stock_customer.id
            else:
                location_dest_id, supplierloc = self.env['stock.warehouse']._get_partner_locations()

            if self.state == 'draft':
                self.location_id = location_id
                self.location_dest_id = location_dest_id
        # TDE CLEANME move into onchange_partner_id
        if self.partner_id:
            if self.partner_id.picking_warn == 'no-message' and self.partner_id.parent_id:
                partner = self.partner_id.parent_id
            elif self.partner_id.picking_warn not in ('no-message', 'block') and self.partner_id.parent_id.picking_warn == 'block':
                partner = self.partner_id.parent_id
            else:
                partner = self.partner_id
            if partner.picking_warn != 'no-message':
                if partner.picking_warn == 'block':
                    self.partner_id = False
                return {'warning': {
                    'title': ("Warning for %s") % partner.name,
                    'message': partner.picking_warn_msg
                }}

    # @api.model
    # def default_get(self, fields):
    #     print("all_so_scheduling_rec-----")
    #     res = super(Picking, self).default_get(fields)
    #     if self.env['stock.picking.type'].browse(self.picking_type_id.id).name == 'Delivery Orders':
    #         so = self.env['sale.order'].browse(self.get('origin'))
    #         all_so_scheduling_rec = self.env['sale.order.scheduling'].search(
    #             [('sale_id', '=', so.id), ('company_id', '=', self.env.user.company_id.id)])
    #         if all_so_scheduling_rec:
    #             print("all_so_scheduling_rec-----", all_so_scheduling_rec)
    #
    #     return res




    @api.model
    def create(self, vals):
        # Piyush: code for generating valid sequence 07-05-2020
        # Gaurav 2/07/20 updated and commented piyush code for updating sequence after validate
        # if 'name' not in vals or vals['name'] == _('New'):
        #     vals['name'] = self.env['ir.sequence'].next_by_code('stock.picking') or _('New')
        #     print("val name," , vals['name'])
        #     # code ends here
        # Gaurav  end

        # check = self.env['purchase.order'].search([('id', '=', vals.purchase_id.id)])
        # for val in check:
        #     self.as_per_schedule = val.check.as_per_schedule
        #     self.order_type = val.check.order_type

        # code ends  here

        # TDE FIXME: clean that brol
        # Gaurav edit commenting for sequence on validate
        # defaults = self.default_get(['name', 'picking_type_id'])
        # if vals.get('name', '/') == '/' and defaults.get('name', '/') == '/' and vals.get('picking_type_id', defaults.get('picking_type_id')):
        #     vals['name'] = self.env['stock.picking.type'].browse(vals.get('picking_type_id', defaults.get('picking_type_id'))).sequence_id.next_by_id()
        # Gaurav end
        # TDE FIXME: what ?
        # As the on_change in one2many list is WIP, we will overwrite the locations on the stock moves here
        # As it is a create the format will be a list of (0, 0, dict)

        # Gaurav 6/3/20 adds delivery and LR date validation for receipts
        picking_namee = self.env['stock.picking.type'].browse(self.picking_type_id.id).name
        # print("picking_nameeeeeeeeeee", picking_namee)
        if self.env['stock.picking.type'].browse(vals.get('picking_type_id')).name == 'Receipts':

            deliver_date = vals.get('delivered_date')
            if vals.get('delivered_date'):
                    print("doc d date",vals.get('doc_crnt_generation'))
                    if deliver_date > vals.get('doc_crnt_generation'):
                        raise ValidationError("Delivery or LR date can't be greater than Doc Date")
            # Checking whether doc generation date is less than delivered date and lr date
            lr_date = vals.get('lr_date')
            if vals.get('lr_date'):
                if lr_date > vals.get('doc_crnt_generation'):
                    raise ValidationError("Delivery or LR date can't be greater than Doc Date")
        # Gaurav ends

        if vals.get('move_lines') and vals.get('location_id') and vals.get('location_dest_id'):
            for move in vals['move_lines']:
                if len(move) == 3 and move[0] == 0:
                    move[2]['location_id'] = vals['location_id']
                    move[2]['location_dest_id'] = vals['location_dest_id']

        # Himanshu SO function added to add the address related to the customer
        # self.add_delivery_address(vals)
        data = self.env['res.partner'].search([('id', '=', vals.get('partner_id'))])
        street = data.street
        street2 = data.street2
        zip = data.zip
        city = data.city
        state = self.env['res.country.state'].search([('id', '=', data.state_id.id)]).name
        country = self.env['res.country'].search([('id', '=', data.country_id.id)]).name
        data_list = [street, street2, city, state, zip, country]
        val = ""
        for i in data_list:
            if i != False:
                val = val + str(i) + "\n"

        vals['address'] = val


        res = super(Picking, self).create(vals)
        res._autoconfirm_picking()
        # avinash:21/11/20
        from_bill = True
        # end avinash
        return res

    @api.multi
    def write(self, vals):

        res = super(Picking, self).write(vals)


        # Gaurav 6/3/20 adds delivery and LR date validation for receipts
        picking_namee = self.env['stock.picking.type'].browse(self.picking_type_id.id).name
        print("picking_nameeeeeeeeeee", picking_namee)
        if self.env['stock.picking.type'].browse(self.picking_type_id.id).name == 'Receipts':
            deliver_date = vals.get('delivered_date')
            if vals.get('delivered_date'):
                if deliver_date > self.doc_crnt_generation:
                    raise ValidationError("Delivery or LR date can't be greater than Doc Date")
            # Checking whether doc generation date is less than delivered date and lr date
            lr_date = vals.get('lr_date')
            if vals.get('lr_date'):
                if lr_date > self.doc_crnt_generation:
                    raise ValidationError("Delivery or LR date can't be greater than Doc Date")
                    # Gaurav ends


        # Change locations of moves if those of the picking change
        after_vals = {}
        if vals.get('location_id'):
            after_vals['location_id'] = vals['location_id']
        if vals.get('location_dest_id'):
            after_vals['location_dest_id'] = vals['location_dest_id']
        if after_vals:
            self.mapped('move_lines').filtered(lambda move: not move.scrapped).write(after_vals)
        if vals.get('move_lines'):
            # Do not run autoconfirm if any of the moves has an initial demand. If an initial demand
            # is present in any of the moves, it means the picking was created through the "planned
            # transfer" mechanism.
            pickings_to_not_autoconfirm = self.env['stock.picking']
            for picking in self:
                if picking.state != 'draft':
                    continue
                for move in picking.move_lines:
                    if not float_is_zero(move.product_uom_qty, precision_rounding=move.product_uom.rounding):
                        pickings_to_not_autoconfirm |= picking
                        break
            (self - pickings_to_not_autoconfirm)._autoconfirm_picking()
        return res

    @api.multi
    def unlink(self):
        self.mapped('move_lines')._action_cancel()
        self.mapped('move_lines').unlink() # Checks if moves are not done
        return super(Picking, self).unlink()

    # Actions
    # ----------------------------------------

    @api.one
    def action_assign_owner(self):
        self.move_line_ids.write({'owner_id': self.owner_id.id})

    def action_assign_partner(self):
        for picking in self:
            picking.move_lines.write({'partner_id': picking.partner_id.id})

    @api.multi
    def do_print_picking(self):
        self.write({'printed': True})
        return self.env.ref('stock.action_report_picking').report_action(self)

    @api.multi
    def action_confirm(self):
        # call `_action_confirm` on every draft move
        self.mapped('move_lines')\
            .filtered(lambda move: move.state == 'draft')\
            ._action_confirm()
        # call `_action_assign` on every confirmed move which location_id bypasses the reservation
        self.filtered(lambda picking: picking.location_id.usage in ('supplier', 'inventory', 'production') and picking.state == 'confirmed')\
            .mapped('move_lines')._action_assign()
        if self.env.context.get('planned_picking') and len(self) == 1:
            action = self.env.ref('stock.action_picking_form')
            result = action.read()[0]
            result['res_id'] = self.id
            result['context'] = {
                'search_default_picking_type_id': [self.picking_type_id.id],
                'default_picking_type_id': self.picking_type_id.id,
                'contact_display': 'partner_address',
                'planned_picking': False,
            }
            return result
        else:
            return True

    @api.multi
    def action_assign(self):
        """ Check availability of picking moves.
        This has the effect of changing the state and reserve quants on available moves, and may
        also impact the state of the picking as it is computed based on move's states.
        @return: True
        """
        self.filtered(lambda picking: picking.state == 'draft').action_confirm()
        moves = self.mapped('move_lines').filtered(lambda move: move.state not in ('draft', 'cancel', 'done'))
        if not moves:
            raise UserError(_('Nothing to check the availability for.'))
        moves._action_assign()
        return True

    @api.multi
    def force_assign(self):
        """ Changes state of picking to available if moves are confirmed or waiting.
        @return: True
        """
        self.mapped('move_lines').filtered(lambda move: move.state in ['confirmed', 'waiting', 'partially_available'])._force_assign()
        return True

    @api.multi
    def action_cancel(self):
        self.mapped('move_lines')._action_cancel()
        self.write({'is_locked': True})
        return True

    @api.multi
    def action_done(self):
        """Changes picking state to done by processing the Stock Moves of the Picking

        Normally that happens when the button "Done" is pressed on a Picking view.
        @return: True
        """
        # TDE FIXME: remove decorator when migration the remaining
        todo_moves = self.mapped('move_lines').filtered(lambda self: self.state in ['draft', 'waiting', 'partially_available', 'assigned', 'confirmed', 'bill_pending'])
        # Check if there are ops not linked to moves yet
        # print("Done 1")
        for pick in self:
            print("Done 2")
            # # Explode manually added packages
            # for ops in pick.move_line_ids.filtered(lambda x: not x.move_id and not x.product_id):
            #     for quant in ops.package_id.quant_ids: #Or use get_content for multiple levels
            #         self.move_line_ids.create({'product_id': quant.product_id.id,
            #                                    'package_id': quant.package_id.id,
            #                                    'result_package_id': ops.result_package_id,
            #                                    'lot_id': quant.lot_id.id,
            #                                    'owner_id': quant.owner_id.id,
            #                                    'product_uom_id': quant.product_id.uom_id.id,
            #                                    'product_qty': quant.qty,
            #                                    'qty_done': quant.qty,
            #                                    'location_id': quant.location_id.id, # Could be ops too
            #                                    'location_dest_id': ops.location_dest_id.id,
            #                                    'picking_id': pick.id
            #                                    }) # Might change first element
            # # Link existing moves or add moves when no one is related
            for ops in pick.move_line_ids.filtered(lambda x: not x.move_id):
                # print("Done 3")
                # Search move with this product
                moves = pick.move_lines.filtered(lambda x: x.product_id == ops.product_id)
                moves = sorted(moves, key=lambda m: m.quantity_done < m.product_qty, reverse=True)
                if moves:
                    ops.move_id = moves[0].id
                else:
                    new_move = self.env['stock.move'].create({
                                                    'name': _('New Move:') + ops.product_id.display_name,
                                                    'product_id': ops.product_id.id,
                                                    'product_uom_qty': ops.qty_done,
                                                    'product_uom': ops.product_uom_id.id,
                                                    'location_id': pick.location_id.id,
                                                    'location_dest_id': pick.location_dest_id.id,
                                                    'picking_id': pick.id,
                                                   })
                    ops.move_id = new_move.id
                    new_move._action_confirm()
                    todo_moves |= new_move
                    #'qty_done': ops.qty_done})
                    # print("Done 4")

        todo_moves._action_done()
        # print("Done 5")
        self.validate_scheduling()
        # if self.delivery_invoice_date:
        #     self.write({'date_done': self.delivery_invoice_date})
        # else:
        #     self.write({'date_done': fields.Datetime.now()})
        return True

    def validate_scheduling(self):
        if self.move_lines:
            for val in self.move_lines:
                if val.move_order_schedule_lines:
                    for data in val.move_order_schedule_lines:
                        received_data = data.received_qty
                        if received_data > 0:
                            # print('recieved qty', received_data)
                            schedule_line_get = self.env['order.scheduling.line'].search([('id','=',data.order_scheduling_line_id.id)])
                            # print('schedule_line_get', schedule_line_get)

                            if schedule_line_get:
                                if received_data == schedule_line_get.product_qty:
                                    self.env['order.scheduling.detail.line'].search([('order_scheduling_line_id', '=', schedule_line_get.id)]).write({'received_qty': data.received_qty,'state':'done'})
                                else:
                                    self.env['order.scheduling.detail.line'].search([('order_scheduling_line_id', '=', schedule_line_get.id)]).write({'received_qty': data.received_qty})

    # Backward compatibility
    # Problem with fixed reference to a function:
    # it doesn't allow for overriding action_done() through do_transfer
    # get rid of me in master (and make me private ?)
    def do_transfer(self):
        return self.action_done()

    def _check_move_lines_map_quant_package(self, package):
        """ This method checks that all product of the package (quant) are well present in the move_line_ids of the picking. """
        all_in = True
        pack_move_lines = self.move_line_ids.filtered(lambda ml: ml.package_id == package)
        keys = ['product_id', 'lot_id']
        precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')

        grouped_quants = {}
        for k, g in groupby(sorted(package.quant_ids, key=itemgetter(*keys)), key=itemgetter(*keys)):
            grouped_quants[k] = sum(self.env['stock.quant'].concat(*list(g)).mapped('quantity'))

        grouped_ops = {}
        for k, g in groupby(sorted(pack_move_lines, key=itemgetter(*keys)), key=itemgetter(*keys)):
            grouped_ops[k] = sum(self.env['stock.move.line'].concat(*list(g)).mapped('product_qty'))
        if any(not float_is_zero(grouped_quants.get(key, 0) - grouped_ops.get(key, 0), precision_digits=precision_digits) for key in grouped_quants) \
                or any(not float_is_zero(grouped_ops.get(key, 0) - grouped_quants.get(key, 0), precision_digits=precision_digits) for key in grouped_ops):
            all_in = False
        return all_in

    @api.multi
    def _check_entire_pack(self):
        """ This function check if entire packs are moved in the picking"""
        for picking in self:
            origin_packages = picking.move_line_ids.mapped("package_id")
            for pack in origin_packages:
                if picking._check_move_lines_map_quant_package(pack):
                    picking.move_line_ids.filtered(lambda ml: ml.package_id == pack).write({'result_package_id': pack.id})

    @api.multi
    def do_unreserve(self):
        for picking in self:
            picking.move_lines._do_unreserve()

    # Piyush: validation for stock in hand  20-03-2020

    # Product Check
    # def _compute_quantities(self):
    #     if self.move_lines and self.product_id and self.product_id.positive_stock:
    #         for qty in self.move_lines:
    #             if qty.quantity_done > self.product_id.qty_available:
    #                 raise ValidationError('Cannot issue quantity more than available. For {} available quantity '
    #                                       'is {} '.format(qty.name, self.product_id.qty_available))

    # Company Check
    def _compute_quantities(self):
        if self.move_lines and self.product_id and self.env.user.company_id.default_positive_stock and \
                self.product_id.tracking == 'none' and self.picking_type_code == 'outgoing':
            for qty in self.move_lines:
                # if qty.quantity_done > self.product_id.qty_available:
                if qty.quantity_done > qty.reserved_availability:
                    raise ValidationError('Cannot issue quantity more than reserve. For {} reserved quantity '
                                          'is {} '.format(qty.name, qty.reserved_availability))

        # code ends here
    #
    # # Piyush: code for view of invoices in dispatches on 15-07-1010
    @api.multi
    def action_view_invoice_in_dispatch(self):
        """This function returns an action that display existing invoices
        of given sales order ids. It can either be a in a list or in a form
        view, if there is only one Invoice to show."""
        sale_order = self.sale_id
        created_invoice = self.env['account.invoice'].search([('dispatch_ids', '=', self.id),
                                                              ('sale_id', '=', sale_order.id)])

        if created_invoice:
            print(created_invoice.id, created_invoice)
            action = self.env.ref('account.action_invoice_tree2')
            result = action.read()[0]
            result['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            result['res_id'] = created_invoice.id
            result['context'] = {}
            return result

        else:
            pass

    # # code ends here

    # Piyush: code for invoices
    @api.multi
    def action_invoice_create(self, sale_order, grouped=False, final=False):
        if sale_order:
            inv_obj = self.env['account.invoice']
            precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
            invoices = {}
            references = {}
            invoices_origin = {}
            invoices_name = {}
            qty_done = 0.0
            for qty in self.move_lines:
                if qty.quantity_done > 0:
                    qty_done = qty.quantity_done

            for order in sale_order:
                group_key = order.id if grouped else (order.partner_invoice_id.id, order.currency_id.id)
                for line in order.order_line.sorted(key=lambda l: l.qty_to_invoice < 0):
                    if float_is_zero(qty_done, precision_digits=precision):
                        continue
                    if group_key not in invoices:
                        inv_data = order._prepare_invoice()
                        invoice = inv_obj.create(inv_data)
                        references[invoice] = order
                        invoices[group_key] = invoice
                        invoices_origin[group_key] = [invoice.origin]
                        invoices_name[group_key] = [invoice.name]
                    elif group_key in invoices:
                        if order.name not in invoices_origin[group_key]:
                            invoices_origin[group_key].append(order.name)
                        if order.client_order_ref and order.client_order_ref not in invoices_name[group_key]:
                            invoices_name[group_key].append(order.client_order_ref)

                    if line.qty_to_invoice > 0:
                        line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)
                    elif line.qty_to_invoice < 0 and final:
                        line.invoice_line_create(invoices[group_key].id, line.qty_to_invoice)

                if references.get(invoices.get(group_key)):
                    if order not in references[invoices[group_key]]:
                        references[invoices[group_key]] |= order

            for group_key in invoices:
                invoices[group_key].write({'name': ', '.join(invoices_name[group_key]),
                                           'origin': ', '.join(invoices_origin[group_key])})

            if not invoices:
                raise UserError(_('There is no invoiceable line.'))

            for invoice in invoices.values():
                invoice.compute_taxes()
                if not invoice.invoice_line_ids:
                    raise UserError(_('There is no invoiceable line.'))
                # If invoice is negative, do a refund invoice instead
                if invoice.amount_total < 0:
                    invoice.type = 'out_refund'
                    for line in invoice.invoice_line_ids:
                        line.quantity = -line.quantity
                # Use additional field helper function (for account extensions)
                for line in invoice.invoice_line_ids:
                    line._set_additional_fields(invoice)
                # Necessary to force computation of taxes and cash rounding. In account_invoice, they are triggered
                # by onchanges, which are not triggered when doing a create.
                invoice.compute_taxes()
                invoice._onchange_cash_rounding()
                invoice.message_post_with_view('mail.message_origin_link',
                                               values={'self': invoice, 'origin': references[invoice]},
                                               subtype_id=self.env.ref('mail.mt_note').id)
            return [inv.id for inv in invoices.values()]

    # code ends here

    # Piyush: code for creating invoices from dispatch on 14-07-2020
    # P: added changed related to making sale order readonly when creating invoice from dispatch on 13-08-2020
    @api.multi
    def action_create_invoices(self):

        sale_order = self.sale_id
        created_invoice = self.env['account.invoice'].search([('dispatch_ids', '=', self.id),
                                                              ('sale_id', '=', sale_order.id)])

        if created_invoice:
            action = self.env.ref('account.action_invoice_tree2')
            result = action.read()[0]
            result['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            result['res_id'] = created_invoice.id
            result['context'] = {}
            return result

        else:
            action = self.env.ref('account.action_invoice_tree2')
            result = action.read()[0]
            result['views'] = [(self.env.ref('account.invoice_form').id, 'form')]
            result['target'] = 'current'
            result['context'] = {
                'default_partner_id': sale_order.partner_id and sale_order.partner_id.id or False,
                'default_sale_id': sale_order and sale_order.id or False,
                'default_type': 'out_invoice',
                'journal_type': 'sale',
                'default_freeze_account_item_lines': True,
                # avinash:11/09/20 Added to send operation type delivery on invoice form
                'default_picking_type_id': self.picking_type_id and self.picking_type_id.id or False,
                #end avinash
            }
            return result

            # sale_order.action_invoice_create(sale_order)
    # code ends here

    # Piyush: code for updating schedule shipped qty on 23-07-2020
    @api.multi
    def update_so_scheduling(self):
        if self.move_lines:
            for val in self.move_lines:
                if val.move_sale_order_schedule_lines:
                    for line in val.move_sale_order_schedule_lines:
                        if line.dispatch_qty > 0:
                            schedule_detail_lines = self.env['scheduling.sale.order'].search([('sale_order_id', '=', val.sale_id.id),
                                                                                              ('product_id', '=', line.product_id.id),
                                                                                              ('schedule_date', '=', line.date),
                                                                                              ('dispatch_date', '=', line.dispatch_date)])
                            for qty in schedule_detail_lines:
                                qty.update({'qty_shipped': qty.qty_shipped + line.dispatch_qty})

    # code ends here

    # avinash:10/09/20 (1) Comparing done quantities in lot and done quantites in scheduling
    # (2) Lot name is mandatory on detail button
    # (3) In case of scheduling update done quantities in move lines
    def compute_done_quantities(self):
        for ml in self.move_lines:
            if self.sale_id and self.sale_id.check_scheduled:
                # avinash: 10/09/20 [1] Code for checking lot name and
                # [2] comparing done quantities in lot and done quantities in schedule lines
                if ml.product_id.tracking != 'none':
                    total_done_qty = 0
                    # if ml.move_line_ids:
                    for move_line_lot in ml.move_line_ids:
                        # When we click on confirm button without lot id it confirms
                        # But when we try validate form it give error for lot id and we cannot edit lot id
                        if not move_line_lot.lot_id:
                            raise ValidationError("Please enter lot name")
                        total_done_qty += move_line_lot.qty_done

                    if ml.quantity_done != total_done_qty:
                        raise ValidationError("Pending quantity in scheduling and done quantity in lot are different for product {}".format(ml.product_id.name))

                # piyush: 10/09/20 Code for updating done quantities in move line ids
                for schedule_lines in ml.move_sale_order_schedule_lines:
                    # avinash: 05/09/20 Added for updating pending quantity in schedule wizard on dispatch
                    if schedule_lines.product_qty and schedule_lines.pending_qty:
                        # avinash: 12/11/20 Updating pending quantity in schedule wizard on dispatch
                        # schedule_lines.pending_qty = schedule_lines.product_qty - schedule_lines.dispatch_qty
                        pending_quantity = schedule_lines.pending_qty - schedule_lines.dispatch_qty
                        schedule_lines.pending_qty = pending_quantity
                        # end avinash
                for mvl in ml.move_line_ids:
                    mvl.qty_done = ml.quantity_done

        # end avinash



    # Piyush: code for generating seq in dispatch onclick of confirm button on 06-07-2020
    @api.multi
    def action_button_confirm(self):
        # Piyush: code for calling compute qty on 14-07-2020
        for move_line in self:
            self.compute_done_quantities()
            quantity_check = any(ids.quantity_done > 0 for ids in move_line.move_lines)
            if quantity_check:
                for qty in move_line.move_lines:
                    print(qty)
                    if qty.quantity_done:
                        self._compute_quantities()
                        qty.sale_line_id.to_invoice_qty = qty.quantity_done

            else:
                raise UserError(_("Done Quantities required for atleast one item!"))
        # code ends here
        # avinash: 15/10/20 Added so that same lot cannot be added again. To avoid negative stock
        purchase = self.env['purchase.order']
        purchase.check_lot_detail_repeat(move_line.move_lines)
        # end avinash

        picking_transfer_made = self._context.get('default_transfer_made')
        order_type = self.env['stock.picking.type'].browse(self.picking_type_id.id).name == 'Delivery Orders'
        if order_type and picking_transfer_made:
            transfer_seq = self.env['ir.sequence'].next_by_code('stock.picking.transfer') or 'New'
            self.write({'name': transfer_seq})

        else:
            name = self.env['stock.picking.type'].browse(self.picking_type_id.id).sequence_id.next_by_id()
            # self.write({'name': name})
            self.name = name
            self.ensure_one()
        if not self.move_lines and not self.move_line_ids:
            raise UserError(_('Please add some lines to move'))

        self.write({'state': 'bill_pending'})
        for sale in self.sale_id:
            sale.write({'dispatch_ids': self})

        # P: code for updating delivered qty field in sale order line for making invoices on 15-07-2020
        for sm in self.sale_id.order_line:
            sm.qty_delivered = sm._get_delivered_qty()

        # avinash:12/11/20 Added to make dispatch_qty field readonly in case of bill pending state
        if self.state == "bill_pending":
            for move_line in self.move_lines:
                for schedule_line in move_line.move_sale_order_schedule_lines:
                    schedule_line.check_bill_pending = True

        #end avinash

        # code ends here

    @api.multi
    def button_validate(self):
        # Piyush: code for calling compute qty
        self._compute_quantities()
        #Jatin added this to rectify the stock onhand issue in case of job work challan 05-09-2020
        if self.purchase_id.job_order == True and self.picking_type_id.name == 'Receipts':
            self.bill_available = True
        #Jatin
        # Piyush: validation for master box and MB label required on 23-05-2020
        for line_ids in self.move_lines:
            for box in line_ids.move_line_ids:
                if box.result_package_id and not box.master_box_item_id:
                    raise ValidationError(_("Please provide the master box!"))
                elif box.master_box_item_id and not box.result_package_id:
                    raise ValidationError(_("Please provide the master box label!"))
        # code ends here

        # if self.destination_cmpy:
        #     moving_destination = self.env['stock.location'].search(
        #         [('name', '=', "Stock"), ('company_id', '=', self.destination_cmpy.id)])
        #     if moving_destination:
        #         moving_destination_data = moving_destination[0].id
        #
        #         for val in self:
        #             stock_move_transfer = val.copy({
        #                 'location_id': self.location_dest_id.id,
        #                 'location_dest_id': moving_destination_data,
        #             })
        #
        # stock_move_transfer.action_confirm()
        # stock_move_transfer.action_done()

        # defaults = self.default_get(['name', 'picking_type_id'])
        # if self.get('name', '/') == '/' and defaults.get('name', '/') == '/' \
        #         and self.get('picking_type_id', defaults.get('picking_type_id')):

        # if 'default_transfer_made' in self._context:
        picking_transfer_made = self._context.get('default_transfer_made')
        # print('picking transfer codeeeeeeeeeeeeeeeeeeee',picking_transfer_made)
        # Piyush: this seq in receipt not in dispatch as another is given to dispatch on confirm button on 06-07-2020
        if self.picking_type_code == 'incoming':
            # code ends here
            # Gaurav checking that record made is transfer made if yes show sequence tran otherwise based on type
            if self.env['stock.picking.type'].browse(
                    self.picking_type_id.id).name == 'Delivery Orders' and picking_transfer_made == True:
                transfer_seq = self.env['ir.sequence'].next_by_code('stock.picking.transfer') or ('New')
                # print("sequenceeeeeeeeeeee1 transfer id", transfer_seq)
                self.write({'name': transfer_seq})

            else:
                # avinash: 14/10/20 commented and Added so when receipt validated from vendor bill it do not update name again
                # name = self.env['stock.picking.type'].browse(self.picking_type_id.id).sequence_id.next_by_id()
                # self.write({'name': name})
                # Gaurav end
                if not self.picking_type_id.warehouse_id.code == self.display_name.split('/')[0]:
                    name = self.env['stock.picking.type'].browse(self.picking_type_id.id).sequence_id.next_by_id()
                    # print("sequenceeeeeeeeeeee1 name id", name)
                    self.write({'name': name})
                # end avinash
                self.ensure_one()
            if not self.move_lines and not self.move_line_ids:
                raise UserError(_('Please add some lines to move'))

        # avinash -29/07/20 To update reference no in stock move
        # print(self.move_lines, self.move_lines.id, self.move_lines.name)
        if self.move_lines:
            self.move_lines.write({'name': self.name})
        # end avinash

        # Piyush: added schedule_lines to prevent transfer for scheduled order on 09-07-2020
        schedule_lines = True
        if self.move_lines:
            for lines in self.move_lines:
                if lines.move_sale_order_schedule_lines:
                    schedule_lines = False
        # code ends here

        # If no lots when needed, raise error
        picking_type = self.picking_type_id
        precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        no_quantities_done = all(float_is_zero(move_line.qty_done, precision_digits=precision_digits) for move_line in self.move_line_ids.filtered(lambda m: m.state not in ('done', 'cancel')))
        no_reserved_quantities = all(float_is_zero(move_line.product_qty, precision_rounding=move_line.product_uom_id.rounding) for move_line in self.move_line_ids)

        if no_reserved_quantities and no_quantities_done:
            raise UserError(_('You cannot validate a transfer if you have not processed any quantity. You should rather cancel the transfer.'))

        if picking_type.use_create_lots or picking_type.use_existing_lots:
            lines_to_check = self.move_line_ids
            if not no_quantities_done:
                lines_to_check = lines_to_check.filtered(
                    lambda line: float_compare(line.qty_done, 0,
                                               precision_rounding=line.product_uom_id.rounding)
                )

            for line in lines_to_check:
                product = line.product_id
                if product and product.tracking != 'none':
                    if not line.lot_name and not line.lot_id:
                        raise UserError(_('You need to supply a lot/serial number for %s.') % product.display_name)

        # Piyush: added schedule_lines to prevent transfer for scheduled order on 09-07-2020

        if no_quantities_done and schedule_lines:
            view = self.env.ref('stock.view_immediate_transfer')
            wiz = self.env['stock.immediate.transfer'].create({'pick_ids': [(4, self.id)]})
            return {
                'name': _('Immediate Transfer?'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.immediate.transfer',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                'context': self.env.context,
            }

        if self._get_overprocessed_stock_moves() and not self._context.get('skip_overprocessed_check'):
            view = self.env.ref('stock.view_overprocessed_transfer')
            wiz = self.env['stock.overprocessed.transfer'].create({'picking_id': self.id})
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.overprocessed.transfer',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                'context': self.env.context,
            }

        # Piyush: code for making this run in dispatch only on 08-07-2020
        if self.picking_type_code == 'outgoing' and self.sale_id:
            check = self.env['account.invoice'].search([('dispatch_ids', '=', self.id),
                                                        ('state', 'in', ['open', 'paid'])])
            if check:
                for invoice in check:
                    self.invoice_no = invoice.number or ''
                    self.delivery_invoice_date = invoice.date_invoice or fields.Datetime.now
                # Check backorder should check for other barcodes
                if self._check_backorder():
                    self.update_so_scheduling()
                    return self.action_generate_backorder_wizard()
                else:
                    self.action_done()
                    # Piyush: made changes for managing state in hoitymoppet on 15-09-2020
                    self.sale_id.write({'state': 'done'})
                    # code ends here
                    self.update_so_scheduling()

            else:
                raise ValidationError(_("Dispatch without invoice can not be validated!"))
        # else:
        #     self.action_done()

        # Check backorder should check for other barcodes
        if self._check_backorder():
            return self.action_generate_backorder_wizard()

        # print("validate after check baCkorder")

        if self.picking_type_code == 'incoming':
            self.action_done()

        # code ends here

        # Gaurav added function for transit to dest location transfer
        # Jatin commented this because is is used only for transfer
        # self._transit_move_destination_cmpy()
        # Gaurav end

        # Piyush: code for creating stock move 30-04-2020

        for mv in self.move_lines:
            for line in mv.move_line_ids:

                if line.individual_box:

                    stlc = line.move_id and line.move_id.location_id and line.move_id.location_id.id or False
                    stds = line.move_id and line.move_id.location_dest_id and line.move_id.location_dest_id.id or False

                    # making dictionary of required item for individual box
                    stock_dict = {
                        'name': self.name or '',
                        'product_id': line.individual_box.id,
                        'product_uom_qty': line.individual_box_item_qty,
                        'quantity_done': line.individual_box_item_qty,
                        'location_id': stlc,
                        'location_dest_id': stds,
                        'state': 'draft',
                        'product_uom': line.individual_box.uom_id.id,
                        'company_id': self.env.user.company_id.id,
                    }

                    # creating stock_dict values in environment of stock.move

                    stock_move_id = self.env['stock.move'].create(stock_dict)
                    # print(stock_move_id)

                    if stock_move_id:
                        # code for comparing on hand qty of individual box and master box on 07-05-2020
                        if line.individual_box and line.individual_box_item_qty and line.env.user.company_id.default_positive_stock:
                            if line.individual_box_item_qty > line.individual_box.qty_available:
                                raise ValidationError(
                                    'Cannot issue quantity more than available. For {} available quantity '
                                    'is {} '.format(line.individual_box.name, line.individual_box.qty_available))
                            elif line.individual_box_item_qty == 0:
                                raise ValidationError(
                                    'Individual Box quantity can not be 0, please provide sufficient quantity! '
                                )
                        var = stock_move_id._action_confirm()._action_done()

        # creating stock move for master box item 01-05-2020

        # code for creating qty of master box 01-05-2020

        comp_dict = {}
        for ml in self.move_lines:
            for line_ids in ml.move_line_ids:
                if line_ids.master_box_item_id:
                    if line_ids.master_box_item_id.id not in comp_dict:
                        comp_dict[line_ids.master_box_item_id.id] = [line_ids.result_package_id.id]
                    elif line_ids.master_box_item_id.id in comp_dict:
                        if line_ids.result_package_id.id not in comp_dict.get(line_ids.master_box_item_id.id):
                            values_of_key = comp_dict.get(line_ids.master_box_item_id.id)
                            creating_values_of_key = values_of_key
                            creating_values_of_key.append(line_ids.result_package_id.id)
                            comp_dict[line_ids.master_box_item_id.id] = creating_values_of_key

        # creating dict of master box for stock move

        if comp_dict:
            
            for data in comp_dict:
                product_id = self.env['product.product'].browse(data)
                stock_dict_master = {
                    'name': self.name or '',
                    'product_id': data,
                    'product_uom_qty': len(comp_dict[data]),
                    'quantity_done': len(comp_dict[data]),
                    'location_id': mv.location_id and mv.location_id.id or False,
                    'location_dest_id': mv.location_dest_id and mv.location_dest_id.id or False,
                    'state': 'draft',
                    'product_uom': product_id.uom_id.id or False,
                    'company_id': self.env.user.company_id.id,
                }

                # creating stock_move_id_new values in environment of stock.move

                stock_move_id_new = self.env['stock.move'].create(stock_dict_master)
                if stock_move_id_new:
                    # code for comparing on hand qty of master box and master box on 07-05-2020
                    if product_id and product_id.env.user.company_id.default_positive_stock:
                        if len(comp_dict[data]) > product_id.qty_available:
                            raise ValidationError(
                                'Cannot issue quantity more than available. For {} available quantity '
                                'is {} '.format(product_id.name, product_id.qty_available))
                        elif len(comp_dict[data]) == 0:
                            raise ValidationError(
                                'Master Box quantity can not be 0, please provide sufficient quantity! '
                            )
                    var_new = stock_move_id_new._action_confirm()._action_done()

            # code ends here
        return True

    def action_generate_backorder_wizard(self):
        view = self.env.ref('stock.view_backorder_confirmation')
        wiz = self.env['stock.backorder.confirmation'].create({'pick_ids': [(4, p.id) for p in self]})
        return {
            'name': _('Create Backorder?'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.backorder.confirmation',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': wiz.id,
            'context': self.env.context,
        }

    def action_toggle_is_locked(self):
        self.ensure_one()
        self.is_locked = not self.is_locked
        return True

    def _check_backorder(self):
        """ This method will loop over all the move lines of self and
        check if creating a backorder is necessary. This method is
        called during button_validate if the user has already processed
        some quantities and in the immediate transfer wizard that is
        displayed if the user has not processed any quantities.

        :return: True if a backorder is necessary else False
        """
        quantity_todo = {}
        quantity_done = {}
        for move in self.mapped('move_lines'):
            quantity_todo.setdefault(move.product_id.id, 0)
            quantity_done.setdefault(move.product_id.id, 0)
            quantity_todo[move.product_id.id] += move.product_uom_qty
            quantity_done[move.product_id.id] += move.quantity_done
        for ops in self.mapped('move_line_ids').filtered(lambda x: x.package_id and not x.product_id and not x.move_id):
            for quant in ops.package_id.quant_ids:
                quantity_done.setdefault(quant.product_id.id, 0)
                quantity_done[quant.product_id.id] += quant.qty
        for pack in self.mapped('move_line_ids').filtered(lambda x: x.product_id and not x.move_id):
            quantity_done.setdefault(pack.product_id.id, 0)
            quantity_done[pack.product_id.id] += pack.product_uom_id._compute_quantity(pack.qty_done, pack.product_id.uom_id)
        return any(quantity_done[x] < quantity_todo.get(x, 0) for x in quantity_done)

    @api.multi
    def _autoconfirm_picking(self):
        if not self._context.get('planned_picking'):
            for picking in self.filtered(lambda picking: picking.state not in ('done', 'cancel') and picking.move_lines):
                picking.action_confirm()

    def _get_overprocessed_stock_moves(self):
        self.ensure_one()
        return self.move_lines.filtered(
            lambda move: move.product_uom_qty != 0 and float_compare(move.quantity_done, move.product_uom_qty,
                                                                     precision_rounding=move.product_uom.rounding) == 1
        )

    @api.multi
    def _create_backorder(self, backorder_moves=[]):
        """ Move all non-done lines into a new backorder picking.
        """
        backorders = self.env['stock.picking']
        for picking in self:
            # Gaurav 12/6/20 added state bill pending in filter(which is causing main/ form to show extra moves)
            moves_to_backorder = picking.move_lines.filtered(lambda x: x.state not in ('done', 'cancel','bill_pending'))
            # print("moves_to_backorder,", moves_to_backorder)
            if moves_to_backorder:
                backorder_picking = picking.copy({
                    # Gaurav 2/7/20 change reference / to New BO
                    'name': 'New BO',
                    'order_scheduling_id': False,
                    'move_lines': [],
                    'move_line_ids': [],
                    'backorder_id': picking.id,
                    # Gaurav 18/6/20 added bill available false to uncheck bill available and invoice detail  on creation of new backorder
                    'bill_available': False,
                    'invoice_no': False,
                    'delivery_invoice_date': False,
                    #Jatin added for passing the purchase_id of the receipt in case of backorder
                    'purchase_id':picking.purchase_id.id or False,
                    #end jatin
                })
                # print("backorder_picking",backorder_picking)
                picking.message_post(
                    _('The backorder <a href=# data-oe-model=stock.picking data-oe-id=%d>%s</a> has been created.') % (
                        backorder_picking.id, backorder_picking.name))
                moves_to_backorder.write({'picking_id': backorder_picking.id, 'show_scheduling_detail': False})
                moves_to_backorder.mapped('move_line_ids').write({'picking_id': backorder_picking.id})

                # Piyush: code for sending schedule lines for backorder item on 17-07-2020
                if moves_to_backorder:
                    for val in moves_to_backorder:  # looping in the stock.move whose back order is going to be created
                        # avinash:12/11/20 Commented and Added search condition because in stock.move.schedule.line.
                        # If we create more than two dispatch then schedules lines double every time we create new backorder.
                        # move = self.env['stock.move'].search([('sale_id', '=', val.sale_id.id), ('state', '=', 'done')])
                        move = self.env['stock.move'].search([('sale_id', '=', val.sale_id.id), ('state', '=', 'done'), ('name', '=', self.name)])
                        # end avinash
                        # taking stock.move already created for this SO but looping in only last two SM
                        # for schedule in move[0:2]:  # looping in schedule lines
                        for schedule in move:  # looping in schedule lines
                            for lines in schedule.move_order_schedule_lines:  # looping in the detail scheduling lines for already created SM
                                if lines.pending_qty > 0 and lines.product_id.id == val.product_id.id:  # sending those qty whose pending qty is > 0
                                    move_schedule_lines = self._prepare_schedule_lines(lines)
                                    val.write({'move_sale_order_schedule_lines': move_schedule_lines})
                # code ends here

                backorder_picking.action_assign()
                backorders |= backorder_picking
                # print("last backorders,",backorders)
        #         Gaurav end
        return backorders

    # Piyush: code for preapring dict of schedule lines for backorder stock move on 17-07-2020

    def _prepare_schedule_lines(self, schedule_line):
        sch_list = []
        if schedule_line:
            for val in schedule_line:
                dict_sch = (0, False, {
                    'product_id': val.product_id and val.product_id.id or False,
                    'prod_tmpl_id': val.product_id and val.product_id.product_tmpl_id.id or False,
                    'date': val.date or fields.datetime.now(),
                    'dispatch_date': val.dispatch_date or fields.datetime.now(),
                    'schedule_document': val.schedule_document or '',
                    'product_qty': val.product_qty or 0.0,
                    'dispatch_qty': 0.0,
                    # avinash:12/11/20 commented and added condition for pending quantity.
                    # 'pending_qty': val.product_qty - val.dispatch_qty or 0.0,
                    'pending_qty': val.pending_qty or 0.0,
                    #end avinash
                    'order_scheduling_id': val.id,
                    'product_uom': val.product_uom.id or val.product_id.uom_id.id,
                    'remarks': val.remarks,
                        })
                sch_list.append(dict_sch)
        return sch_list
    # code ends here

    def _put_in_pack(self):
        package = False
        for pick in self.filtered(lambda p: p.state not in ('done', 'cancel')):
            operations = pick.move_line_ids.filtered(lambda o: o.qty_done > 0 and not o.result_package_id)
            operation_ids = self.env['stock.move.line']
            if operations:
                package = self.env['stock.quant.package'].create({})
                for operation in operations:
                    if float_compare(operation.qty_done, operation.product_uom_qty, precision_rounding=operation.product_uom_id.rounding) >= 0:
                        operation_ids |= operation
                    else:
                        quantity_left_todo = float_round(
                            operation.product_uom_qty - operation.qty_done,
                            precision_rounding=operation.product_uom_id.rounding,
                            rounding_method='UP')
                        done_to_keep = operation.qty_done
                        new_operation = operation.copy(
                            default={'product_uom_qty': 0, 'qty_done': operation.qty_done})
                        operation.write({'product_uom_qty': quantity_left_todo, 'qty_done': 0.0})
                        new_operation.write({'product_uom_qty': done_to_keep})
                        operation_ids |= new_operation

                operation_ids.write({'result_package_id': package.id})
            else:
                raise UserError(_('Please process some quantities to put in the pack first!'))
        return package

    def put_in_pack(self):
        return self._put_in_pack()

    def button_scrap(self):
        self.ensure_one()
        products = self.env['product.product']
        for move in self.move_lines:
            if move.state not in ('draft', 'cancel') and move.product_id.type in ('product', 'consu'):
                products |= move.product_id
        return {
            'name': _('Scrap'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.scrap',
            'view_id': self.env.ref('stock.stock_scrap_form_view2').id,
            'type': 'ir.actions.act_window',
            'context': {'default_picking_id': self.id, 'product_ids': products.ids},
            'target': 'new',
        }

    def action_see_move_scrap(self):
        self.ensure_one()
        action = self.env.ref('stock.action_stock_scrap').read()[0]
        scraps = self.env['stock.scrap'].search([('picking_id', '=', self.id)])
        action['domain'] = [('id', 'in', scraps.ids)]
        return action

    def action_see_packages(self):
        self.ensure_one()
        action = self.env.ref('stock.action_package_view').read()[0]
        packages = self.move_line_ids.mapped('result_package_id')
        action['domain'] = [('id', 'in', packages.ids)]
        action['context'] = {'picking_id': self.id}
        return action

    def action_picking_move_tree(self):
        action = self.env.ref('stock.stock_move_action').read()[0]
        action['views'] = [
            (self.env.ref('stock.view_picking_move_tree').id, 'tree'),
        ]
        action['context'] = self.env.context
        action['domain'] = [('picking_id', 'in', self.ids)]
        return action


    # so scheduling


    # def compute_so_show_schedule(self):
    #     for val in self :
    #         if val :
    #             if val.picking_id.sale_order_id.so_type in ('scheduled','open_order') or val.picking_id.sale_order_id.sample:
    #                 val.show_so_schedule = True
    #             else :
    #                 val.show_so_schedule = False
    #
    # so_order_type = fields.Selection(related='picking_id.sale_order_id.so_type', store=True)
    # # so_sample = fields.Boolean(related='picking_id.sale_order_id.sample', store=True)
    # schedule_so_move_lines = fields.One2many('scheduling.sale.picking', 'move_id', 'Schedule So lines')
    # schedule_sale_line_id = fields.Many2one('scheduling.sale.order','Scheduling Sale Line')
    # show_so_schedule = fields.Boolean(compute='compute_so_show_schedule',string='Show Schedule')
    # so_qty = fields.Float('SO Qty',related='sale_line_id.product_uom_qty')
    # date_dispatch = fields.Date(string='Dispatch Date',compute='get_min_schedule_date')
    # date_schedule = fields.Date(string='Schedule Date',compute='get_min_schedule_date')
    #
    # def sale_schedule_dispatch_form(self):
    #     if len(self.schedule_so_move_lines) > 0:
    #         view = self.env.ref('crm_extension.view_stock_move_so_dispatch_schedule')
    #         return {
    #             'name': _('SO Schedule Operations'),
    #             'type': 'ir.actions.act_window',
    #             'view_type': 'form',
    #             'view_mode': 'form',
    #             'res_model': 'stock.move',
    #             'views': [(view.id, 'form')],
    #             'view_id': view.id,
    #             'target': 'new',
    #             'res_id': self.id,
    #
    #         }
    #     else:
    #         so_schedule_id = self.env['scheduling.sale.picking'].search(
    #             [('so_line_id', '=', self.sale_line_id.id),('state','=','done'),('is_pack','=',True),('used_in_dispatch','=',False)])
    #         if len(so_schedule_id) > 0:
    #             for line in so_schedule_id:
    #                 schedult_tup = {
    #                     'scheduling_so_id': line.scheduling_so_id.id,
    #                     'product_id': line.product_id.id,
    #                     'qty_to_dispatch': line.qty_to_dispatch,
    #                     'qty_pack': line.qty_done,
    #                     'qty_pick': line.qty_pick,
    #                     'qty_done': line.qty_done,
    #                     'dispatch_date': line.dispatch_date,
    #                     'schedule_date': line.schedule_date,
    #                     'is_dispatch':True,
    #                     'so_line_id': line.so_line_id.id,
    #                     'sale_id': line.sale_id.id,
    #                     'company_id': line.company_id.id,
    #                 }
    #                 sch_pick_id = self.env['scheduling.sale.picking'].create(schedult_tup)
    #                 line.update({'used_in_dispatch':True})
    #                 if len(sch_pick_id) > 0:
    #                     sch_pick_id.write({'move_id': self.id})
    #             view = self.env.ref('crm_extension.view_stock_move_so_dispatch_schedule')
    #             return {
    #                 'name': _('SO Schedule Operations'),
    #                 'type': 'ir.actions.act_window',
    #                 'view_type': 'form',
    #                 'view_mode': 'form',
    #                 'res_model': 'stock.move',
    #                 'views': [(view.id, 'form')],
    #                 'view_id': view.id,
    #                 'target': 'new',
    #                 'res_id': self.id,
    #             }
    #         else:
    #             raise UserError(_('No Scheduling Defined for this Product!'))
    #
    #
    # def action_show_so_schedule(self):
    #     self.ensure_one()
    #     res = self.sale_schedule_dispatch_form()
    #     return res




# ravi start for stock issue model
class Issues(models.Model):
    _name = "stock.issues"
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _description = "Issues"
    _order = "name desc"

    # _order = "priority desc, date asc, id desc"

    # avinash:16/10/20 (1)To make lot field mandatory if product type is tracking.
    # (2) User cannot add same product twice. So that we can avoid negative stock.
    @api.onchange('move_line_ids')
    def lot_field_mandatory(self):
        if self.move_line_ids:
            product_list_no_track = []
            product_list_track = []
            for move in self.move_line_ids:
                if self.env['account.invoice'].check_product_tracking(move) == ['lot', 'serial']:
                    move.check_lot_available = True
                    if move.lot_id.id not in product_list_track:
                        product_list_track.append(move.lot_id.id)
                    else:
                        raise ValidationError('You cannot add same lot again.')
                else:
                    move.check_lot_available = False
                    if move.product_id.id not in product_list_no_track:
                        product_list_no_track.append(move.product_id.id)
                    else:
                        raise ValidationError('You cannot add same product again.')

    # end avinash


    # Gaurav modified 23/6/20 added default context on picking_type_name for Operation type(Issues/internal)
    @api.model
    def _default_picking_type(self):
        picking_type_code = ''
        picking_type_id_name=''
        type_obj = self.env['stock.picking.type']
        company_id = self.env.user.company_id.id
        if 'default_picking_type_code' in self._context:
            picking_type_code = self._context.get('default_picking_type_code')
            # print('picking codeeeeeeeeeeeeeeeeeeee', picking_type_code)
        if 'default_picking_type_name' in self._context:
            picking_type_id_name = self._context.get('default_picking_type_name')
            # print('picking codeeeeeeeeeeeeeeeeeeee', picking_type_id_name)
        if picking_type_code == 'internal':
            if picking_type_id_name == 'issue':
                types = type_obj.search([('code', '=', 'internal'), ('name', '=', 'Issue'),
                                         ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search(
                        [('code', '=', 'internal'), ('name', '=', 'Issue'), ('warehouse_id', '=', False)])
            else:
                types = type_obj.search([('code', '=', 'internal'), ('warehouse_id.company_id', '=', company_id)])
                if not types:
                    types = type_obj.search([('code', '=', 'internal'), ('warehouse_id', '=', False)])
        elif picking_type_code == 'outgoing':
            types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id.company_id', '=', company_id)])
            if not types:
                types = type_obj.search([('code', '=', 'outgoing'), ('warehouse_id', '=', False)])
        else:
            types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id.company_id', '=', company_id)])
            if not types:
                types = type_obj.search([('code', '=', 'incoming'), ('warehouse_id', '=', False)])
        return types[:1]

        # Gaurav end


    @api.model
    def _default_location_id(self):
        res = {}
        location_ids = ''
        location_ids = self.env['stock.location'].search(
            [('name', '=', 'Stock'), ('company_id', '=', self.env.user.company_id.id)])
        # print("loc src xx,",location_ids)
        has_my_group = self.env.user.has_group('stock.group_stock_multi_warehouses')
        # print("has_my_group,", has_my_group)
        if location_ids:
            res = location_ids[:1]

        return res

    @api.model
    def _domain_location_id(self):
        res = {}
        location_ids = ''
        location_ids = self.env['stock.location'].search(
            [('name', '=', 'Stock'), ('company_id', '=', self.env.user.company_id.id)])
        # print("loc src domain xx,", location_ids)
        if location_ids:
            res = [('id', 'in', location_ids.ids)]

        return res

    @api.model
    def _default_location_dest_id(self):
        location_dest_ids = ''
        location_dest_ids = self.env['stock.location'].search(
            [('name', '=', 'Issue')])

        # print("loc dest xx,", location_dest_ids)
        if location_dest_ids:
            return location_dest_ids[:1]


    # Gaurav 4/4/20 added for computing state
    @api.depends('move_type', 'move_lines.state', 'move_lines.picking_id')
    @api.one
    def _compute_state(self):
        ''' State of a picking depends on the state of its related stock.move
        - Draft: only used for "planned pickings"
        - Waiting: if the picking is not ready to be sent so if
          - (a) no quantity could be reserved at all or if
          - (b) some quantities could be reserved and the shipping policy is "deliver all at once"
        - Waiting another move: if the picking is waiting for another move
        - Ready: if the picking is ready to be sent so if:
          - (a) all quantities are reserved or if
          - (b) some quantities could be reserved and the shipping policy is "as soon as possible"
        - Done: if the picking is done.
        - Cancelled: if the picking is cancelled
        '''
        if not self.move_lines:
            self.state = 'draft'
        elif any(move.state == 'draft' for move in self.move_lines):  # TDE FIXME: should be all ?
            self.state = 'draft'
        elif all(move.state == 'cancel' for move in self.move_lines):
            self.state = 'cancel'
        elif all(move.state in ['cancel', 'done'] for move in self.move_lines):
            self.state = 'done'
        else:
            relevant_move_state = self.move_lines._get_relevant_state_among_moves()
            if relevant_move_state == 'partially_available':
                self.state = 'assigned'
            else:
                self.state = relevant_move_state


    name = fields.Char(
        'Reference', default='New',
        copy=False, index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    origin = fields.Char(
        'Source Document', index=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Reference of the document")
    note = fields.Text('Notes')

    # backorder_id = fields.Many2one(
    #     'stock.picking', 'Back Order of',
    #     copy=False, index=True,
    #     states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
    #     help="If this shipment was split, then this field links to the shipment which contains the already processed part.")

    move_type = fields.Selection([
        ('direct', 'As soon as possible'), ('one', 'When all products are ready')], 'Shipping Policy',
        default='direct', required=True,
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="It specifies goods to be deliver partially or all at once")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('waiting', 'Waiting Another Operation'),
        ('confirmed', 'Waiting'),
        ('assigned', 'Ready'),
        ('done', 'Done'),
        ('cancel', 'Cancelled'),
    ], string='Status', compute='_compute_state',
        copy=False, index=True, readonly=True, store=True, track_visibility='onchange',
        help=" * Draft: not confirmed yet and will not be scheduled until confirmed.\n"
             " * Waiting Another Operation: waiting for another move to proceed before it becomes automatically available (e.g. in Make-To-Order flows).\n"
             " * Waiting: if it is not ready to be sent because the required products could not be reserved.\n"
             " * Ready: products are reserved and ready to be sent. If the shipping policy is 'As soon as possible' this happens as soon as anything is reserved.\n"
             " * Done: has been processed, can't be modified or cancelled anymore.\n"
             " * Cancelled: has been cancelled, can't be confirmed anymore.")

    group_id = fields.Many2one(
        'procurement.group', 'Procurement Group',
        readonly=True, related='move_lines.group_id', store=True)

    # priority = fields.Selection(
    #     PROCUREMENT_PRIORITIES, string='Priority',
    #     compute='_compute_priority', inverse='_set_priority', store=True,
    #     # default='1', required=True,  # TDE: required, depending on moves ? strange
    #     index=True, track_visibility='onchange',
    #     states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
    #     help="Priority for this picking. Setting manually a value here would set it as priority for all the moves")
    scheduled_date = fields.Datetime(
        'Scheduled Date', store=True,
        index=True, track_visibility='onchange',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Scheduled time for the first part of the shipment to be processed. Setting manually a value here would set it as expected date for all the stock moves.")
    date = fields.Datetime(
        'Creation Date',
        default=fields.Datetime.now, index=True, track_visibility='onchange',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Creation Date, usually the time of the order")
    date_done = fields.Datetime('Date of Transfer', copy=False, readonly=True, help="Completion Date of Transfer")

    location_id = fields.Many2one(
        'stock.location', "Source Location",
        default=_default_location_id, domain=_domain_location_id,
        states={'draft': [('readonly', False)]}, store='true')
    location_dest_id = fields.Many2one(
        'stock.location', "Destination Location",
        default=_default_location_dest_id,
        states={'draft': [('readonly', False)]}, store='true')

    move_lines = fields.One2many('stock.move', 'picking_id2', string="Stock Moves", copy=True)
    has_scrap_move = fields.Boolean('Has Scrap Moves')
    # Gaurav Added 5/3/20 default function for operation type: issue
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',
        readonly=True, default=_default_picking_type)
    # Gaurav end
    picking_type_code = fields.Selection([
        ('incoming', 'Vendors'),
        ('outgoing', 'Customers'),
        ('internal', 'Internal')], related='picking_type_id.code',
        readonly=True)
    picking_type_entire_packs = fields.Boolean(related='picking_type_id.show_entire_packs',readonly=True)

    partner_id = fields.Many2one('res.partner', 'Partner',states={'done': [('readonly', True)], 'cancel': [('readonly', True)]})
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id)

    move_line_ids = fields.One2many('stock.move.line', 'picking_id2', 'Operations')

    move_line_exist = fields.Boolean('Has Pack Operations', help='Check the existence of pack operation on the picking')

    has_packages = fields.Boolean('Has Packages', help='Check the existence of destination packages on move lines')

    # entire_package_ids = fields.One2many('stock.quant.package',
    #                                      help='Those are the entire packages of a picking shown in the view of operations')
    # entire_package_detail_ids = fields.One2many('stock.quant.package',
    #                                             help='Those are the entire packages of a picking shown in the view of detailed operations')

    show_check_availability = fields.Boolean(
        help='Technical field used to compute whether the check availability button should be shown.')
    show_mark_as_todo = fields.Boolean(
        help='Technical field used to compute whether the mark as todo button should be shown.')
    show_validate = fields.Boolean(default=True,
        help='Technical field used to compute whether the validate should be shown.')

    owner_id = fields.Many2one(
        'res.partner', 'Owner',
        states={'done': [('readonly', True)], 'cancel': [('readonly', True)]},
        help="Default Owner")
    printed = fields.Boolean('Printed')
    is_locked = fields.Boolean(default=True, help='When the picking is not done this allows changing the '
                               'initial demand. When the picking is done this allows '
                               'changing the done quantities.')
    # Used to search on pickings
    product_id = fields.Many2one('product.product', 'Product', related='move_lines.product_id')
    show_operations = fields.Boolean()
    show_lots_text = fields.Boolean()
    has_tracking = fields.Boolean()

    # ravi start at 14/2/2020 for scheduling selection
    order_scheduling_id = fields.Many2one('order.scheduling', 'Scheduled Order')
    # sale_order_scheduling_id = fields.Many2one('sale.order.scheduling', 'Scheduled Sale Order')
    # ravi end

    # ravi Added these Fields
    lr_no = fields.Char("LR No")
    lr_date = fields.Datetime(string="LR Date")
    delivered_date = fields.Datetime("Delivered Date")
    scr_of_delivery_proof = fields.Binary("Delivery Proof")
    cust_transport_id = fields.Char(string='Transporter')

    eway_bill_no = fields.Char("Eway Bill No")
    eway_proof = fields.Binary("Eway Bill Attachment")
    invoice_no = fields.Char("Invoice No")
    delivery_invoice_date = fields.Char("Invoice Date")
    invoice_attach = fields.Binary("Invoice Attach")


    @api.depends('partner_id')
    def _compute_location_id(self):
        for val in self:
            location_id = ''
            location_ids = val.env['stock.location'].search(
                [('name', '=', 'Stock'), ('company_id', '=', val.env.user.company_id.id)])
            if location_ids:
                val.location_id = location_ids.id

            # picking_type = val.env['stock.picking.type'].search([('name', '=', 'Issues'), ('company_id', '=', val.env.user.company_id.id)])
            # if picking_type:
            #     val.picking_type_id = picking_type.id

    @api.depends('partner_id')
    def _compute_location_dest_id(self):
        for val in self:
            location_id = ''
            location_ids = val.env['stock.location'].search(
                [('name', '=', 'Issues'), ('company_id', '=', val.env.user.company_id.id)])
            if location_ids:
                val.location_dest_id = location_ids.id

    # # Gaurav 4/4/20 added for computing state
    # @api.depends('move_type', 'move_lines.state', 'move_lines.picking_id')
    # @api.one
    # def _compute_state(self):
    #     ''' State of a picking depends on the state of its related stock.move
    #     - Draft: only used for "planned pickings"
    #     - Waiting: if the picking is not ready to be sent so if
    #       - (a) no quantity could be reserved at all or if
    #       - (b) some quantities could be reserved and the shipping policy is "deliver all at once"
    #     - Waiting another move: if the picking is waiting for another move
    #     - Ready: if the picking is ready to be sent so if:
    #       - (a) all quantities are reserved or if
    #       - (b) some quantities could be reserved and the shipping policy is "as soon as possible"
    #     - Done: if the picking is done.
    #     - Cancelled: if the picking is cancelled
    #     '''
    #     if not self.move_lines:
    #         self.state = 'draft'
    #     elif any(move.state == 'draft' for move in self.move_lines):  # TDE FIXME: should be all ?
    #         self.state = 'draft'
    #     elif all(move.state == 'cancel' for move in self.move_lines):
    #         self.state = 'cancel'
    #     elif all(move.state in ['cancel', 'done'] for move in self.move_lines):
    #         self.state = 'done'
    #     else:
    #         relevant_move_state = self.move_lines._get_relevant_state_among_moves()
    #         if relevant_move_state == 'partially_available':
    #             self.state = 'assigned'
    #         else:
    #             self.state = relevant_move_state





    # avinash 30/07/20

    # @api.depends('move_line_ids')
    # @api.onchange('qty_done')
    # def onchange_qty_done(self):
    #     print('qty done = ',self.move_line_ids.qty_done)
    #     raise ValidationError('Test')

    #avinash - 21/07/20 Create function to create sequence.

    @api.multi
    def _autoconfirm_picking(self):
        if not self._context.get('planned_picking'):
            for picking in self.filtered(
                    lambda picking: picking.state not in ('done', 'cancel') and picking.move_lines):
                picking.action_confirm()


    # avinash - 21/07/20 Create function to create sequence.
    @api.model
    def create(self, vals):
        print(self.move_line_ids.qty_done)

        defaults = self.default_get(['name', 'picking_type_id'])
        # print(defaults, vals.get('picking_type_id'), defaults.get('picking_type_id'))
        # if vals.get('name', '/') == '/' and defaults.get('name', '/') == '/' and vals.get('picking_type_id', defaults.get('picking_type_id')):
        vals['name'] = self.env['stock.picking.type'].browse(vals.get('picking_type_id', defaults.get('picking_type_id'))).sequence_id.next_by_id()

        # if vals.get('move_lines') and vals.get('location_id') and vals.get('location_dest_id'):
        #     for move in vals['move_lines']:
        #         if len(move) == 3 and move[0] == 0:
        #             move[2]['location_id'] = vals['location_id']
        #             move[2]['location_dest_id'] = vals['location_dest_id']
        #             move[2]['location_dest_id'] = vals['location_dest_id']
        #             move[2]['location_dest_id'] = vals['location_dest_id']


        res = super(Issues, self).create(vals)
        res._autoconfirm_picking()
        return res

      #avinash end

    # Gaurav edit for sequence on validate
    @api.multi
    def button_issue_validate(self):
        # Gaurav edit for sequence on validate
        # defaults = self.default_get(['name', 'picking_type_id'])
        # if self.get('name', '/') == '/' and defaults.get('name', '/') == '/' \
        #         and self.get('picking_type_id', defaults.get('picking_type_id')):

        #avinash-24/07/20 commeting code because becuase need sequence on create
        # name = self.env['stock.picking.type'].browse(self.picking_type_id.id).sequence_id.next_by_id()
        # self.write({'name': name})
        #avinash end
        self.show_validate=False
        self.ensure_one()
        if not self.move_lines and not self.move_line_ids:
            raise UserError(_('Please add some lines to move'))
    # Gaurav end

        # If no lots when needed, raise error
        picking_type = self.picking_type_id
        #avinash- 23/07/20 Test
        # print(self.picking_type_id.name)
        precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
        no_quantities_done = all(
            float_is_zero(move_line.qty_done, precision_digits=precision_digits) for move_line in
            self.move_line_ids.filtered(lambda m: m.state not in ('done', 'cancel')))
        no_reserved_quantities = all(
            float_is_zero(move_line.product_qty, precision_rounding=move_line.product_uom_id.rounding) for move_line
            in self.move_line_ids)
        if no_reserved_quantities and no_quantities_done:
            raise UserError(_(
                'You cannot validate a transfer if you have not processed any quantity. You should rather cancel the transfer.'))

        if picking_type.use_create_lots or picking_type.use_existing_lots:
            lines_to_check = self.move_line_ids
            if not no_quantities_done:
                lines_to_check = lines_to_check.filtered(
                    lambda line: float_compare(line.qty_done, 0,
                                               precision_rounding=line.product_uom_id.rounding)
                )

            for line in lines_to_check:
                product = line.product_id
                if product and product.tracking != 'none':
                    if not line.lot_name and not line.lot_id:
                        raise UserError(_('You need to supply a lot/serial number for %s.') % product.display_name)

        if no_quantities_done:
            view = self.env.ref('stock.view_immediate_transfer')
            wiz = self.env['stock.immediate.transfer'].create({'pick_ids': [(4, self.id)]})
            return {
                'name': _('Immediate Transfer?'),
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.immediate.transfer',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                'context': self.env.context,
            }

        if self._get_overprocessed_stock_moves() and not self._context.get('skip_overprocessed_check'):
            view = self.env.ref('stock.view_overprocessed_transfer')
            wiz = self.env['stock.overprocessed.transfer'].create({'picking_id': self.id})
            return {
                'type': 'ir.actions.act_window',
                'view_type': 'form',
                'view_mode': 'form',
                'res_model': 'stock.overprocessed.transfer',
                'views': [(view.id, 'form')],
                'view_id': view.id,
                'target': 'new',
                'res_id': wiz.id,
                'context': self.env.context,
            }

        # Check backorder should check for other barcodes
        if self._check_backorder():
            return self.action_generate_backorder_wizard()
        self.action_done()
        # Gaurav added function for transit to dest location transfer
        # self._transit_move_destination_cmpy()
        # Gaurav end
        # print(self.state)
        return

    def _get_overprocessed_stock_moves(self):
        self.ensure_one()
        return self.move_lines.filtered(
            lambda move: move.product_uom_qty != 0 and float_compare(move.quantity_done, move.product_uom_qty,
                                                                     precision_rounding=move.product_uom.rounding) == 1
        )

    @api.multi
    def action_done(self):
        """Changes picking state to done by processing the Stock Moves of the Picking

        Normally that happens when the button "Done" is pressed on a Picking view.
        @return: True
        """
        # TDE FIXME: remove decorator when migration the remaining
        todo_moves = self.mapped('move_lines').filtered(
            lambda self: self.state in ['draft', 'waiting', 'partially_available', 'assigned', 'confirmed'])
        # Check if there are ops not linked to moves yet
        # print("Done 1")
        for pick in self:
            # print("Done 2")
            # # Explode manually added packages
            # for ops in pick.move_line_ids.filtered(lambda x: not x.move_id and not x.product_id):
            #     for quant in ops.package_id.quant_ids: #Or use get_content for multiple levels
            #         self.move_line_ids.create({'product_id': quant.product_id.id,
            #                                    'package_id': quant.package_id.id,
            #                                    'result_package_id': ops.result_package_id,
            #                                    'lot_id': quant.lot_id.id,
            #                                    'owner_id': quant.owner_id.id,
            #                                    'product_uom_id': quant.product_id.uom_id.id,
            #                                    'product_qty': quant.qty,
            #                                    'qty_done': quant.qty,
            #                                    'location_id': quant.location_id.id, # Could be ops too
            #                                    'location_dest_id': ops.location_dest_id.id,
            #                                    'picking_id': pick.id
            #                                    }) # Might change first element
            # # Link existing moves or add moves when no one is related
            for ops in pick.move_line_ids.filtered(lambda x: not x.move_id):
                # print("Done 3")
                # Search move with this product
                moves = pick.move_lines.filtered(lambda x: x.product_id == ops.product_id)
                moves = sorted(moves, key=lambda m: m.quantity_done < m.product_qty, reverse=True)
                if moves:
                    ops.move_id = moves[0].id

                #avinash-27/07/20 passing picking id2 and true so that inside create function of stock move we will
                # get picking id of stock.issue
                # And to check if the picking id is from stock issue we pass true.
                elif pick.picking_type_id.name == "Issue":
                    # print(pick.id, pick.picking_type_id, pick.picking_type_id.name)
                    new_move = self.env['stock.move'].create({
                        # 'name': _('New Move:') + ops.product_id.display_name,
                        'name': pick.name,
                        'product_id': ops.product_id.id,
                        'product_uom_qty': ops.qty_done,
                        'product_uom': ops.product_uom_id.id,
                        'location_id': pick.location_id.id,
                        'location_dest_id': pick.location_dest_id.id,
                        'picking_id2': pick.id,
                        'from_issues': True
                    })
                    ops.move_id = new_move.id
                    # print(new_move.picking_id.picking_type_id, new_move.picking_id.picking_type_id.name)
                    # new_move._actison_confirm()
                    new_move._action_confirm()
                    todo_moves |= new_move
                    # 'qty_done': ops.qty_done})
                    # print("Done 4")

                    #end avinash
                else:
                    # print(pick.id, pick.picking_type_id, pick.picking_type_id.name)
                    new_move = self.env['stock.move'].create({
                        'name': _('New Move:') + ops.product_id.display_name,
                        'product_id': ops.product_id.id,
                        'product_uom_qty': ops.qty_done,
                        'product_uom': ops.product_uom_id.id,
                        'location_id': pick.location_id.id,
                        'location_dest_id': pick.location_dest_id.id,
                        'picking_id': pick.id,
                        'from_issues': False
                    })
                    ops.move_id = new_move.id
                    # print(new_move.picking_id.picking_type_id,new_move.picking_id.picking_type_id.name)
                    # new_move._actison_confirm()
                    new_move._action_confirm()
                    todo_moves |= new_move
                    # 'qty_done': ops.qty_done})
                    # print("Done 4")
        todo_moves._action_done()
        # print("Done 5")
        self.validate_scheduling()
        self.write({'date_done': fields.Datetime.now()})
        return True

    def _transit_move_destination_cmpy(self):

        if self.destination_cmpy:
            stock_destination = self.env['stock.location'].search(
                [('name', '=', "Stock"), ('company_id', '=', self.destination_cmpy.id)])
            if stock_destination:
                stock_destination_data = stock_destination[0].id

                for val in self:
                    stock_move_transfer = val.copy({
                        'location_id': self.location_dest_id.id,
                        'location_dest_id': stock_destination_data,
                        'state': 'assigned'
                    })

        stock_move_transfer.action_confirm()
        stock_move_transfer.action_done()

        # if self.destination_cmpy:
        #     stock_destination = self.env['stock.location'].search(
        #         [('name', '=', "Stock"), ('company_id', '=', self.destination_cmpy.id)])
        #     print('update_dest iddddddddddddddddd',stock_destination,stock_destination.id)
        #     print('update_dest nameeeeeeeeeeeee',stock_destination.name)
        #     if len(stock_destination) > 0:
        #         self.location_dest_id=stock_destination.id

        # Gaurav end

    def _check_backorder(self):
        """ This method will loop over all the move lines of self and
        check if creating a backorder is necessary. This method is
        called during button_validate if the user has already processed
        some quantities and in the immediate transfer wizard that is
        displayed if the user has not processed any quantities.

        :return: True if a backorder is necessary else False
        """
        quantity_todo = {}
        quantity_done = {}
        for move in self.mapped('move_lines'):
            quantity_todo.setdefault(move.product_id.id, 0)
            quantity_done.setdefault(move.product_id.id, 0)
            quantity_todo[move.product_id.id] += move.product_uom_qty
            quantity_done[move.product_id.id] += move.quantity_done
        for ops in self.mapped('move_line_ids').filtered(
                lambda x: x.package_id and not x.product_id and not x.move_id):
            for quant in ops.package_id.quant_ids:
                quantity_done.setdefault(quant.product_id.id, 0)
                quantity_done[quant.product_id.id] += quant.qty
        for pack in self.mapped('move_line_ids').filtered(lambda x: x.product_id and not x.move_id):
            quantity_done.setdefault(pack.product_id.id, 0)
            quantity_done[pack.product_id.id] += pack.product_uom_id._compute_quantity(pack.qty_done,
                                                                                       pack.product_id.uom_id)
        return any(quantity_done[x] < quantity_todo.get(x, 0) for x in quantity_done)

    def validate_scheduling(self):
        if self.move_lines:
            for val in self.move_lines:
                if val.move_order_schedule_lines:
                    for data in val.move_order_schedule_lines:
                        received_data = data.received_qty
                        if received_data > 0:
                            # print('recieved qty', received_data)
                            schedule_line_get = self.env['order.scheduling.line'].search(
                                [('id', '=', data.order_scheduling_line_id.id)])
                            # print('schedule_line_get', schedule_line_get)

                            if schedule_line_get:
                                if received_data == schedule_line_get.product_qty:
                                    self.env['order.scheduling.detail.line'].search(
                                        [('order_scheduling_line_id', '=', schedule_line_get.id)]).write(
                                        {'received_qty': data.received_qty, 'state': 'done'})
                                else:
                                    self.env['order.scheduling.detail.line'].search(
                                        [('order_scheduling_line_id', '=', schedule_line_get.id)]).write(
                                        {'received_qty': data.received_qty})

    @api.multi
    def action_confirm(self):
        # call `_action_confirm` on every draft move
        self.mapped('move_lines') \
            .filtered(lambda move: move.state == 'draft') \
            ._action_confirm()
        # call `_action_assign` on every confirmed move which location_id bypasses the reservation
        self.filtered(lambda picking: picking.location_id.usage in (
        'supplier', 'inventory', 'production') and picking.state == 'confirmed') \
            .mapped('move_lines')._action_assign()
        if self.env.context.get('planned_picking') and len(self) == 1:
            action = self.env.ref('stock.action_picking_form')
            result = action.read()[0]
            result['res_id'] = self.id
            result['context'] = {
                'search_default_picking_type_id': [self.picking_type_id.id],
                'default_picking_type_id': self.picking_type_id.id,
                'contact_display': 'partner_address',
                'planned_picking': False,
            }
            return result
        else:
            return True

    def action_generate_backorder_wizard(self):
        view = self.env.ref('stock.view_backorder_confirmation')
        wiz = self.env['stock.backorder.confirmation'].create({'pick_ids': [(4, p.id) for p in self]})
        return {
            'name': _('Create Backorder?'),
            'type': 'ir.actions.act_window',
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.backorder.confirmation',
            'views': [(view.id, 'form')],
            'view_id': view.id,
            'target': 'new',
            'res_id': wiz.id,
            'context': self.env.context,
        }

    # @api.onchange('order_scheduling_id')
    # def _onchange_order_scheduling_id(self):
    #     result = {}
    #     all_schedule_product = []
    #     # print ("on chage order schuduleeeeeeee",self)
    #     if self.order_scheduling_id and self.order_scheduling_id.purchase_id.order_type == 'open':
    #         if self.move_lines:
    #             for val in self.move_lines:
    #                 sch_list = []
    #                 scheduling_line = self.env['order.scheduling.line'].search(
    #                     [('product_id', '=', val.product_id.id),
    #                      ('order_scheduling_id', '=', self.order_scheduling_id.id), ('product_qty', '>', 0)])
    #                 # print('scheduling_line', scheduling_line)
    #                 if len(scheduling_line) > 0:
    #                     val.order_scheduling_id = self.order_scheduling_id.id
    #                     val.order_scheduling_line_id = scheduling_line[0].id
    #                     scheduling_detail = self.env['order.scheduling.detail.line'].search(
    #                         [('order_scheduling_line_id', '=', scheduling_line[0].id),
    #                          ('company_id', '=', self.env.user.company_id.id)])
    #                     print('scheduling_detail', scheduling_detail)
    #                     if scheduling_detail:
    #                         val.order_scheduling_detail_line_id = scheduling_detail[0].id
    #                         val.show_scheduling_detail = True
    #                 else:
    #                     val.show_scheduling_detail = False
    #                     val.order_scheduling_id == ''
    #                     val.order_scheduling_line_id = ''
    #                     val.order_scheduling_detail_line_id = ''
    #
    #     return result

    # Company Check
    def _compute_quantities_line_ids(self):
        if self.move_line_ids and self.product_id and self.env.user.company_id.default_positive_stock:
            for qty in self.move_line_ids:
                if qty.quantity_done > self.product_id.qty_available:
                    raise ValidationError('Cannot issue quantity more than available. For {} available quantity '
                                          'is {} '.format(qty.name, self.product_id.qty_available))

    
























































