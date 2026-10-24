/** @odoo-module **/

import { Component } from "@odoo/owl";
import { DropdownItem } from "@web/core/dropdown/dropdown_item";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { STATIC_ACTIONS_GROUP_NUMBER } from "@web/search/action_menus/action_menus";

const cogMenuRegistry = registry.category("cogMenu");

export class EquipmentTimesheetExportMenu extends Component {
    static template = "equipment_timesheet.ExportReportMenu";
    static components = { DropdownItem };
    static props = {};

    setup() {
        this.action = useService("action");
    }

    exportReport() {
        const searchContext = this.env.searchModel?.context || {};
        const resModel = this.env.searchModel?.resModel || this.env.model?.root?.resModel;
        const viewType = this.env.config?.viewType;
        const ctx = {};

        if (searchContext.default_project_id) {
            ctx.default_export_scope = "project";
            ctx.default_project_id = searchContext.default_project_id;
        } else if (resModel === "project.project") {
            const activeId = this.env.model?.root?.resId;
            if (activeId && viewType === "form") {
                ctx.default_export_scope = "project";
                ctx.default_project_id = activeId;
            } else {
                ctx.default_export_scope = "all";
            }
        } else if (resModel === "equipment.timesheet") {
            const activeId = this.env.model?.root?.resId;
            if (activeId && viewType === "form") {
                ctx.default_export_scope = "timesheet";
                ctx.default_timesheet_id = activeId;
            } else {
                ctx.default_export_scope = "all";
            }
        } else {
            ctx.default_export_scope = "all";
        }

        this.action.doAction({
            name: "Export Report",
            type: "ir.actions.act_window",
            res_model: "equipment.timesheet.export.wizard",
            view_mode: "form",
            views: [[false, "form"]],
            target: "new",
            context: ctx,
        });
    }
}

export const equipmentTimesheetExportMenuItem = {
    Component: EquipmentTimesheetExportMenu,
    groupNumber: STATIC_ACTIONS_GROUP_NUMBER,
    isDisplayed: (env) => {
        if (env.isSmall) {
            return false;
        }
        const resModel = env.searchModel?.resModel || env.model?.root?.resModel;
        return ["project.project", "equipment.timesheet"].includes(resModel);
    },
};

cogMenuRegistry.add("equipment-timesheet-export-menu", equipmentTimesheetExportMenuItem, { sequence: 1 });
