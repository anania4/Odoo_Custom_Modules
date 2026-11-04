/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { ORM } from "@web/core/orm_service";

let currentProjectType = null;

patch(ORM.prototype, {
    async call(model, method, args = [], kwargs = {}) {
        const result = await super.call(model, method, args, kwargs);
        if (model === "project.project" && method === "web_read" && result?.length && result[0].project_type) {
            currentProjectType = result[0].project_type;
        }
        return result;
    },
    searchRead(model, domain, fields, kwargs = {}) {
        if (model === "project.project.stage" && currentProjectType) {
            kwargs = Object.assign({}, kwargs);
            kwargs.context = Object.assign({}, kwargs.context || {}, {
                pipeline_project_type: currentProjectType,
            });
        }
        return super.searchRead(model, domain, fields, kwargs);
    },
});
