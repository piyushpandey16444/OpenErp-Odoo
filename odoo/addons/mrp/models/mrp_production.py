# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from collections import defaultdict
import math

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tools import float_compare
import  datetime

class MrpProduction(models.Model):
    """ Manufacturing Orders """
    _name = 'mrp.production'
    _description = 'Manufacturing Order'
    _date_name = 'date_planned_start'
    _inherit = ['mail.thread', 'mail.activity.mixin']
    _order = 'date_planned_start asc,id'

    @api.model
    def _get_default_picking_type(self):
        return self.env['stock.picking.type'].search([
            ('code', '=', 'mrp_operation'),
            ('warehouse_id.company_id', 'in', [self.env.context.get('company_id', self.env.user.company_id.id), False])],
            limit=1).id

    @api.model
    def _get_default_location_src_id(self):
        location = False
        if self._context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_src_id
        if not location:
            location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
            try:
                location.check_access_rule('read')
            except (AttributeError, AccessError):
                location = self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1).lot_stock_id
        return location and location.id or False

    @api.model
    def _get_default_location_dest_id(self):
        location = False
        if self._context.get('default_picking_type_id'):
            location = self.env['stock.picking.type'].browse(self.env.context['default_picking_type_id']).default_location_dest_id
        if not location:
            location = self.env.ref('stock.stock_location_stock', raise_if_not_found=False)
            try:
                location.check_access_rule('read')
            except (AttributeError, AccessError):
                location = self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1).lot_stock_id
        return location and location.id or False

    name = fields.Char(
        'Reference', copy=False, readonly=True, default=lambda x: _('New'))
    origin = fields.Char(
        'Source', copy=False,states={'confirmed': [('readonly', False)]},
        help="Reference of the document that generated this production order request.")

    product_id = fields.Many2one(
        'product.product', 'Product',
        domain=[('type', 'in', ['product', 'consu'])],
         required=True,
        states={'confirmed': [('readonly', False)]})
    product_tmpl_id = fields.Many2one('product.template', 'Product Template', related='product_id.product_tmpl_id', readonly=True)
    product_qty = fields.Float(
        'Quantity To Produce',
        default=1.0, digits=dp.get_precision('Product Unit of Measure'),
         required=True, track_visibility='onchange',
        states={'confirmed': [('readonly', False)]})
    product_uom_id = fields.Many2one(
        'product.uom', 'Product Unit of Measure',
        oldname='product_uom', readonly=True, required=True,
        states={'confirmed': [('readonly', False)]})
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type',
        default=_get_default_picking_type, required=True)
    location_src_id = fields.Many2one(
        'stock.location', 'Raw Materials Location',
        default=_get_default_location_src_id,
        readonly=True,  required=True,
        states={'confirmed': [('readonly', False)]},
        help="Location where the system will look for components.")
    location_dest_id = fields.Many2one(
        'stock.location', 'Finished Products Location',
        default=_get_default_location_dest_id,
        readonly=True,  required=True,
        states={'confirmed': [('readonly', False)]},
        help="Location where the system will stock the finished products.")
    date_planned_start = fields.Datetime(
        'Deadline Start', copy=False, default=fields.Datetime.now,
        index=True, required=True,
        states={'confirmed': [('readonly', False)]}, oldname="date_planned")
    date_planned_finished = fields.Datetime(
        'Deadline End', copy=False, default=fields.Datetime.now,
        index=True, 
        states={'confirmed': [('readonly', False)]})
    date_start = fields.Datetime('Start Date', copy=False, index=True, readonly=True)
    date_finished = fields.Datetime('End Date', copy=False, index=True, readonly=True)
    bom_id = fields.Many2one(
        'mrp.bom', 'Bill of Material',
         states={'confirmed': [('readonly', False)]},
        help="Bill of Materials allow you to define the list of required raw materials to make a finished product.")
    #Himanshu mrp 16-12-2020 removed the compute function over the routing_id because if the compute function runs the routing will
    #get selected and it wont be changable.
    routing_id = fields.Many2one(
        'mrp.routing', 'Routing',
         store=True,
        help="The list of operations (list of work centers) to produce the finished product. The routing "
             "is mainly used to compute work center costs during operations and to plan future loads on "
             "work centers based on production planning.")
    #End Himanshu

    #Himanshu 14-12-2020 removed the readonly in order to run the original create because the move_raw_ids are filled
    #whenever a bom is selected but in order to make a stock move we need to run the original create.
    move_raw_ids = fields.One2many(
        'stock.move', 'raw_material_production_id', 'Raw Materials', oldname='move_lines',
        copy=False, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, 
        domain=[('scrapped', '=', False)])
    #End Himanshu

    move_finished_ids = fields.One2many(
        'stock.move', 'production_id', 'Finished Products',
        copy=False, states={'done': [('readonly', True)], 'cancel': [('readonly', True)]}, 
        domain=[('scrapped', '=', False)])
    finished_move_line_ids = fields.One2many(
        'stock.move.line', compute='_compute_lines', inverse='_inverse_lines', string="Finished Product"
        )
    workorder_ids = fields.One2many(
        'mrp.workorder', 'production_id', 'Work Orders',
        copy=False, oldname='workcenter_lines', readonly=True)
    workorder_count = fields.Integer('# Work Orders', compute='_compute_workorder_count')
    workorder_done_count = fields.Integer('# Done Work Orders', compute='_compute_workorder_done_count')
    move_dest_ids = fields.One2many('stock.move', 'created_production_id',
        string="Stock Movements of Produced Goods")

    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('planned', 'Planned'),
        ('progress', 'In Progress'),
        ('done', 'Done'),
        ('cancel', 'Cancelled')], string='State',
        copy=False, default='draft', track_visibility='onchange')
    availability = fields.Selection([
        ('assigned', 'Available'),
        ('partially_available', 'Partially Available'),
        ('waiting', 'Waiting'),
        ('none', 'None')], string='Materials Availability',
        compute='_compute_availability', store=True)


    unreserve_visible = fields.Boolean(
        'Allowed to Unreserve Inventory', compute='_compute_unreserve_visible',
        help='Technical field to check when we can unreserve')
    post_visible = fields.Boolean(
        'Allowed to Post Inventory', compute='_compute_post_visible',
        help='Technical field to check when we can post')
    consumed_less_than_planned = fields.Boolean(
        compute='_compute_consumed_less_than_planned',
        help='Technical field used to see if we have to display a warning or not when confirming an order.')

    user_id = fields.Many2one('res.users', 'Responsible', default=lambda self: self._uid, states={'confirmed': [('readonly', False)]})
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get('mrp.production'),
        required=True)

    check_to_done = fields.Boolean(compute="_get_produced_qty", string="Check Produced Qty", 
        help="Technical Field to see if we can show 'Mark as Done' button")
    qty_produced = fields.Float(compute="_get_produced_qty", string="Quantity Produced")
    procurement_group_id = fields.Many2one(
        'procurement.group', 'Procurement Group',
        copy=False)
    propagate = fields.Boolean(
        'Propagate cancel and split',
        help='If checked, when the previous move of the move (which was generated by a next procurement) is cancelled or split, the move generated by this move will too')
    has_moves = fields.Boolean()
    scrap_ids = fields.One2many('stock.scrap', 'production_id', 'Scraps')
    scrap_count = fields.Integer(compute='_compute_scrap_move_count', string='Scrap Move')
    priority = fields.Selection([('0', 'Not urgent'), ('1', 'Normal'), ('2', 'Urgent'), ('3', 'Very Urgent')], 'Priority',
                                readonly=True, states={'confirmed': [('readonly', False)]}, default='1')
    is_locked = fields.Boolean('Is Locked', default=True, copy=False)
    show_final_lots = fields.Boolean('Show Final Lots', compute='_compute_show_lots')
    production_location_id = fields.Many2one('stock.location', "Production Location", related='product_id.property_stock_production')

    # ravi start at 11/2/2020 for new field_process ids
    process_line_ids = fields.One2many('mrp.production.process.line', 'process_line_id', 'Process Lines', copy=True)
    quantity1 = fields.Float()
    # ravi end
    routing_line_ids = fields.One2many('mrp.production.work.center.line', 'routing_line_id', 'Work Center Operations',
                                       copy=True)

    @api.depends('product_id.tracking')
    def _compute_show_lots(self):
        for production in self:
            production.show_final_lots = production.product_id.tracking != 'none'

    def _inverse_lines(self):
        """ Little hack to make sure that when you change something on these objects, it gets saved"""
        pass

    @api.depends('move_finished_ids.move_line_ids')
    def _compute_lines(self):
        for production in self:
            production.finished_move_line_ids = production.move_finished_ids.mapped('move_line_ids')

    @api.multi
    @api.depends('bom_id.routing_id', 'bom_id.routing_id.operation_ids')
    def _compute_routing(self):
        for production in self:
            if production.bom_id.routing_id.operation_ids:
                production.routing_id = production.bom_id.routing_id.id
            else:
                production.routing_id = False

    #Himanshu mrp 12-12-2020 change the state of MO to draft to comfirm once the confirm button is clicked and freeze all the fields
    #of MO once the state is comfirmed and moves are generated
    def change_state(self):
        self.state ='confirmed'
        for mo in self:
            mo.has_moves = any(mo.move_raw_ids)

    #End Himanshu


    @api.multi
    @api.depends('workorder_ids')
    def _compute_workorder_count(self):
        data = self.env['mrp.workorder'].read_group([('production_id', 'in', self.ids)], ['production_id'], ['production_id'])
        count_data = dict((item['production_id'][0], item['production_id_count']) for item in data)
        for production in self:
            production.workorder_count = count_data.get(production.id, 0)

    @api.multi
    @api.depends('workorder_ids.state')
    def _compute_workorder_done_count(self):
        data = self.env['mrp.workorder'].read_group([
            ('production_id', 'in', self.ids),
            ('state', '=', 'done')], ['production_id'], ['production_id'])
        count_data = dict((item['production_id'][0], item['production_id_count']) for item in data)
        for production in self:
            production.workorder_done_count = count_data.get(production.id, 0)

    @api.multi
    @api.depends('move_raw_ids.state', 'workorder_ids.move_raw_ids', 'bom_id.ready_to_produce')
    def _compute_availability(self):
        for order in self:
            if not order.move_raw_ids:
                order.availability = 'none'
                continue
            if order.bom_id.ready_to_produce == 'all_available':
                order.availability = any(move.state not in ('assigned', 'done', 'cancel') for move in order.move_raw_ids) and 'waiting' or 'assigned'
            else:
                move_raw_ids = order.move_raw_ids.filtered(lambda m: m.product_qty)
                partial_list = [x.state in ('partially_available', 'assigned') for x in move_raw_ids]
                assigned_list = [x.state in ('assigned', 'done', 'cancel') for x in move_raw_ids]
                order.availability = (all(assigned_list) and 'assigned') or (any(partial_list) and 'partially_available') or 'waiting'

    @api.depends('move_raw_ids', 'is_locked', 'state', 'move_raw_ids.quantity_done')
    def _compute_unreserve_visible(self):
        for order in self:
            already_reserved = order.is_locked and order.state not in ('done', 'cancel') and order.mapped('move_raw_ids.move_line_ids')
            any_quantity_done = any([m.quantity_done > 0 for m in order.move_raw_ids])
            order.unreserve_visible = not any_quantity_done and already_reserved

    @api.multi
    @api.depends('move_raw_ids.quantity_done', 'move_finished_ids.quantity_done', 'is_locked')
    def _compute_post_visible(self):
        for order in self:
            if order.product_tmpl_id._is_cost_method_standard():
                order.post_visible = order.is_locked and any((x.quantity_done > 0 and x.state not in ['done', 'cancel']) for x in order.move_raw_ids | order.move_finished_ids)
            else:
                order.post_visible = order.is_locked and any((x.quantity_done > 0 and x.state not in ['done', 'cancel']) for x in order.move_finished_ids)

    @api.multi
    @api.depends('move_raw_ids.quantity_done', 'move_raw_ids.product_uom_qty')
    def _compute_consumed_less_than_planned(self):
        for order in self:
            order.consumed_less_than_planned = any(order.move_raw_ids.filtered(
                lambda move: float_compare(move.quantity_done,
                                           move.product_uom_qty,
                                           precision_rounding=move.product_uom.rounding) == -1)
            )

    @api.multi
    @api.depends('workorder_ids.state', 'move_finished_ids', 'is_locked')
    def _get_produced_qty(self):
        for production in self:
            done_moves = production.move_finished_ids.filtered(lambda x: x.state != 'cancel' and x.product_id.id == production.product_id.id)
            qty_produced = sum(done_moves.mapped('quantity_done'))
            wo_done = True
            if any([x.state not in ('done', 'cancel') for x in production.workorder_ids]):
                wo_done = False
            production.check_to_done = production.is_locked and done_moves and (qty_produced >= production.product_qty) and (production.state not in ('done', 'cancel')) and wo_done
            production.qty_produced = qty_produced
        return True

    # @api.multi
    # @api.depends('move_raw_ids')
    # def _has_moves(self):
    #     for mo in self:
    #         mo.has_moves = any(mo.move_raw_ids)

    @api.multi
    def _compute_scrap_move_count(self):
        data = self.env['stock.scrap'].read_group([('production_id', 'in', self.ids)], ['production_id'], ['production_id'])
        count_data = dict((item['production_id'][0], item['production_id_count']) for item in data)
        for production in self:
            production.scrap_count = count_data.get(production.id, 0)


    _sql_constraints = [
        ('name_uniq', 'unique(name, company_id)', 'Reference must be unique per Company!'),
        ('qty_positive', 'check (product_qty > 0)', 'The quantity to produce must be positive!'),
    ]

    @api.onchange('product_id', 'picking_type_id', 'company_id')
    def onchange_product_id(self):
        """ Finds UoM of changed product. """
        if not self.product_id:
            self.bom_id = False
        else:
            bom = self.env['mrp.bom']._bom_find(product=self.product_id, picking_type=self.picking_type_id, company_id=self.company_id.id)
            if bom.type == 'normal':
                self.bom_id = bom.id
            else:
                self.bom_id = False
            self.product_uom_id = self.product_id.uom_id.id
            return {'domain': {'product_uom_id': [('category_id', '=', self.product_id.uom_id.category_id.id)]}}

    @api.onchange('product_qty')
    def onchange_product_qty(self):
        if self.bom_id:
            for val in self.process_line_ids:
                for operation in self.bom_id.routing_id.operation_ids:
                    if operation.workcenter_id.id == val.workcenter_id.id:
                        cycle_number = math.ceil(self.product_qty / val.workcenter_id.capacity)  # TODO: float_round UP
                        duration_expected = (val.workcenter_id.time_start +
                                             val.workcenter_id.time_stop +
                                             cycle_number * operation.time_cycle * 100.0 / val.workcenter_id.time_efficiency)

                        wo = self.env['mrp.workorder'].search(
                            [('workcenter_id', '=', val.workcenter_id.id), ('state', 'not in', ('done', 'cancel'))])

                        max_date = []
                        for wos in wo:
                            if wos.date_planned_start and wos.date_planned_finished:
                                date_planned_finished = datetime.datetime.strptime(wos.date_planned_finished,
                                                                                   '%Y-%m-%d %H:%M:%S')
                                max_date.append(date_planned_finished)

                        if len(max_date) > 0:
                            date_planned_start = max(max_date)
                            date_planned_start = date_planned_start

                            date_planned_start, date_planned_finished = self.find_shift_date(duration_expected,date_planned_start, val.workcenter_id)

                            val.date_planned_start = date_planned_start
                            val.date_planned_finished = date_planned_finished
                            val.time_cycle = duration_expected
        for val in self:



            if val.move_raw_ids :
                for value in val.move_raw_ids:
                    # bom_lines = self.env['mrp.bom'].search([('id', '=', self.bom_id.id)])
                    if self.bom_id :




                        for bom_line in self.bom_id.bom_line_ids:

                            if value.product_id.id == bom_line.product_id.id :
                                if self.bom_id.product_qty >= 1 :
                                    qty = bom_line.product_qty/self.bom_id.product_qty

                                    self.quantity1 = qty
                                    value.product_uom_qty = qty * self.product_qty



    def find_shift_date(self,duration_expected, date_planned_start, wo_obj):
        l=[]
        for shift in wo_obj.resource_calendar_id.attendance_ids:
            l.append(shift.dayofweek)
            l = list(set(l))

        if (duration_expected / 60) > 8:
            days_to_add = int(duration_expected / 60)
            hrs_to_add = duration_expected % 60
            date_planned_finished = date_planned_start + datetime.timedelta(
                days=days_to_add, hours=hrs_to_add)
            # l = [1, 2, 3, 4, 5, 6]

            count = 0
            loop_date = date_planned_start
            for date in range((date_planned_finished - date_planned_start).days + 1):
                if loop_date.weekday() not in l:
                    count += 1
                loop_date = loop_date + datetime.timedelta(days=1)

            if count:
                date_planned_finished = date_planned_finished + datetime.timedelta(
                    days=count)

        else:
            date_planned_finished = date_planned_start + datetime.timedelta(
                minutes=duration_expected)

        return  date_planned_start, date_planned_finished


    @api.onchange('bom_id')
    def onchange_bom_id(self):
        # self.move_raw_ids = ""
        self.process_line_ids = ""
        self.routing_line_ids = ""
        duration_expected=0.0
        date_planned_start =  datetime.datetime.now()
        date_planned_finished =datetime.datetime.now()
        if self.bom_id:
            bom = self.env['mrp.bom'].search([('company_id', '=', self.company_id.id),('id', '=', self.bom_id.id)])
            print('bom111111111', bom)
            if bom:
                if bom.bom_line_ids:
                    bom_data =[(5,0,0)]
                    for values in bom.bom_line_ids:
                        data=(0,False,{
                            'product_id': values.product_id.id,
                            'product_uom': values.product_uom_id.id,
                            'product_uom_qty': values.product_qty,
                            'operation_id': values.operation_id.id,
                            # 'raw_material_production_id': self.id,
            # # 'sequence': "1234",
            # 'name': self.name,
            # 'date': self.date_planned_start,
            # 'date_expected': self.date_planned_start,
            # 'bom_line_id': values.id,
            #
            # 'location_id': 1,
            # 'location_dest_id': self.product_id.property_stock_production.id,
            # 'raw_material_production_id': self.id,
            # 'company_id': self.company_id.id,
            # # ravi start at 20/2/2020 start for commenting
            # # ravi end
            # 'price_unit': 2,
            # 'procure_method': 'make_to_stock',
            # 'origin': self.name,
            # 'warehouse_id': 1,
            # 'group_id': self.procurement_group_id.id,
            # 'propagate': self.propagate,
            # 'unit_factor': 0,

                        })
                        bom_data.append(data)
                    if bom_data:
                        self.move_raw_ids=bom_data


                if bom.process_line_ids:
                    process_data = []
                    for val in bom.process_line_ids:
                        process_line_data = (0, False, {
                            'process_id': val.process_id.id,
                            'remarks': val.remarks,
                        })
                        process_data.append(process_line_data)
                    if process_data:
                        self.process_line_ids = process_data
                # Yash- 31/10/2020 Add workcenters and operation on change of routing ids
                if bom.routing_line_ids:
                    routline_line_ids = []
                    for line in bom.routing_line_ids:
                        operation_id = line.operation_id or ''
                        workcenter_ids = []
                        for center in line.workcenter_id:
                            workcenter_id = center or False,
                            if workcenter_id:
                                workcenter_ids.append(workcenter_id[0].id)
                        values_work_center_data = (0, False, {
                            'workcenter_id': workcenter_ids,
                            'operation_id': operation_id
                        })
                        routline_line_ids.append(values_work_center_data)

                    if routline_line_ids:
                        self.routing_line_ids = routline_line_ids
            # if self.bom_id.bom_line.ids:
            #     for values in self.bom_id.bom_line.ids:

            # remarks_line_data = []
            # if self.bom_id.bom_line_ids:
            #     for values in self.bom_id.bom_line_ids:
            #         # remarks = values.remarks or '',
            #         # status = values.status or ''
            #         # sale_order_no = values.sale_order_no or ''
            #         values_sale_remarks_line_data = (0, False,{
            #             # 'name': self.name,
            #             # 'date': self.date_planned_start,
            #             # 'date_expected': self.date_planned_start,
            #             # 'product_id': values.product_id.id,
            #             # 'product_uom': values.product_uom_id.id,
            #             # 'product_uom_qty': values.product_qty,
            #             # 'operation_id': values.operation_id.id,
            #             # 'location_id': values.product_id.property_stock_production.id,
            #             # 'location_dest_id': self.location_dest_id.id,
            #             # 'company_id': self.company_id.id,
            #             # 'production_id': self.id,
            #             # 'origin': self.name,
            #             # 'group_id': self.procurement_group_id.id,
            #             # 'propagate': self.propagate,
            #             # 'move_dest_ids': [(4, x.id) for x in self.move_dest_ids],
            #         })
            #
            #
            # #
            # #
            # #
            # #         remarks_line_data.append(values_sale_remarks_line_data)
            # #
            # #     # print('order_line_data',remarks_line_data)
            # #     # print(a)
            # #     self.move_raw_ids = remarks_line_data


    @api.onchange('picking_type_id', 'routing_id')
    def onchange_picking_type(self):
        location = self.env.ref('stock.stock_location_stock')
        try:
            location.check_access_rule('read')
        except (AttributeError, AccessError):
            location = self.env['stock.warehouse'].search([('company_id', '=', self.env.user.company_id.id)], limit=1).lot_stock_id
        self.location_src_id = self.routing_id.location_id.id or self.picking_type_id.default_location_src_id.id or location.id
        self.location_dest_id = self.picking_type_id.default_location_dest_id.id or location.id

    @api.multi
    def write (self, vals):
        res = super(MrpProduction, self).write(vals)
        if 'date_planned_start' in vals:
            moves = (self.mapped('move_raw_ids') + self.mapped('move_finished_ids')).filtered(
                lambda r: r.state not in ['done', 'cancel'])
            moves.write({
                'date_expected': vals['date_planned_start'],
            })
        return res



    @api.model
    def create(self, values):
        # self.move_raw_ids = []
        if not values.get('name', False) or values['name'] == _('New'):
            if values.get('picking_type_id'):
                values['name'] = self.env['stock.picking.type'].browse(values['picking_type_id']).sequence_id.next_by_id()
            else:
                values['name'] = self.env['ir.sequence'].next_by_code('mrp.production') or _('New')
        if not values.get('procurement_group_id'):
            values['procurement_group_id'] = self.env["procurement.group"].create({'name': values['name']}).id
        print("values......product", values)
        production = super(MrpProduction,self).create(values)
        production._generate_moves()

        print("production.............",production)
        return production

    @api.multi
    def unlink(self):
        if any(production.state != 'cancel' for production in self):
            raise UserError(_('hprCannot delete a manufacturing order not in cancel state'))
        return super(MrpProduction, self).unlink()

    def action_toggle_is_locked(self):
        self.ensure_one()
        self.is_locked = not self.is_locked
        return True

    @api.multi
    def _generate_moves(self):
        print(self.bom_id)
        for production in self:
            print("production........",production)
            print("pr..................",production.bom_id)
            print("pr..................",production.bom_id.product_uom_id)
            production._generate_finished_moves()
            factor = production.product_uom_id._compute_quantity(production.product_qty, production.bom_id.product_uom_id) / production.bom_id.product_qty
            boms, lines = production.bom_id.explode(production.product_id, factor, picking_type=production.bom_id.picking_type_id)
            production._generate_raw_moves(lines)
            # Check for all draft moves whether they are mto or not
            production._adjust_procure_method()
            production.move_raw_ids._action_confirm()
        return True

    def _generate_finished_moves(self):
        move = self.env['stock.move'].create({
            'name': self.name,
            'date': self.date_planned_start,
            'date_expected': self.date_planned_start,
            'product_id': self.product_id.id,
            'product_uom': self.product_uom_id.id,
            'product_uom_qty': self.product_qty,
            'location_id': self.product_id.property_stock_production.id,
            'location_dest_id': self.location_dest_id.id,
            'company_id': self.company_id.id,
            'production_id': self.id,
            'origin': self.name,
            'group_id': self.procurement_group_id.id,
            'propagate': self.propagate,
            'move_dest_ids': [(4, x.id) for x in self.move_dest_ids],
        })

        move._action_confirm()
        return move

    def _generate_raw_moves(self, exploded_lines):
        self.ensure_one()
        moves = self.env['stock.move']
        for bom_line, line_data in exploded_lines:
            moves += self._generate_raw_move(bom_line, line_data)
        return moves

    def _generate_raw_move(self, bom_line, line_data):
        quantity = line_data['qty']
        # alt_op needed for the case when you explode phantom bom and all the lines will be consumed in the operation given by the parent bom line
        alt_op = line_data['parent_line'] and line_data['parent_line'].operation_id.id or False
        print("alt_op",alt_op)
        if bom_line.child_bom_id and bom_line.child_bom_id.type == 'phantom':
            return self.env['stock.move']
        if bom_line.product_id.type not in ['product', 'consu']:
            return self.env['stock.move']
        if self.routing_id:
            routing = self.routing_id
        else:
            routing = self.bom_id.routing_id
        if routing and routing.location_id:
            source_location = routing.location_id
        else:
            source_location = self.location_src_id
        original_quantity = (self.product_qty - self.qty_produced) or 1.0
        data = {
            'sequence': bom_line.sequence,
            'name': self.name,
            'date': self.date_planned_start,
            'date_expected': self.date_planned_start,
            'bom_line_id': bom_line.id,
            'product_id': bom_line.product_id.id,
            'product_uom_qty': quantity,
            'product_uom': bom_line.product_uom_id.id,
            'location_id': source_location.id,
            'location_dest_id': self.product_id.property_stock_production.id,
            'raw_material_production_id': self.id,
            'company_id': self.company_id.id,
            # ravi start at 20/2/2020 start for commenting
            'operation_id': bom_line.operation_id.id or alt_op,
            # ravi end
            'price_unit': bom_line.product_id.standard_price,
            'procure_method': 'make_to_stock',
            'origin': self.name,
            'warehouse_id': source_location.get_warehouse().id,
            'group_id': self.procurement_group_id.id,
            'propagate': self.propagate,
            'unit_factor': quantity / original_quantity,
        }
        return self.env['stock.move'].create(data)

    @api.multi
    def _adjust_procure_method(self):
        try:
            mto_route = self.env['stock.warehouse']._get_mto_route()
        except:
            mto_route = False
        for move in self.move_raw_ids:
            product = move.product_id
            routes = product.route_ids + product.route_from_categ_ids
            # TODO: optimize with read_group?
            pull = self.env['procurement.rule'].search([('route_id', 'in', [x.id for x in routes]), ('location_src_id', '=', move.location_id.id),
                                                        ('location_id', '=', move.location_dest_id.id)], limit=1)
            if pull and (pull.procure_method == 'make_to_order'):
                move.procure_method = pull.procure_method
            elif not pull: # If there is no make_to_stock rule either
                if mto_route and mto_route.id in [x.id for x in routes]:
                    move.procure_method = 'make_to_order'

    @api.multi
    def _update_raw_move(self, bom_line, line_data):
        quantity = line_data['qty']
        self.ensure_one()
        move = self.move_raw_ids.filtered(lambda x: x.bom_line_id.id == bom_line.id and x.state not in ('done', 'cancel'))
        if move:
            if quantity > 0:
                production = move[0].raw_material_production_id
                production_qty = production.product_qty - production.qty_produced
                move[0]._decrease_reserved_quanity(quantity)
                move[0].with_context(do_not_unreserve=True).write({'product_uom_qty': quantity})
                move[0]._recompute_state()
                move[0]._action_assign()
                move[0].unit_factor = production_qty and (quantity - move[0].quantity_done) / production_qty or 1.0
            elif quantity < 0:  # Do not remove 0 lines
                if move[0].quantity_done > 0:
                    raise UserError(_('Lines need to be deleted, but can not as you still have some quantities to consume in them. '))
                move[0]._action_cancel()
                move[0].unlink()
            return move
        else:
            self._generate_raw_move(bom_line, line_data)

    @api.multi
    def action_assign(self):
        for production in self:
            production.move_raw_ids._action_assign()
        return True

    @api.multi
    def open_produce_product(self):
        self.ensure_one()
        action = self.env.ref('mrp.act_mrp_product_produce').read()[0]
        return action

    @api.multi
    def button_plan(self):
        """ Create work orders. And probably do stuff, like things. """
        orders_to_plan = self.filtered(lambda order: order.routing_id and order.state == 'confirmed')
        for order in orders_to_plan:
            quantity = order.product_uom_id._compute_quantity(order.product_qty, order.bom_id.product_uom_id) / order.bom_id.product_qty
            boms, lines = order.bom_id.explode(order.product_id, quantity, picking_type=order.bom_id.picking_type_id)
            order._generate_workorders(boms)
        return orders_to_plan.write({'state': 'planned'})

    @api.multi
    def _generate_workorders(self, exploded_boms):
        workorders = self.env['mrp.workorder']
        original_one = False
        for bom, bom_data in exploded_boms:
            # If the routing of the parent BoM and phantom BoM are the same, don't recreate work orders, but use one master routing
            if bom.routing_id.id and (not bom_data['parent_line'] or bom_data['parent_line'].bom_id.routing_id.id != bom.routing_id.id):
                temp_workorders = self._workorders_create(bom, bom_data)
                workorders += temp_workorders
                if temp_workorders: # In order to avoid two "ending work orders"
                    if original_one:
                        temp_workorders[-1].next_work_order_id = original_one
                    original_one = temp_workorders[0]
        return workorders

    def _workorders_create(self, bom, bom_data):
        """
        :param bom: in case of recursive boms: we could create work orders for child
                    BoMs
        """
        workorders = self.env['mrp.workorder']
        bom_qty = bom_data['qty']

        # Initial qty producing
        if self.product_id.tracking == 'serial':
            quantity = 1.0
        else:
            quantity = self.product_qty - sum(self.move_finished_ids.mapped('quantity_done'))
            quantity = quantity if (quantity > 0) else 0

        for operation in bom.routing_id.operation_ids:
            # Yash- As discussed with Dheeraj as of now set woekcenter id first from
            # the list of operation ids
            if len(operation.workcenter_id) > 0:
                workcenter_id = operation.workcenter_id[0]
            else:
                workcenter_id = ''
            workcenter_ids = [w for w in operation.workcenter_id]
            # create workorder
            cycle_number = math.ceil(bom_qty / workcenter_id.capacity)  # TODO: float_round UP
            duration_expected = (workcenter_id.time_start +
                                 workcenter_id.time_stop +
                                 cycle_number * operation.time_cycle * 100.0 / workcenter_id.time_efficiency)

            workorder = workorders.create({
                'name': operation.name,
                'production_id': self.id,
                'workcenter_id': workcenter_id.id,
                'operation_id': operation.id,
                'duration_expected': duration_expected,
                'state': len(workorders) == 0 and 'ready' or 'pending',
                'qty_producing': quantity,
                'capacity': workcenter_id.capacity,
                # 'workcenter_ids': workcenter_ids
            })
            if workorders:
                workorders[-1].next_work_order_id = workorder.id
            workorders += workorder

            # assign moves; last operation receive all unassigned moves (which case ?)
            moves_raw = self.move_raw_ids.filtered(lambda move: move.operation_id == operation)
            if len(workorders) == len(bom.routing_id.operation_ids):
                moves_raw |= self.move_raw_ids.filtered(lambda move: not move.operation_id)
            moves_finished = self.move_finished_ids.filtered(lambda move: move.operation_id == operation) #TODO: code does nothing, unless maybe by_products?
            moves_raw.mapped('move_line_ids').write({'workorder_id': workorder.id})
            (moves_finished + moves_raw).write({'workorder_id': workorder.id})

            workorder._generate_lot_ids()
        return workorders

    @api.multi
    def action_cancel(self):
        """ Cancels production order, unfinished stock moves and set procurement
        orders in exception """
        if any(workorder.state == 'progress' for workorder in self.mapped('workorder_ids')):
            raise UserError(_('You can not cancel production order, a work order is still in progress.'))
        for production in self:
            production.workorder_ids.filtered(lambda x: x.state != 'cancel').action_cancel()

            finish_moves = production.move_finished_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            raw_moves = production.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            (finish_moves | raw_moves)._action_cancel()

        self.write({'state': 'cancel', 'is_locked': True})
        return True

    def _cal_price(self, consumed_moves):
        self.ensure_one()
        return True

    @api.multi
    def post_inventory(self):
        for order in self:
            moves_not_to_do = order.move_raw_ids.filtered(lambda x: x.state == 'done')
            moves_to_do = order.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel'))
            for move in moves_to_do.filtered(lambda m: m.product_qty == 0.0 and m.quantity_done > 0):
                move.product_uom_qty = move.quantity_done
            moves_to_do._action_done()
            moves_to_do = order.move_raw_ids.filtered(lambda x: x.state == 'done') - moves_not_to_do
            order._cal_price(moves_to_do)
            moves_to_finish = order.move_finished_ids.filtered(lambda x: x.state not in ('done','cancel'))
            moves_to_finish._action_done()
            order.action_assign()
            consume_move_lines = moves_to_do.mapped('active_move_line_ids')
            for moveline in moves_to_finish.mapped('active_move_line_ids'):
                if moveline.product_id == order.product_id and moveline.move_id.has_tracking != 'none':
                    if any([not ml.lot_produced_id for ml in consume_move_lines]):
                        raise UserError(_('You can not consume without telling for which lot you consumed it'))
                    # Link all movelines in the consumed with same lot_produced_id false or the correct lot_produced_id
                    filtered_lines = consume_move_lines.filtered(lambda x: x.lot_produced_id == moveline.lot_id)
                    moveline.write({'consume_line_ids': [(6, 0, [x for x in filtered_lines.ids])]})
                else:
                    # Link with everything
                    moveline.write({'consume_line_ids': [(6, 0, [x for x in consume_move_lines.ids])]})
        return True

    @api.multi
    def button_mark_done(self):
        self.ensure_one()
        for wo in self.workorder_ids:
            if wo.time_ids.filtered(lambda x: (not x.date_end) and (x.loss_type in ('productive', 'performance'))):
                raise UserError(_('Work order %s is still running') % wo.name)
        self.post_inventory()
        moves_to_cancel = (self.move_raw_ids | self.move_finished_ids).filtered(lambda x: x.state not in ('done', 'cancel'))
        moves_to_cancel._action_cancel()
        self.write({'state': 'done', 'date_finished': fields.Datetime.now()})
        return self.write({'state': 'done'})

    @api.multi
    def do_unreserve(self):
        for production in self:
            production.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel'))._do_unreserve()
        return True

    @api.multi
    def button_unreserve(self):
        self.ensure_one()
        self.do_unreserve()
        return True

    @api.multi
    def button_scrap(self):
        self.ensure_one()
        return {
            'name': _('Scrap'),
            'view_type': 'form',
            'view_mode': 'form',
            'res_model': 'stock.scrap',
            'view_id': self.env.ref('stock.stock_scrap_form_view2').id,
            'type': 'ir.actions.act_window',
            'context': {'default_production_id': self.id,
                        'product_ids': (self.move_raw_ids.filtered(lambda x: x.state not in ('done', 'cancel')) | self.move_finished_ids.filtered(lambda x: x.state == 'done')).mapped('product_id').ids,
                        },
            'target': 'new',
        }

    @api.multi
    def action_see_move_scrap(self):
        self.ensure_one()
        action = self.env.ref('stock.action_stock_scrap').read()[0]
        action['domain'] = [('production_id', '=', self.id)]
        return action


class MRPPChallan(models.Model):
    _name = 'mrp.challan'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    name = fields.Char('', size=256, default='New')
    challan_date = fields.Datetime('Challan Date' , default=fields.Datetime.now , readonly ="1")

    partner_id = fields.Many2one('res.partner', string="Customer", clickable=True)
    process_name = fields.Many2one('mrp.routing', string="Process")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    item_lines = fields.One2many('mrp.challan.lines','item_line_id', 'Item Lines')
    item_out_lines = fields.One2many('mrp.challan.out.lines', 'item_line_id', 'Item Lines')
    out_item_check = fields.Boolean("Input Items are not same as Output Items")
    show_btn = fields.Boolean('Show', default=False)
    dispatch_through = fields.Text("Dispatch Through")
    expected_return_date = fields.Date("Expected Return Date")
    date_and_time_of_issue = fields.Datetime("Date and Time of Issue")
    material_out = fields.Boolean('Material Out', default=True)
    remarks =fields.Text("Remarks")
    # work_order_no = fields.Many2one('mrp.workorder', string="Work Order No")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('gate_pass', 'Gate Pass Done'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
     ], string='State',
        copy=False, default='draft')

    from_other_source = fields.Boolean("Other Source")
    # challan_type = fields.Selection([
    #     ('returnable', 'Returnable'),
    #     ('non_returnable', 'Non Returnable'),
    # ], string='Challan Type',
    #     copy=False, default='returnable')
    challan_create_type = fields.Selection([
        ('direct', 'Direct'),
        ('production', 'Production'),
    ], string='Challan Create Type',
        copy=False,default='direct')
    eway_bill_no = fields.Char('E-Way Bill No.')
    eway_bill_date = fields.Datetime('E-Way Bill Date')

    # user_ids = fields.Many2many('mrp.production', 'gamification_challenge_users_rel', string="Users",
    #                             help="List of users participating to the challenge")
    # user_domain = fields.Char("User domain", help="Alternative to a list of users")
    # costing = fields.Char("User domain")

    # challan = fields.Many2many("mrp.challan.in", string='Challan')



    def create_job_challan(self):
        print("test")
    #
    @api.model
    def create(self, vals):
        res = super(MRPPChallan, self).create(vals)
        for val in res.item_lines:
            for vals in res.item_lines:
                if val.partner_id != vals.partner_id or val.process_name != vals.process_name:
                    raise ValidationError("Cannot Create Group Challan for Different Vendors or Different Processes...")
        if res.out_item_check:
            if not res.item_out_lines:
                raise ValidationError("Please Define Output Items...")

        if not res.item_lines and not vals.get('from_other_source', True):
            raise ValidationError("Please Define Items...")

        res.show_btn = True
        return res

    @api.multi
    def write(self, vals):
        res = super(MRPPChallan, self).write(vals)
        if self.expected_return_date and datetime.datetime.strptime(self.expected_return_date,
                                                                    "%Y-%m-%d") < datetime.datetime.now():
            raise ValidationError("Please Choose Future Date for Return...")
        if self.date_and_time_of_issue and datetime.datetime.strptime(self.date_and_time_of_issue,
                                                                     "%Y-%m-%d %H:%M:%S") > datetime.datetime.now():
            raise ValidationError("Please Choose Previous Date For Issue...")
        if self.out_item_check:
            if not self.item_out_lines:
                raise ValidationError("Please Define Output Items...")


        if not self.item_lines and not self.from_other_source:
            raise ValidationError("Please Define Items...")

        if self.name == 'New' and self.partner_id:
            self.name = self.env['ir.sequence'].next_by_code('mrp.challan') or '/'
        return res


    # @api.multi
    # @api.onchange('mo_no')
    # def _process_name(self):
    #     # data = self.env['mrp.process'].search([('company_id', '=', self.env.user.company_id.id), ('company_id', '=', self.env.user.company_id.id)])
    #
    #     result = {}
    #     rows_list = []
    #     print("WORKINGGGG")
    #     if self.mo_no:
    #         self.env.cr.execute(
    #             """select process_name from mrp_production_processes where process_Id in (select id from mrp_production where name = %s)""",(self.mo_no.name,))
    #
    #         match_recs = self.env.cr.dictfetchall()
    #
    #         print("data process_name on change", match_recs)
    #         if match_recs is not None:
    #             rows_list = tuple([val["process_name"] for val in match_recs])
    #
    #         result['domain'] = {'process_name': [('id', 'in', rows_list)]}
    #     return result






    @api.multi
    def confirm_challan(self):

        if not self.item_lines:
            raise ValidationError("Please Define Items...")


        # challan = self.env['mrp.challan.gatepass.out'].search([('challan_no', '=', self.name)])
        # if challan:
        #     challan.write({'state': 'confirmed'})
        #     self.state = 'confirmed'
        # if not challan:
        mrp_challan_in = self.env["mrp.challan.in"]
        gate_pass_in_lines_data = []
        gate_pass_out_lines_data = []

        for val in self:
            for values in val.item_out_lines:
                lot_lines_data = []
                challan_out_item_lines = (0, False, {
                    'name': values.name.id,
                    'unit': values.unit.id,
                    'qty': values.qty,
                    'rate': values.rate,
                    'amount': values.amount,
                    'work_order_no': values.work_order_no.id,
                    # 'mo_no': values.mo_no.id,
                    'process_name':values.process_name.id,
                    'partner_id':values.partner_id.id,
                    'product_id': values.product_id.id,
                    'job_challan_out_line_id': values.id,
                    'job_challan_id': val.id,
                    # 'lots_wise_ids':lot_lines_data
                })
                gate_pass_out_lines_data.append(challan_out_item_lines)
            print('gate_pass_out_lines_data', gate_pass_out_lines_data)
            # print(A)
            # for value in val.item_out_lines:
            #     challan_in_item_lines = (0, False, {
            #         'name': value.name.id,
            #         'unit': value.unit.id,
            #         'qty': value.qty,
            #         'rate': value.rate,
            #         'amount': value.amount,
            #         'work_order_no': value.work_order_no.id,
            #         'mo_no': value.mo_no.id,
            #         'process_name': value.process_name.id,
            #         'product_id':value.product_id.id,
            #         'job_challan_in_line_id': value.id,
            #         # 'process_name': value.process_name.id,
            #     })
            #     gate_pass_in_lines_data.append(challan_in_item_lines)

            gate_pass_out_dict = {
                'challan_no': val.name,
                'out_item_check': val.out_item_check,
                # 'mo_date': val.mo_date,
                'challan_date': val.challan_date,
                'item_lines': gate_pass_out_lines_data,
                # 'item_in_lines':gate_pass_in_lines_data,
                'process_name': val.process_name.id,
                # 'state': 'confirmed',
                'dispatch_through': val.dispatch_through,
                'material_out': val.material_out,
                'date_and_time_of_issue': val.date_and_time_of_issue,
                'expected_return_date': val.expected_return_date,
                'partner_id': val.partner_id.id,
                # 'challan_type': val.challan_type,
                'job_challan_id':val.id,
                'name':'New',
                'gateout_create_type':'job_challan',
                'from_other_source':val.from_other_source

            }
            mrp_challan_in.create(gate_pass_out_dict)
        self.write({'state': 'confirmed'})
        self.write({'show_btn': False})


    # @api.multi
    # def reject_challan(self):
    #     self.write({'state': 'rejected'})
    #     self.write({'show_btn': False})


class MRPPChallanlines(models.Model):
    _name = 'mrp.challan.lines'

    name = fields.Many2one('product.template','Item Name')
    unit = fields.Many2one('product.uom','Unit')

    amount = fields.Float('Amount',compute='_amount_all',store=True)
    item_line_id = fields.Many2one('mrp.challan', "Item Line")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    product_id = fields.Many2one('product.product', clickable=True, string="Product")

    # mo_no = fields.Many2one('mrp.production', "MO number")
    work_order_no = fields.Many2one('mrp.workorder', string="Work Order No")
    process_name = fields.Many2one('mrp.routing', string="Process")
    partner_id = fields.Many2one('res.partner', string="Vendor")
    qty = fields.Float('Qty', default=1.0, digits=dp.get_precision('Manufacturing Unit of Measure'))
    rate = fields.Float('Rate', default=1.0)
    tracking = fields.Selection(related='product_id.product_tmpl_id.tracking', store=True)
    # lots_wise_ids = fields.One2many('mrp.lot.wise', 'lot_wise_id', string='Lot Wise')
    from_other_source = fields.Boolean("From other Source", related='item_line_id.from_other_source')


    # def issue_lot_wise_form(self):
    #     """
    #     Show Issue MRS LIne Form for Issuing the Quantity.
    #     """
    #     self.ensure_one()
    #     view = self.env.ref('mrp.mrp_challan_lines_form')
    #
    #     # self._create_tracking_lines(self.product_id, self.issue_id)
    #
    #     return {
    #         'name': _('Challan Detail'),
    #         'type': 'ir.actions.act_window',
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'mrp.challan.lines',
    #         'views': [(view.id, 'form')],
    #         'view_id': view.id,
    #         'target': 'new',
    #         'res_id': self.id,
    #     }



    @api.depends('qty', 'rate')
    def _amount_all(self):
        if self:
            for val in self:
                amt = 0.0
                if val.qty > 0 and val.rate > 0:
                    amt = val.qty * val.rate
                    val.amount = amt


    @api.multi
    @api.constrains('qty', 'amount')
    def _check_qty_and_rate(self):
        for line in self:
            if line.qty <=0.0 or line.amount <=0.0:
                raise ValidationError("Qty and Rate cannot be 0 in Challan Lines")

    @api.onchange('product_id')
    def onchange_product_id_new(self):
        if self :
            if self.product_id :
                print ("self productttttttttttt", self.product_id.uom_id)
                self.unit = self.product_id.uom_id.id


    # shubham last selling price logic
    @api.onchange('name', 'qty')
    def onchange_product_id(self):
        if self.name:
            self.unit = self.name.uom_id

            date_order = self.env['sale.order.line'].search(
                [('product_id', '=', self.name.id)],
                order='create_date desc', limit=1)

            if date_order:
                for val in date_order:
                    if val.price_unit:
                        print ("yessssss")
                        self.rate = val.price_unit
                    else:
                        print ('ese')
                        self.rate = self.name.list_price
            else:
                self.rate = self.name.list_price


            self.amount = self.rate * self.qty

class MRPPChallanOutlines(models.Model):
    _name = 'mrp.challan.out.lines'

    name = fields.Many2one('product.template', 'Item Name')
    unit = fields.Many2one('product.uom', 'Unit')
    qty = fields.Float('Qty', digits=dp.get_precision('Manufacturing Unit of Measure'))
    rate = fields.Float('Rate')
    amount = fields.Float('Amount',compute='_amount_all',store=True)
    item_line_id = fields.Many2one('mrp.challan', "Item Line")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    # mo_no = fields.Many2one('mrp.production', "MO number")
    work_order_no = fields.Many2one('mrp.workorder', string="Work Order No")
    process_name = fields.Many2one('mrp.routing', string="Process")
    partner_id = fields.Many2one('res.partner', string="Vendor")
    product_id = fields.Many2one('product.product', string="Product")
    from_other_source = fields.Boolean("From other Source", related='item_line_id.from_other_source')





    # shubham last selling price logic
    # @api.onchange('name', 'qty')
    # def onchange_product_id(self):
    #     if self.name:
    #         self.unit = self.name.uom_id
    #
    #         date_order = self.env['sale.order.line'].search(
    #             [('product_id', '=', self.name.id)],
    #             order='create_date desc', limit=1)
    #
    #         if date_order:
    #             for val in date_order:
    #                 if val.price_unit:
    #                     print ("yessssss")
    #                     self.rate = val.price_unit
    #                 else:
    #                     print ('ese')
    #                     self.rate = self.name.list_price
    #         else:
    #             self.rate = self.name.list_price
    #
    #         self.amount = self.rate * self.qty

    @api.onchange('product_id')
    def onchange_product_id_new(self):
        if self:
            if self.product_id:
                # print ("self productttttttttttt", self.product_id.uom_id)
                self.unit = self.product_id.uom_id.id
                self.rate = self.product_id.lst_price

    @api.depends('qty', 'rate')
    def _amount_all(self):
        if self:
            for val in self:
                amt = 0.0
                if val.qty > 0 and val.rate > 0:
                    amt = val.qty * val.rate
                    val.amount = amt



class ChallanIn(models.Model):
    _name = 'mrp.challan.in'
    _inherit = ['mail.thread', 'mail.activity.mixin', 'portal.mixin']

    name = fields.Char('Challan In No', size=256, default='New')
    challan_date = fields.Datetime('Challan Date' , default=fields.Datetime.now , readonly ="1")
    # mo_no = fields.Many2one('mrp.production',"MO number")
    # mo_date = fields.Datetime("MO Date")
    partner_id = fields.Many2one('res.partner', string="Customer",clickable=True)
    process_name = fields.Many2one('mrp.routing', string="Process")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    item_lines = fields.One2many('mrp.challan.in.lines','item_line_id', 'Item Lines')
    out_item_check = fields.Boolean("Output Items are not same as Input Items")
    show_btn = fields.Boolean('Show', default=False)
    dispatch_through = fields.Text("Dispatch Through")
    expected_return_date = fields.Date("Expected Return Date")
    date_and_time_of_issue = fields.Datetime("Date and Time of issue")
    material_out = fields.Boolean('Material Out', default=True)
    remarks =fields.Text("Remarks")
    # work_order_no = fields.Many2one('mrp.workorder', string="Work Order No")
    challan_no = fields.Char("Challan No")
    state = fields.Selection([
        ('draft', 'Draft'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
     ], string='State',
        copy=False, default='draft')
    challan_type = fields.Selection([
        ('returnable', 'Returnable'),
        ('non_returnable', 'Non Returnable'),
    ], string='Challan Type',
        copy=False, default='returnable')
    job_challan_id = fields.Many2one('mrp.challan', string="Job Challan")



    @api.model
    def create(self, values):
        if 'name' not in values or values['name'] == _('New'):
            values['name'] = self.env['ir.sequence'].next_by_code('mrp.challan.in') or _('New')

        res = super(ChallanIn, self).create(values)

        # if res.name == 'New':
        #     res.name = res.env['ir.sequence'].next_by_code('mrp.challan.in') or '/'

        return res

    @api.multi
    def reject_challan(self):
        self.write({'state': 'rejected'})

    # def scrap_btn_method(self):
    #     print("Scrap BTN")

    @api.multi
    def confirm_challan_in(self):
        if self.item_lines:

            mrp_challan_in = self.env["mrp.challan.in"]
            gate_pass_out_lines_data = []

            # for val in self.item_lines:
            #     if self.job_challan_id.item_out_lines:
            #         for values in self.job_challan_id.item_out_lines:
            #             if val.product_id == values.product_id:
            #                 product_quantity_lines = self.env['mrp.challan.in.lines'].search([('product_id', '=', val.product_id.id),('job_challan_id', '=', self.job_challan_id.id)])
            #                 total_quantity = 0.0
            #                 print('product_quantity_lines',product_quantity_lines)
            #                 for product_quantity in product_quantity_lines:
            #                     total_quantity = total_quantity + product_quantity.qty
            #                 print('total_quantity',total_quantity)
            #                 # print(a)
            #
            #                 if total_quantity < values.qty:
            #                     challan_out_item_lines = (0, False, {
            #                         'name': val.name.id,
            #                         'unit': val.unit.id,
            #                         'qty': values.qty - total_quantity,
            #                         'rate': values.rate,
            #                         'amount': (values.qty - val.qty)*val.rate,
            #                         # 'work_order_no': values.work_order_no.id,
            #                         'process_name': self.process_name.id,
            #                         'partner_id': self.partner_id.id,
            #                         'product_id': val.product_id.id,
            #                         'job_challan_id': self.job_challan_id.id,
            #                         # 'job_challan_out_line_id': values.id,
            #                     })
            #                     gate_pass_out_lines_data.append(challan_out_item_lines)

            for val in self.item_lines:
                if val.received_qty < val.qty:
                                    challan_out_item_lines = (0, False, {
                                        'name': val.name.id,
                                        'unit': val.unit.id,
                                        'qty': val.qty - val.received_qty,
                                        'rate': val.rate,
                                        'amount': (val.qty - val.received_qty)*val.rate,
                                        # 'work_order_no': values.work_order_no.id,
                                        'process_name': self.process_name.id,
                                        'partner_id': self.partner_id.id,
                                        'product_id': val.product_id.id,
                                        'job_challan_id': self.job_challan_id.id,
                                        # 'job_challan_out_line_id': values.id,
                                    })
                                    gate_pass_out_lines_data.append(challan_out_item_lines)

            if gate_pass_out_lines_data:
                gate_pass_out_dict = {
                    'challan_no': self.challan_no,
                    'out_item_check': self.out_item_check,
                    'challan_date': self.challan_date,
                    'item_lines': gate_pass_out_lines_data,
                    'process_name': self.process_name.id,
                    'dispatch_through': self.dispatch_through,
                    'material_out': self.material_out,
                    'date_and_time_of_issue': self.date_and_time_of_issue,
                    'expected_return_date': self.expected_return_date,
                    'partner_id': self.partner_id.id,
                    'job_challan_id': self.job_challan_id.id,
                    'name': 'New',
                    'gateout_create_type': 'job_challan',
                    # 'from_other_source': self.from_other_source

                }
                mrp_challan_in.create(gate_pass_out_dict)

            self.write({'show_btn': False})
            self.write({'state': 'confirmed'})
        else:
            raise ValidationError("Please Define Lines")




class ChallanInLines(models.Model):
    _name = 'mrp.challan.in.lines'

    name = fields.Many2one('product.template','Item Name')
    unit = fields.Many2one('product.uom','Unit')
    qty = fields.Float('Qty', digits=dp.get_precision('Manufacturing Unit of Measure'))
    rate = fields.Float('Rate')
    amount = fields.Float('Amount')
    item_line_id = fields.Many2one('mrp.challan.in', "Item Line")
    company_id = fields.Many2one('res.company', 'Company', required=True, index=True,
                                 default=lambda self: self.env.user.company_id.id)
    # ravi start at 7/2/2020 for commenting and chnaging string
    # received_qty = fields.Float("Received Quantity", digits=dp.get_precision('Manufacturing Unit of Measure'))
    received_qty = fields.Float("Dispatch Quantity", digits=dp.get_precision('Manufacturing Unit of Measure'))
    # ravi end
    scrap_qty = fields.Float("Scrap", digits=dp.get_precision('Manufacturing Unit of Measure'))
    scrap_unit = fields.Many2one("product.uom", string="Scarp Unit")

    # mo_no = fields.Many2one('mrp.production', "MO number")
    work_order_no = fields.Many2one('mrp.workorder', string="Work Order No")
    partner_id = fields.Many2one('res.partner', string="Vendor")
    process_name = fields.Many2one('mrp.routing', string="Process")
    product_id = fields.Many2one('product.product', string="Product")

    tracking = fields.Selection(related='product_id.product_tmpl_id.tracking', store=True)
    # lots_wise_ids = fields.One2many('mrp.lot.wise', 'lot_wise_id', string='Lot Wise')

    job_challan_id = fields.Many2one('mrp.challan', string="Job Challan")


    # def issue_lot_wise_form(self):
    #     self.ensure_one()
    #     view = self.env.ref('mrp.mrp_challan_in__lines_form')
    #     return {
    #         'name': _('Challan Detail'),
    #         'type': 'ir.actions.act_window',
    #         'view_type': 'form',
    #         'view_mode': 'form',
    #         'res_model': 'mrp.challan.in.lines',
    #         'views': [(view.id, 'form')],
    #         'view_id': view.id,
    #         'target': 'new',
    #         'res_id': self.id,
    #     }





    # shubham last selling price logic
    @api.onchange('name', 'qty')
    def onchange_product_id(self):
        if self.name:
            self.unit = self.name.uom_id

            date_order = self.env['sale.order.line'].search(
                [('product_id', '=', self.name.id)],
                order='create_date desc', limit=1)

            if date_order:
                for val in date_order:
                    if val.price_unit:
                        self.rate = val.price_unit
                    else:
                        self.rate = self.name.list_price
            else:
                self.rate = self.name.list_price


            self.amount = self.rate * self.qty



# ravi start at 11/2/2020 for adding new model for process line
class MrpProductionProcessLine(models.Model):
    _name = 'mrp.production.process.line'
    # _rec_name = ""

    process_line_id = fields.Many2one('mrp.production', 'Parent Mrp Production', index=True, ondelete='cascade', required=True)
    process_id = fields.Many2one('mrp.routing', 'Process', required=True)
    remarks = fields.Char('Remarks')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id)

# ravi end


# Yash - 30/10/2020 Class to have mrp order work center line
class MrpOrderWorkCenterLine(models.Model):
    _name = 'mrp.production.work.center.line'
    # _rec_name = ""
    operation_id = fields.Many2one('mrp.routing.workcenter', 'Operation', required=True)
    routing_line_id = fields.Many2one('mrp.production', 'Parent BoM', index=True, ondelete='cascade', required=True)
    workcenter_id = fields.Many2many('mrp.workcenter', string='Work Center', ondelete='restrict')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id)
