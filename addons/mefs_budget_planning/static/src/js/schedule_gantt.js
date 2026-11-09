/** @odoo-module **/

import { onWillRender } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { ListRenderer } from "@web/views/list/list_renderer";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

const DAY_LETTERS = ["M", "T", "W", "T", "F", "S", "S"];
const MAX_DAYS = 366 * 5; // safety cap on chart width
const DAY_WIDTH = 24;
const MIN_WIDTH = 30;
const DEFAULT_WIDTHS = {
    boq_line_id: 70,
    task: 220,
    quantity: 80,
    uom_id: 70,
    progress: 120,
    date_start: 110,
    duration_days: 90,
    date_end: 110,
};

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
        // Odoo's automatic widths are off (they cannot handle the extra header
        // rows), so this table sizes its columns with a <colgroup> and has its
        // own drag-to-resize on the column titles.
        this.ganttWidths = {};
        this.ganttResizing = false;
        const renderer = this;
        this.columnWidths = {
            onStartResize: (ev) => this.onGanttStartResize(ev),
            get resizing() {
                return renderer.ganttResizing;
            },
        };
    }

    getColumnWidth(column) {
        if (column.type !== "field") {
            return this.ganttWidths[column.id] || 40;
        }
        if (this.ganttWidths[column.name]) {
            return this.ganttWidths[column.name];
        }
        if (column.widget === "handle") {
            return 30;
        }
        return DEFAULT_WIDTHS[column.name] || 100;
    }

    get ganttTableWidth() {
        let width = this.columns.reduce((sum, column) => sum + this.getColumnWidth(column), 0);
        width += this.gantt.days.length * DAY_WIDTH;
        width += (this.hasSelectors ? 40 : 0) + (this.hasOpenFormViewColumn ? 60 : 0);
        width += this.hasActionsColumn ? 40 : 0;
        return width;
    }

    onGanttStartResize(ev) {
        const th = ev.target.closest("th");
        const name = th && th.dataset.name;
        const table = this.tableRef.el;
        const col = name && table.querySelector(`col[data-name="${name}"]`);
        if (!col) {
            return;
        }
        this.ganttResizing = true;
        const startX = ev.clientX;
        const startWidth = col.getBoundingClientRect().width || parseInt(col.style.width) || 100;
        const startTableWidth = table.getBoundingClientRect().width;
        let newWidth = startWidth;
        table.classList.add("o_resizing");

        const onMove = (moveEv) => {
            moveEv.preventDefault();
            newWidth = Math.max(MIN_WIDTH, Math.round(startWidth + moveEv.clientX - startX));
            col.style.width = `${newWidth}px`;
            table.style.width = `${Math.round(startTableWidth + newWidth - startWidth)}px`;
        };
        const onStop = (stopEv) => {
            if (stopEv.type === "pointerdown" && stopEv.button === 0) {
                return;
            }
            window.removeEventListener("pointermove", onMove);
            for (const type of ["pointerup", "pointerdown", "keydown"]) {
                window.removeEventListener(type, onStop);
            }
            this.ganttWidths[name] = newWidth;
            table.classList.remove("o_resizing");
            this.ganttResizing = false;
        };
        window.addEventListener("pointermove", onMove);
        for (const type of ["pointerup", "pointerdown", "keydown"]) {
            window.addEventListener(type, onStop);
        }
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

        const today = luxon.DateTime.local().toISODate();
        const days = [];
        for (let d = begin; d <= end && days.length < MAX_DAYS; d = d.plus({ days: 1 })) {
            const key = d.toISODate();
            days.push({
                key,
                letter: DAY_LETTERS[d.weekday - 1],
                number: d.day,
                weekend: d.weekday >= 6,
                weekStart: d.weekday === 1,
                today: key === today,
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
        return { days, weeks, today };
    }

    /**
     * Status of a task, used to colour its bar:
     * done (100%), late (end passed, not done), active (started), planned.
     */
    getGanttStatus(record, start, end) {
        const progress = record.data.progress || 0;
        const today = this.gantt.today;
        if (progress >= 100) {
            return "done";
        }
        if (end < today) {
            return "late";
        }
        if (start <= today || progress > 0) {
            return "active";
        }
        return "planned";
    }

    getGanttCellClass(record, day) {
        const classes = ["o_gantt_cell"];
        if (day.weekend) {
            classes.push("o_gantt_weekend");
        }
        if (day.weekStart) {
            classes.push("o_gantt_week_start");
        }
        if (day.today) {
            classes.push("o_gantt_today");
        }
        const start = record.data.date_start && record.data.date_start.toISODate();
        const end = record.data.date_end && record.data.date_end.toISODate();
        if (start && end && start <= day.key && day.key <= end) {
            classes.push("o_gantt_bar", `o_gantt_status_${this.getGanttStatus(record, start, end)}`);
            if (day.key === start) {
                classes.push("o_gantt_bar_start");
            }
            if (day.key === end) {
                classes.push("o_gantt_bar_end");
            }
            // Completed part of the bar (from the start, by Progress %)
            const total = record.data.date_end.diff(record.data.date_start, "days").days + 1;
            const index = luxon.DateTime.fromISO(day.key).diff(record.data.date_start.startOf("day"), "days").days;
            const doneDays = Math.round((total * (record.data.progress || 0)) / 100);
            if (index < doneDays) {
                classes.push("o_gantt_bar_done");
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
