/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { formatMonetary } from "@web/views/fields/formatters";

// Categorical palette, fixed order (never cycled). Past 8 slices the rest
// fold into "Other" (neutral gray).
const PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
const OTHER_COLOR = "#8a8984";

/**
 * "Planned Expenses %": doughnut with the total in the centre and a legend
 * table (colour, cost type, amount, share bar, %). Hovering a legend row
 * highlights its slice and vice versa. Reads the live expense lines.
 */
export class ExpensePieChart extends Component {
    static template = "mefs_budget_planning.ExpensePieChart";
    static props = { ...standardFieldProps };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        this.state = useState({ active: -1 });
        onWillStart(() => loadBundle("web.chartjs_lib"));
        useEffect(
            () => this.renderChart(),
            () => [JSON.stringify(this.slices)]
        );
        onWillUnmount(() => this.chart?.destroy());
    }

    get slices() {
        const list = this.props.record.data.expense_line_ids;
        const rows = (list ? list.records : [])
            .map((rec) => {
                const ct = rec.data.cost_type_id;
                const label = ct ? ct.display_name ?? ct[1] ?? "" : "";
                return { label: label || "—", amount: rec.data.amount || 0 };
            })
            .filter((r) => r.amount > 0);
        let slices;
        if (rows.length <= PALETTE.length) {
            slices = rows.map((r, i) => ({ ...r, color: PALETTE[i] }));
        } else {
            const kept = rows.slice(0, PALETTE.length - 1).map((r, i) => ({ ...r, color: PALETTE[i] }));
            const other = rows.slice(PALETTE.length - 1).reduce((a, r) => a + r.amount, 0);
            slices = [...kept, { label: "Other", amount: other, color: OTHER_COLOR }];
        }
        const total = slices.reduce((a, s) => a + s.amount, 0);
        return slices.map((s) => ({ ...s, share: total ? s.amount / total : 0 }));
    }

    get total() {
        return this.slices.reduce((a, s) => a + s.amount, 0);
    }

    get totalMillions() {
        const m = this.total / 1e6;
        return m >= 100 ? m.toFixed(0) : m.toFixed(2);
    }

    formatAmount(value) {
        const currency = this.props.record.data.currency_id;
        const currencyId = currency ? currency.id ?? currency[0] : undefined;
        return formatMonetary(value, { currencyId });
    }

    formatShare(share) {
        const pct = share * 100;
        return `${pct < 1 && pct > 0 ? pct.toFixed(1) : Math.round(pct)}%`;
    }

    // ---- Legend <-> slice highlighting ----
    highlight(index) {
        this.state.active = index;
        if (!this.chart) {
            return;
        }
        const active = index >= 0 ? [{ datasetIndex: 0, index }] : [];
        this.chart.setActiveElements(active);
        this.chart.update();
    }

    renderChart() {
        const slices = this.slices;
        this.chart?.destroy();
        this.chart = null;
        if (!slices.length || !this.canvasRef.el) {
            return;
        }
        this.chart = new Chart(this.canvasRef.el, {
            type: "doughnut",
            data: {
                labels: slices.map((s) => s.label),
                datasets: [{
                    data: slices.map((s) => s.amount),
                    backgroundColor: slices.map((s) => s.color),
                    hoverBackgroundColor: slices.map((s) => s.color),
                    borderWidth: 0,
                    borderRadius: 6,
                    spacing: 3,
                    hoverOffset: 10,
                }],
            },
            options: {
                cutout: "70%",
                maintainAspectRatio: false,
                animation: { duration: 250 },
                layout: { padding: 12 },
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        callbacks: {
                            label: (ctx) =>
                                ` ${this.formatAmount(ctx.parsed)} · ${this.formatShare(slices[ctx.dataIndex].share)}`,
                        },
                    },
                },
                onHover: (_ev, elements) => {
                    const index = elements.length ? elements[0].index : -1;
                    if (index !== this.state.active) {
                        this.state.active = index;
                    }
                },
            },
        });
    }
}

registry.category("fields").add("mefs_expense_pie_chart", { component: ExpensePieChart });
