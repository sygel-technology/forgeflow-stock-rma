# -*- coding: utf-8 -*-
# © 2017 Eficent Business and IT Consulting Services S.L.
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from openerp import api, fields, models
from datetime import datetime


class RmaOrder(models.Model):
    _name = "rma.order"
    _inherit = ['mail.thread']

    @api.model
    def _get_default_type(self):
        if 'supplier' in self.env.context:
            return "supplier"
        return "customer"

    @api.multi
    def _compute_in_shipment_count(self):
        for rec in self:
            rec.in_shipment_count = len(rec.rma_line_ids.mapped(
                'procurement_ids.move_ids').filtered(
                lambda m: m.location_dest_id.usage == 'internal').mapped(
                'picking_id'))

    @api.multi
    def _compute_out_shipment_count(self):
        for rec in self:
            rec.out_shipment_count = len(rec.rma_line_ids.mapped(
                'procurement_ids.move_ids').filtered(
                lambda m: m.location_id.usage == 'internal').mapped(
                'picking_id'))

    @api.multi
    def _compute_supplier_line_count(self):
        self.supplier_line_count = len(self.rma_line_ids.filtered(
            lambda r: r.supplier_rma_line_ids))

    @api.multi
    def _compute_line_count(self):
        for rec in self:
            rec.line_count = len(rec._get_valid_lines())

    @api.model
    def _default_date_rma(self):
        return datetime.now()

    name = fields.Char(
        string='Group Number', index=True, copy=False)
    type = fields.Selection(
        [('customer', 'Customer'), ('supplier', 'Supplier')],
        string="Type", required=True, default=_get_default_type, readonly=True)
    reference = fields.Char(string='Partner Reference',
                            help="The partner reference of this RMA order.")
    comment = fields.Text('Additional Information')
    date_rma = fields.Datetime(string='Order Date', index=True,
                               default=_default_date_rma)
    partner_id = fields.Many2one(
        comodel_name='res.partner', string='Partner', required=True)
    rma_line_ids = fields.One2many('rma.order.line', 'rma_id',
                                   string='RMA lines')
    in_shipment_count = fields.Integer(compute=_compute_in_shipment_count,
                                       string='# of Invoices')
    out_shipment_count = fields.Integer(compute=_compute_out_shipment_count,
                                        string='# of Outgoing Shipments')
    line_count = fields.Integer(compute=_compute_line_count,
                                string='# of Outgoing Shipments')
    supplier_line_count = fields.Integer(compute=_compute_supplier_line_count,
                                         string='# of Outgoing Shipments')
    company_id = fields.Many2one('res.company', string='Company',
                                 required=True, default=lambda self:
                                 self.env.user.company_id)

    @api.model
    def create(self, vals):
        if (self.env.context.get('supplier') or
                vals.get('type') == 'supplier'):
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'rma.order.supplier')
        else:
            vals['name'] = self.env['ir.sequence'].next_by_code(
                'rma.order.customer')
        return super(RmaOrder, self).create(vals)

    @api.multi
    def action_view_in_shipments(self):
        action = self.env.ref('stock.action_picking_tree_all')
        result = action.read()[0]
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self.rma_line_ids:
            if line.type == 'customer':
                for move in line.move_ids:
                    if move.picking_id.location_id == customers:
                        picking_ids.append(move.picking_id.id)
            else:
                for move in line.move_ids:
                    if move.picking_id.location_id == suppliers:
                        picking_ids.append(move.picking_id.id)
        shipments = list(set(picking_ids))
        # choose the view_mode accordingly
        if len(shipments) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(shipments) + ")]"
        elif len(shipments) == 1:
            res = self.env.ref('stock.view_picking_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = shipments[0]
        return result

    @api.multi
    def action_view_out_shipments(self):
        action = self.env.ref('stock.action_picking_tree_all')
        result = action.read()[0]
        picking_ids = []
        suppliers = self.env.ref('stock.stock_location_suppliers')
        customers = self.env.ref('stock.stock_location_customers')
        for line in self.rma_line_ids:
            if line.type == 'customer':
                for move in line.move_ids:
                    if move.picking_id.location_id != customers:
                        picking_ids.append(move.picking_id.id)
            else:
                for move in line.move_ids:
                    if move.picking_id.location_id != suppliers:
                        picking_ids.append(move.picking_id.id)
        shipments = list(set(picking_ids))
        # choose the view_mode accordingly
        if len(shipments) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(shipments) + ")]"
        elif len(shipments) == 1:
            res = self.env.ref('stock.view_picking_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = shipments[0]
        return result

    @api.multi
    def _get_valid_lines(self):
        """:return: A recordset of rma lines.
        """
        self.ensure_one()
        return self.rma_line_ids

    @api.multi
    def action_view_lines(self):
        if self.type == 'customer':
            action = self.env.ref('rma.action_rma_customer_lines')
        else:
            action = self.env.ref('rma.action_rma_supplier_lines')
        result = action.read()[0]
        lines = self._get_valid_lines()
        # choose the view_mode accordingly
        if len(lines) != 1:
            result['domain'] = [('id', 'in', lines.ids)]
        elif len(lines) == 1:
            if self.type == 'customer':
                res = self.env.ref('rma.view_rma_line_form', False)
            else:
                res = self.env.ref('rma.view_rma_line_supplier_form', False)

            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = lines.id
        return result

    @api.multi
    def action_view_supplier_lines(self):
        action = self.env.ref('rma.action_rma_supplier_lines')
        result = action.read()[0]
        lines = self.rma_line_ids
        related_lines = [line.id for line in lines.supplier_rma_line_ids]
        # choose the view_mode accordingly
        if len(related_lines) != 1:
            result['domain'] = "[('id', 'in', " + \
                               str(related_lines) + ")]"
        elif len(related_lines) == 1:
            res = self.env.ref('rma.view_rma_line_supplier_form', False)
            result['views'] = [(res and res.id or False, 'form')]
            result['res_id'] = related_lines[0]
        return result