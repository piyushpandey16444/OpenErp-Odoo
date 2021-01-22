# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

from odoo import api, fields, models, _
from odoo.addons import decimal_precision as dp
from odoo.exceptions import UserError, ValidationError
from odoo.tools import float_round


class MrpBom(models.Model):
    """ Defines bills of material for a product or a product template """
    _name = 'mrp.bom'
    _description = 'Bill of Material'
    _inherit = ['mail.thread']
    _rec_name = 'product_tmpl_id'
    _order = "sequence"

    def _get_default_product_uom_id(self):
        return self.env['product.uom'].search([], limit=1, order='id').id

    code = fields.Char('Reference')
    active = fields.Boolean(
        'Active', default=True,
        help="If the active field is set to False, it will allow you to hide the bills of material without removing it.")
    type = fields.Selection([
        ('normal', 'Manufacture this product'),
        ('phantom', 'Kit')], 'BoM Type',
        default='normal', required=True)
    product_tmpl_id = fields.Many2one(
        'product.template', 'Product',
        domain="[('type', 'in', ['product', 'consu'])]", required=True)
    product_id = fields.Many2one(
        'product.product', 'Product Variant',
        domain="['&', ('product_tmpl_id', '=', product_tmpl_id), ('type', 'in', ['product', 'consu'])]",
        help="If a product variant is defined the BOM is available only for this product.")
    bom_line_ids = fields.One2many('mrp.bom.line', 'bom_id', 'BoM Lines', copy=True)
    product_qty = fields.Float(
        'Quantity', default=1.0,
        digits=dp.get_precision('Unit of Measure'), required=True)
    product_uom_id = fields.Many2one(
        'product.uom', 'Product Unit of Measure',
        default=_get_default_product_uom_id, oldname='product_uom', required=True,
        help="Unit of Measure (Unit of Measure) is the unit of measurement for the inventory control")
    sequence = fields.Integer('Sequence', help="Gives the sequence order when displaying a list of bills of material.")
    routing_id = fields.Many2one(
        'mrp.routing', 'Routing',
        help="The operations for producing this BoM.  When a routing is specified, the production orders will "
             " be executed through work orders, otherwise everything is processed in the production order itself. ")
    ready_to_produce = fields.Selection([
        ('all_available', 'All components available'),
        ('asap', 'The components of 1st operation')], string='Manufacturing Readiness',
        default='asap', required=True)
    picking_type_id = fields.Many2one(
        'stock.picking.type', 'Operation Type', domain=[('code', '=', 'mrp_operation')],
        help=u"When a procurement has a ‘produce’ route with a operation type set, it will try to create "
             "a Manufacturing Order for that product using a BoM of the same operation type. That allows "
             "to define procurement rules which trigger different manufacturing orders with different BoMs.")
    company_id = fields.Many2one(
        'res.company', 'Company',
        default=lambda self: self.env['res.company']._company_default_get('mrp.bom'),
        required=True)



    # ravi start at 11/2/2020 for new field_process ids
    process_line_ids = fields.One2many('mrp.bom.process.line', 'process_line_id', 'Process Lines', copy=True)
    # ravi end

    # ravi start at 11/2/2020 for new field_process ids
    routing_line_ids = fields.One2many('mrp.bom.work.center.line', 'routing_line_id', 'Work Center Operations', copy=True)
    # ravi end


    @api.constrains('product_id', 'product_tmpl_id', 'bom_line_ids')
    def _check_product_recursion(self):
        for bom in self:
            if bom.bom_line_ids.filtered(lambda x: x.product_id.product_tmpl_id == bom.product_tmpl_id):
                raise ValidationError(_('BoM line product %s should not be same as BoM product.') % bom.display_name)
        operation_ids = []

        #Himanshu mrp 16-12-2020 if workcenter_operation tab is empty then raise the error to add operations.
        if not self.routing_line_ids:
            raise ValidationError(_("Please add the operations in the work center operation tab"))
        else:
            for line in self.routing_line_ids:
                for op in line.operation_id:
                    operation_ids.append(op.mrp_operation_id)
        #End Himanshu
        # operation_ids = [op.mrp_operation_id for op in self.routing_line_ids.operation_id]
        if not self.bom_line_ids:
            raise ValidationError("Please add minimum 1 product in Components Tab.")
        else:
            for line in self.bom_line_ids:
                if not line.operation_id:
                    raise ValidationError(
                        "Please select a consumed operation in line {0}".format(str(line.product_id.name)))
                elif operation_ids and line.operation_id.mrp_operation_id not in operation_ids:
                    raise ValidationError("Please select operation from WorkCenter operations.")

    @api.onchange('product_uom_id')
    def onchange_product_uom_id(self):
        res = {}
        if not self.product_uom_id or not self.product_tmpl_id:
            return
        if self.product_uom_id.category_id.id != self.product_tmpl_id.uom_id.category_id.id:
            self.product_uom_id = self.product_tmpl_id.uom_id.id
            res['warning'] = {'title': _('Warning'), 'message': _('The Product Unit of Measure you chose has a different category than in the product form.')}
        return res

    @api.onchange('product_tmpl_id')
    def onchange_product_tmpl_id(self):
        if self.product_tmpl_id:
            self.product_uom_id = self.product_tmpl_id.uom_id.id
            if self.product_id.product_tmpl_id != self.product_tmpl_id:
                self.product_id = False

    @api.onchange('routing_id')
    def onchange_routing_id(self):
        work_center_line_data = []
        self.routing_line_ids = ""
        if self.routing_id.operation_ids:
            for values in self.routing_id.operation_ids:
                name = values.mrp_operation_id.name or ''
                workcenter_ids = []
                for center in values.workcenter_id:
                    workcenter_id = center or False,
                    if workcenter_id:
                        workcenter_ids.append(workcenter_id[0].id)

                values_work_center_data = (0, False, {
                    'workcenter_id': workcenter_ids,
                    # 'name': name,
                    'operation_id': values
                })
                work_center_line_data.append(values_work_center_data)
                #Himanshu error
        if work_center_line_data:
            self.routing_line_ids = work_center_line_data
    
        for line in self.bom_line_ids:
            line.operation_id = False


    @api.multi
    def name_get(self):
        return [(bom.id, '%s%s' % (bom.code and '%s: ' % bom.code or '', bom.product_tmpl_id.display_name)) for bom in self]

    @api.multi
    def unlink(self):
        if self.env['mrp.production'].search([('bom_id', 'in', self.ids), ('state', 'not in', ['done', 'cancel'])], limit=1):
            raise UserError(_('You can not delete a Bill of Material with running manufacturing orders.\nPlease close or cancel it first.'))
        return super(MrpBom, self).unlink()

    @api.model
    def _bom_find(self, product_tmpl=None, product=None, picking_type=None, company_id=False):
        """ Finds BoM for particular product, picking and company """
        if product:
            if not product_tmpl:
                product_tmpl = product.product_tmpl_id
            domain = ['|', ('product_id', '=', product.id), '&', ('product_id', '=', False), ('product_tmpl_id', '=', product_tmpl.id)]
        elif product_tmpl:
            domain = [('product_tmpl_id', '=', product_tmpl.id)]
        else:
            # neither product nor template, makes no sense to search
            return False
        if picking_type:
            domain += ['|', ('picking_type_id', '=', picking_type.id), ('picking_type_id', '=', False)]
        if company_id or self.env.context.get('company_id'):
            domain = domain + [('company_id', '=', company_id or self.env.context.get('company_id'))]
        # order to prioritize bom with product_id over the one without
        return self.search(domain, order='sequence, product_id', limit=1)

    def explode(self, product, quantity, picking_type=False):
        """
            Explodes the BoM and creates two lists with all the information you need: bom_done and line_done
            Quantity describes the number of times you need the BoM: so the quantity divided by the number created by the BoM
            and converted into its UoM
        """
        from collections import defaultdict

        graph = defaultdict(list)
        V = set()

        def check_cycle(v, visited, recStack, graph):
            visited[v] = True
            recStack[v] = True
            for neighbour in graph[v]:
                if visited[neighbour] == False:
                    if check_cycle(neighbour, visited, recStack, graph) == True:
                        return True
                elif recStack[neighbour] == True:
                    return True
            recStack[v] = False
            return False

        boms_done = [(self, {'qty': quantity, 'product': product, 'original_qty': quantity, 'parent_line': False})]
        lines_done = []
        V |= set([product.product_tmpl_id.id])

        bom_lines = [(bom_line, product, quantity, False) for bom_line in self.bom_line_ids]
        for bom_line in self.bom_line_ids:
            V |= set([bom_line.product_id.product_tmpl_id.id])
            graph[product.product_tmpl_id.id].append(bom_line.product_id.product_tmpl_id.id)
        while bom_lines:
            current_line, current_product, current_qty, parent_line = bom_lines[0]
            bom_lines = bom_lines[1:]

            if current_line._skip_bom_line(current_product):
                continue

            line_quantity = current_qty * current_line.product_qty
            bom = self._bom_find(product=current_line.product_id, picking_type=picking_type or self.picking_type_id, company_id=self.company_id.id)
            if bom.type == 'phantom':
                converted_line_quantity = current_line.product_uom_id._compute_quantity(line_quantity / bom.product_qty, bom.product_uom_id)
                bom_lines = [(line, current_line.product_id, converted_line_quantity, current_line) for line in bom.bom_line_ids] + bom_lines
                for bom_line in bom.bom_line_ids:
                    graph[current_line.product_id.product_tmpl_id.id].append(bom_line.product_id.product_tmpl_id.id)
                    if bom_line.product_id.product_tmpl_id.id in V and check_cycle(bom_line.product_id.product_tmpl_id.id, {key: False for  key in V}, {key: False for  key in V}, graph):
                        raise UserError(_('Recursion error!  A product with a Bill of Material should not have itself in its BoM or child BoMs!'))
                    V |= set([bom_line.product_id.product_tmpl_id.id])
                boms_done.append((bom, {'qty': converted_line_quantity, 'product': current_product, 'original_qty': quantity, 'parent_line': current_line}))
            else:
                # We round up here because the user expects that if he has to consume a little more, the whole UOM unit
                # should be consumed.
                rounding = current_line.product_uom_id.rounding
                line_quantity = float_round(line_quantity, precision_rounding=rounding, rounding_method='UP')
                lines_done.append((current_line, {'qty': line_quantity, 'product': current_product, 'original_qty': quantity, 'parent_line': parent_line}))

        return boms_done, lines_done


#  ravi start 11/2/2020 for adding create and write function
    @api.model
    def create(self, values):
        res = super(MrpBom, self).create(values)

        already_created_boms = len(self.env['mrp.bom'].search([('product_tmpl_id', '=', res.product_tmpl_id.id)]))

        res.sequence = already_created_boms

        # temp_all_process_in_process = [process.process_id.id for process in
        #                                  res.process_line_ids]
        #
        # for val in res.bom_line_ids:
        #     if val.operation_id:
        #         if val.operation_id.id not in temp_all_process_in_process:
        #             raise ValidationError("Process in Components Tab must be in Process tab...")

        # if res.routing_line_ids == False:
        #     raise ValidationError("You cannot validate this receipt, Bill should be Available !")


        if res.bom_line_ids:
            all_process = []
            for val in res.process_line_ids:
                all_process.append(val.process_id.id)

            # for val in res.bom_line_ids:
            #     if val.operation_id.id not in all_process:
            #         raise ValidationError("Please Select A valid Consumed Operation")
        return res

    @api.multi
    def write(self, values):
        res = super(MrpBom, self).write(values)

        # temp_all_process_in_process = [process.process_id.id for process in
        #                                self.process_line_ids]
        #
        # for val in self.bom_line_ids:
        #     if val.operation_id:
        #         if val.operation_id.id not in temp_all_process_in_process:
        #             raise ValidationError("Process in Components Tab must be in Process tab...")


        if self.bom_line_ids:
            all_process = []
            for val in self.process_line_ids:
                all_process.append(val.process_id.id)

            # for val in self.bom_line_ids:
            #     if val.operation_id.id not in all_process:
            #         raise ValidationError("Please Select A valid Consumed Operation")
        return res
#  ravi end



class MrpBomLine(models.Model):
    _name = 'mrp.bom.line'
    _order = "sequence, id"
    _rec_name = "product_id"

    def _get_default_product_uom_id(self):
        return self.env['product.uom'].search([], limit=1, order='id').id

    product_id = fields.Many2one(
        'product.product', 'Product', required=True)
    product_qty = fields.Float(
        'Product Quantity', default=1.0,
        digits=dp.get_precision('Product Unit of Measure'), required=True)
    product_uom_id = fields.Many2one(
        'product.uom', 'Product Unit of Measure',
        default=_get_default_product_uom_id,
        oldname='product_uom', required=True,
        help="Unit of Measure (Unit of Measure) is the unit of measurement for the inventory control")
    sequence = fields.Integer(
        'Sequence', default=1,
        help="Gives the sequence order when displaying.")
    routing_id = fields.Many2one(
        'mrp.routing', 'Routing',
        related='bom_id.routing_id', store=True,
        help="The list of operations to produce the finished product. The routing is mainly used to "
             "compute work center costs during operations and to plan future loads on work centers "
             "based on production planning.")
    bom_id = fields.Many2one(
        'mrp.bom', 'Parent BoM',
        index=True, ondelete='cascade', required=True)
    attribute_value_ids = fields.Many2many(
        'product.attribute.value', string='Variants',
        help="BOM Product Variants needed form apply this line.")
    # ravi start at commenting the field and adding new filed
    operation_id = fields.Many2one('mrp.routing.workcenter', 'Consumed in Operation',
                                   help="The operation where the components are consumed, or the finished products created.")
    # operation_id = fields.Many2one('mrp.routing', 'Consumed in Operation', help="The operation where the components are consumed, or the finished products created.")
    # ravi end
    child_bom_id = fields.Many2one(
        'mrp.bom', 'Sub BoM', compute='_compute_child_bom_id')
    child_line_ids = fields.One2many(
        'mrp.bom.line', string="BOM lines of the referred bom",
        compute='_compute_child_line_ids')
    has_attachments = fields.Boolean('Has Attachments', compute='_compute_has_attachments')

    _sql_constraints = [
        ('bom_qty_zero', 'CHECK (product_qty>=0)', 'All product quantities must be greater or equal to 0.\n'
            'Lines with 0 quantities can be used as optional lines. \n'
            'You should install the mrp_byproduct module if you want to manage extra products on BoMs !'),
    ]

    @api.one
    @api.depends('product_id', 'bom_id')
    def _compute_child_bom_id(self):
        if not self.product_id:
            self.child_bom_id = False
        else:
            self.child_bom_id = self.env['mrp.bom']._bom_find(
                product_tmpl=self.product_id.product_tmpl_id,
                product=self.product_id,
                picking_type=self.bom_id.picking_type_id)

    @api.one
    @api.depends('product_id')
    def _compute_has_attachments(self):
        nbr_attach = self.env['ir.attachment'].search_count([
            '|',
            '&', ('res_model', '=', 'product.product'), ('res_id', '=', self.product_id.id),
            '&', ('res_model', '=', 'product.template'), ('res_id', '=', self.product_id.product_tmpl_id.id)])
        self.has_attachments = bool(nbr_attach)

    @api.one
    @api.depends('child_bom_id')
    def _compute_child_line_ids(self):
        """ If the BOM line refers to a BOM, return the ids of the child BOM lines """
        self.child_line_ids = self.child_bom_id.bom_line_ids.ids

    @api.onchange('product_uom_id')
    def onchange_product_uom_id(self):
        res = {}
        if not self.product_uom_id or not self.product_id:
            return res
        if self.product_uom_id.category_id != self.product_id.uom_id.category_id:
            self.product_uom_id = self.product_id.uom_id.id
            res['warning'] = {'title': _('Warning'), 'message': _('The Product Unit of Measure you chose has a different category than in the product form.')}
        return res

    @api.onchange('product_id')
    def onchange_product_id(self):
        if self.product_id:
            self.product_uom_id = self.product_id.uom_id.id

    @api.model
    def create(self, values):
        if 'product_id' in values and 'product_uom_id' not in values:
            values['product_uom_id'] = self.env['product.product'].browse(values['product_id']).uom_id.id
        return super(MrpBomLine, self).create(values)

    def _skip_bom_line(self, product):
        """ Control if a BoM line should be produce, can be inherited for add
        custom control. It currently checks that all variant values are in the
        product. """
        if self.attribute_value_ids:
            if not product or self.attribute_value_ids - product.attribute_value_ids:
                return True
        return False

    @api.multi
    def action_see_attachments(self):
        domain = [
            '|',
            '&', ('res_model', '=', 'product.product'), ('res_id', '=', self.product_id.id),
            '&', ('res_model', '=', 'product.template'), ('res_id', '=', self.product_id.product_tmpl_id.id)]
        attachment_view = self.env.ref('mrp.view_document_file_kanban_mrp')
        return {
            'name': _('Attachments'),
            'domain': domain,
            'res_model': 'mrp.document',
            'type': 'ir.actions.act_window',
            'view_id': attachment_view.id,
            'views': [(attachment_view.id, 'kanban'), (False, 'form')],
            'view_mode': 'kanban,tree,form',
            'view_type': 'form',
            'help': _('''<p class="oe_view_nocontent_create">
                        Click to upload files to your product.
                    </p><p>
                        Use this feature to store any files, like drawings or specifications.
                    </p>'''),
            'limit': 80,
            'context': "{'default_res_model': '%s','default_res_id': %d}" % ('product.product', self.product_id.id)
        }

    # def _get_default_operation(self):
    #     for operation in self.routing_id.operation_ids:
    #         pass


# ravi start at 11/2/2020 for adding new model for process line
class MrpBomProcessLine(models.Model):
    _name = 'mrp.bom.process.line'
    # _rec_name = ""

    process_line_id = fields.Many2one('mrp.bom', 'Parent BoM', index=True, ondelete='cascade', required=True)
    process_id = fields.Many2one('mrp.routing.workcenter', 'Process', required=True)
    remarks = fields.Char('Remarks')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id)

# ravi end


# Yash start at 28/10/2020 for adding new model for process line
class MrpBomWorkCenterLine(models.Model):
    _name = 'mrp.bom.work.center.line'
    # _rec_name = ""
    # name = fields.Char('Operation', required=True)
    operation_id = fields.Many2one('mrp.routing.workcenter', 'Operation',required=True)
    routing_line_id = fields.Many2one('mrp.bom', 'Parent BoM', index=True, ondelete='cascade', required=True)
    workcenter_id = fields.Many2many('mrp.workcenter', string='Work Center', ondelete='restrict')
    company_id = fields.Many2one('res.company', 'Company', default=lambda self: self.env.user.company_id.id)

    @api.onchange('operation_id')
    def onchange_operation_id(self):
        self.workcenter_id = self.operation_id.workcenter_id

# Yash end
