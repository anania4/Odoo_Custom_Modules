/** @odoo-module **/

import { useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

/**
 * Cost groups of the Project Estimated Cost table. Closed, a group shows only
 * its total column; open, it shows all its columns. The toggle sits in the
 * title of the group's total column.
 */
const GROUPS = [
    {
        key: "material",
        label: "Material",
        total: "total_material_cost",
        fields: [
            "material_product_id", "material_uom_id", "material_consumption",
            "material_unit_price", "material_price_per_work_unit",
            "total_material_cost", "material_categ_id",
        ],
        buttons: ["action_add_material_row"],
    },
    {
        key: "equipment",
        label: "Equipment",
        total: "total_equipment_cost",
        fields: [
            "equipment_product_id", "equipment_count", "equipment_output",
            "equipment_rate_hour", "equipment_rental_hours",
            "total_equipment_cost", "equipment_categ_id",
        ],
        buttons: [],
    },
    {
        key: "manpower",
        label: "Manpower",
        total: "total_manpower_cost",
        fields: [
            "manpower_product_id", "manpower_count", "manpower_price_day",
            "total_manpower_cost", "labour_categ_id",
        ],
        buttons: [],
    },
    {
        key: "subcontract",
        label: "Subcontractor",
        total: "total_subcontractor_cost",
        fields: ["subcontract_cost_unit", "total_subcontractor_cost", "subcontract_categ_id"],
        buttons: [],
    },
];

function groupOf(column) {
    if (column.type === "field") {
        return GROUPS.find((g) => g.fields.includes(column.name)) || null;
    }
    if (column.type === "button_group") {
        const names = (column.buttons || []).map((b) => b.name);
        return GROUPS.find((g) => g.buttons.some((n) => names.includes(n))) || null;
    }
    return null;
}

export class EstimateGroupsListRenderer extends ListRenderer {
    static template = "mefs_budget_planning.EstimateGroupsListRenderer";

    setup() {
        super.setup();
        // Always starts minimized: every group closed, only the totals shown
        this.groupState = useState(Object.fromEntries(GROUPS.map((g) => [g.key, false])));
    }

    toggleGroup(key) {
        this.groupState[key] = !this.groupState[key];
    }

    /** The group whose total column this is (gets the toggle), else null. */
    totalGroupOf(column) {
        return GROUPS.find((g) => column.type === "field" && column.name === g.total) || null;
    }

    /** Closed groups keep only their total column. */
    getActiveColumns(list) {
        return super.getActiveColumns(list).filter((column) => {
            const group = groupOf(column);
            if (!group || this.groupState[group.key]) {
                return true;
            }
            return column.type === "field" && column.name === group.total;
        });
    }
}

export class EstimateGroupsX2ManyField extends X2ManyField {
    static components = { ...X2ManyField.components, ListRenderer: EstimateGroupsListRenderer };
}

registry.category("fields").add("budget_estimate_groups", {
    ...x2ManyField,
    component: EstimateGroupsX2ManyField,
});
