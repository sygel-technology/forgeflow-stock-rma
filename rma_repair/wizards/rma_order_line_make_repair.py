# Copyright 2020 ForgeFlow S.L.
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl.html).

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError


class RmaLineMakeRepair(models.TransientModel):
    _name = "rma.order.line.make.repair"
    _description = "Make Repair Order from RMA Line"

    item_ids = fields.One2many(
        comodel_name="rma.order.line.make.repair.item",
        inverse_name="wiz_id",
        string="Items",
    )

    @api.model
    def _prepare_item(self, line):
        return {
            "line_id": line.id,
            "product_id": line.product_id.id,
            "product_qty": line.qty_to_repair,
            "rma_id": line.rma_id.id,
            "out_route_id": line.out_route_id.id,
            "product_uom_id": line.uom_id.id,
            "partner_id": line.partner_id.id,
            "location_id": line.operation_id.repair_location_id.id
            or line.location_id.id,
            "invoice_method": line.operation_id.repair_invoice_method or "after_repair",
        }

    @api.model
    def default_get(self, fields_list):
        res = super(RmaLineMakeRepair, self).default_get(fields_list)
        rma_line_obj = self.env["rma.order.line"]
        rma_line_ids = self.env.context["active_ids"] or []
        active_model = self.env.context["active_model"]

        if not rma_line_ids:
            return res
        assert active_model == "rma.order.line", "Bad context propagation"
        items = []
        lines = rma_line_obj.browse(rma_line_ids)
        for line in lines:
            items.append([0, 0, self._prepare_item(line)])
        res["item_ids"] = items
        return res

    def make_repair_order(self):
        self.ensure_one()
        res = []
        repair_obj = self.env["repair.order"]
        for item in self.item_ids:
            rma_line = item.line_id
            data = item._prepare_repair_order(rma_line)
            repair = repair_obj.create(data)
            res.append(repair.id)
        return {
            "domain": [("id", "in", res)],
            "name": _("Repairs"),
            "view_mode": "tree,form",
            "res_model": "repair.order",
            "view_id": False,
            "context": False,
            "type": "ir.actions.act_window",
        }


class RmaLineMakeRepairItem(models.TransientModel):
    _name = "rma.order.line.make.repair.item"
    _description = "RMA Line Make Repair Item"

    @api.constrains("product_qty")
    def _check_prodcut_qty(self):
        for rec in self:
            if rec.product_qty <= 0.0:
                raise ValidationError(_("Quantity must be positive."))

    wiz_id = fields.Many2one(
        comodel_name="rma.order.line.make.repair", string="Wizard", ondelete="cascade"
    )
    line_id = fields.Many2one(
        comodel_name="rma.order.line", string="RMA", required=True
    )
    rma_id = fields.Many2one(
        comodel_name="rma.order", related="line_id.rma_id", string="RMA Order"
    )
    product_id = fields.Many2one(
        comodel_name="product.product", string="Product", readonly=True
    )
    product_qty = fields.Float(string="Quantity to repair", digits="Product UoS")
    product_uom_id = fields.Many2one(
        comodel_name="uom.uom", string="UoM", readonly=True
    )
    out_route_id = fields.Many2one(
        comodel_name="stock.route",
        string="Outbound Route",
        domain=[("rma_selectable", "=", True)],
    )
    partner_id = fields.Many2one(
        comodel_name="res.partner",
        string="Customer",
        required=False,
        domain=[("customer", "=", True)],
        readonly=True,
    )
    location_id = fields.Many2one(
        comodel_name="stock.location", string="Location", required=True
    )
    invoice_method = fields.Selection(
        selection=[
            ("none", "No Invoice"),
            ("b4repair", "Before Repair"),
            ("after_repair", "After Repair"),
        ],
        required=True,
        help="Selecting 'Before Repair' or 'After Repair' will allow you "
        "to generate invoice before or after the repair is done "
        "respectively. 'No invoice' means you don't want to generate "
        "invoice for this repair order.",
    )

    def _prepare_repair_order(self, rma_line):
        self.ensure_one()
        addr = rma_line.partner_id.address_get(["delivery", "invoice"])
        return {
            "product_id": rma_line.product_id.id,
            "partner_id": rma_line.partner_id.id,
            "pricelist_id": rma_line.partner_id.property_product_pricelist.id or False,
            "product_qty": self.product_qty,
            "rma_line_id": rma_line.id,
            "product_uom": rma_line.product_id.uom_po_id.id,
            "company_id": rma_line.company_id.id,
            "location_id": self.location_id.id,
            "invoice_method": self.invoice_method,
            "address_id": addr["delivery"],
            "partner_invoice_id": addr["invoice"],
            "lot_id": rma_line.lot_id.id,
        }
