/** @odoo-module **/

import { onWillRender } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

const DAY_LETTERS = ["M", "T", "W", "T", "F", "S", "S"];
const MAX_DAYS = 366 * 5; // safety cap on chart width

/**
 * Project Schedule list with Gantt day columns appended to the same rows.
 * The chart starts on the Monday of the Project Start Date's week and runs
 * to the Sunday of the week of the last task end.
 */
export class ScheduleGanttListRenderer extends ListRenderer {
    static template = "mefs_budget_planning.ScheduleGanttListRenderer";
    static recordRowTemplate = "mefs_budget_planning.ScheduleGanttListRenderer.RecordRow";
    static useMagicColumnWidths = false;

    setup() {
        super.setup();
        this.gantt = { days: [], weeks: [] };
        onWillRender(() => {
            this.gantt = this.computeGantt();
        });
    }

    get nbCols() {
        return super.nbCols + this.gantt.days.length;
    }

    get ganttLeadColspan() {
        return this.columns.length + (this.hasSelectors ? 1 : 0);
    }

    computeGantt() {
        const parent = this.props.list._parent;
        const projectStart = parent && parent.data.project_start_date;
        const dates = [];
        for (const record of this.props.list.records) {
            if (record.data.date_start) {
                dates.push(record.data.date_start);
            }
            if (record.data.date_end) {
                dates.push(record.data.date_end);
            }
        }
        const first = projectStart || (dates.length && dates.reduce((a, b) => (a < b ? a : b)));
        if (!first) {
            return { days: [], weeks: [] };
        }
        let last = dates.reduce((a, b) => (a > b ? a : b), first);
        const starts = dates.filter((d) => d < first);
        const begin = (starts.length ? starts.reduce((a, b) => (a < b ? a : b)) : first)
            .startOf("week") // ISO week: Monday
            .startOf("day");
        const end = last.endOf("week").startOf("day");

        const days = [];
        for (let d = begin; d <= end && days.length < MAX_DAYS; d = d.plus({ days: 1 })) {
            days.push({
                key: d.toISODate(),
                letter: DAY_LETTERS[d.weekday - 1],
                number: d.day,
                weekend: d.weekday >= 6,
                weekStart: d.weekday === 1,
            });
        }
        const weeks = [];
        for (let i = 0; i < days.length; i += 7) {
            const monday = begin.plus({ days: i });
            weeks.push({
                key: monday.toISODate(),
                label: monday.setLocale("en").toFormat("LLL d, yyyy"),
            });
        }
        return { days, weeks };
    }

    getGanttCellClass(record, day) {
        const classes = ["o_gantt_cell"];
        if (day.weekend) {
            classes.push("o_gantt_weekend");
        }
        if (day.weekStart) {
            classes.push("o_gantt_week_start");
        }
        const start = record.data.date_start && record.data.date_start.toISODate();
        const end = record.data.date_end && record.data.date_end.toISODate();
        if (start && end && start <= day.key && day.key <= end) {
            classes.push("o_gantt_bar");
            if (day.key === start) {
                classes.push("o_gantt_bar_start");
            }
            if (day.key === end) {
                classes.push("o_gantt_bar_end");
            }
        }
        return classes.join(" ");
    }
}

export class ScheduleGanttX2ManyField extends X2ManyField {
    static components = { ...X2ManyField.components, ListRenderer: ScheduleGanttListRenderer };
}

registry.category("fields").add("budget_schedule_gantt", {
    ...x2ManyField,
    component: ScheduleGanttX2ManyField,
});
