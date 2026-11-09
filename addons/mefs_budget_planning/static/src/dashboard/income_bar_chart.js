/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef, useState } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { formatMonetary } from "@web/views/fields/formatters";
import { formatDate } from "@web/core/l10n/dates";

const BAR_FROM = "#7fb0dc";
const BAR_TO = "#2e6da4";
const BAR_TOP = "#1d4f7c"; // largest bar
const TRACK = "rgba(46, 109, 164, 0.07)";
const ROW_HEIGHT = 46;
const LABEL_MAX = 28;

/**
 * Round axis: a step of 1, 2, 2.5 or 5 x 10^n giving about `target` ticks,
 * and a maximum rounded up to a whole number of steps.
 */
export function niceAxis(maxValue, target = 6) {
    if (!(maxValue > 0)) {
        return { max: 1, step: 0.2 };
    }
    const raw = maxValue / target;
    const magnitude = 10 ** Math.floor(Math.log10(raw));
    const step = [1, 2, 2.5, 5, 10].map((m) => m * magnitude).find((s) => s >= raw);
    return { max: Math.ceil(maxValue / step - 1e-9) * step, step };
}

/** Tick label: up to 2 decimals, no trailing zeros (2, 2.5, 0.25). */
export function formatTick(value) {
    return String(Math.round(value * 100) / 100);
}

function shorten(text) {
    return text.length > LABEL_MAX ? `${text.slice(0, LABEL_MAX - 1)}…` : text;
}

/** Light full-width track behind every bar. */
const barTracks = {
    id: "mefsBarTracks",
    beforeDatasetsDraw(chart) {
        const { ctx, chartArea } = chart;
        const meta = chart.getDatasetMeta(0);
        ctx.save();
        ctx.fillStyle = TRACK;
        meta.data.forEach((bar) => {
            const h = bar.height;
            const y = bar.y - h / 2;
            ctx.beginPath();
            ctx.roundRect(chartArea.left, y, chartArea.right - chartArea.left, h, h / 2);
            ctx.fill();
        });
        ctx.restore();
    },
};

/** Value (in millions) at the end of each bar; inside the bar if it would overflow. */
const barValues = {
    id: "mefsBarValues",
    afterDatasetsDraw(chart, _args, opts) {
        const { ctx, chartArea } = chart;
        const meta = chart.getDatasetMeta(0);
        const values = chart.data.datasets[0].data;
        ctx.save();
        ctx.font = "600 12px sans-serif";
        ctx.textBaseline = "middle";
        meta.data.forEach((bar, i) => {
            const text = `${formatTick(values[i])}M`;
            const width = ctx.measureText(text).width;
            const dim = opts.active >= 0 && opts.active !== i;
            if (bar.x + 8 + width <= chartArea.right) {
                ctx.textAlign = "left";
                ctx.fillStyle = dim ? "rgba(17, 24, 39, 0.35)" : opts.ink;
                ctx.fillText(text, bar.x + 8, bar.y);
            } else {
                ctx.textAlign = "right";
                ctx.fillStyle = "#fff";
                ctx.fillText(text, bar.x - 8, bar.y);
            }
        });
        ctx.restore();
    },
};

/**
 * Planned Income: one bar per row of the Planned Income Summary table,
 * amount in millions. Reads the dashboard's live one2many, so it follows
 * edits before they are saved.
 */
export class IncomeBarChart extends Component {
    static template = "mefs_budget_planning.IncomeBarChart";
    static props = { ...standardFieldProps };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        this.state = useState({ active: -1 });
        onWillStart(() => loadBundle("web.chartjs_lib"));
        useEffect(
            () => this.renderChart(),
            () => [JSON.stringify(this.rows)]
        );
        onWillUnmount(() => this.chart?.destroy());
    }

    get rows() {
        const list = this.props.record.data.income_line_ids;
        if (!list) {
            return [];
        }
        return list.records.map((rec) => {
            const wt = rec.data.work_type_id;
            const label = wt ? wt.display_name ?? wt[1] ?? "" : "";
            const date = rec.data.date;
            return {
                label: label || "—",
                amount: rec.data.amount || 0,
                date: date ? formatDate(date) : "",
            };
        });
    }

    get total() {
        return this.rows.reduce((a, r) => a + r.amount, 0);
    }

    get topIndex() {
        let top = -1;
        this.rows.forEach((r, i) => {
            if (r.amount > 0 && (top < 0 || r.amount > this.rows[top].amount)) {
                top = i;
            }
        });
        return top;
    }

    get chartHeight() {
        return Math.max(380, this.rows.length * ROW_HEIGHT + 70);
    }

    formatAmount(value) {
        const currency = this.props.record.data.currency_id;
        const currencyId = currency ? currency.id ?? currency[0] : undefined;
        return formatMonetary(value, { currencyId });
    }

    formatMillions(value) {
        return `${formatTick(value / 1e6)}M`;
    }

    setActive(index) {
        if (index === this.state.active) {
            return;
        }
        this.state.active = index;
        if (this.chart) {
            this.chart.options.plugins.mefsBarValues.active = index;
            this.chart.update("none");
        }
    }

    renderChart() {
        const rows = this.rows;
        this.chart?.destroy();
        this.chart = null;
        if (!rows.length || !this.canvasRef.el) {
            return;
        }
        const ink = getComputedStyle(this.canvasRef.el).color;
        const muted = "#6b7280";
        const grid = "rgba(107, 114, 128, 0.16)";
        const total = this.total;
        const top = this.topIndex;
        const axis = niceAxis(Math.max(...rows.map((r) => r.amount / 1e6)));

        const barColor = (ctx) => {
            const { chart, dataIndex } = ctx;
            const area = chart.chartArea;
            const active = this.state.active;
            if (active >= 0 && active !== dataIndex) {
                return "rgba(46, 109, 164, 0.22)";
            }
            if (!area) {
                return BAR_TO;
            }
            const end = dataIndex === top ? BAR_TOP : BAR_TO;
            const gradient = chart.ctx.createLinearGradient(area.left, 0, area.right, 0);
            gradient.addColorStop(0, BAR_FROM);
            gradient.addColorStop(1, end);
            return gradient;
        };

        this.chart = new Chart(this.canvasRef.el, {
            type: "bar",
            data: {
                labels: rows.map((r) => shorten(r.label)),
                datasets: [{
                    data: rows.map((r) => r.amount / 1e6),
                    backgroundColor: barColor,
                    hoverBackgroundColor: barColor,
                    borderRadius: 999,
                    borderSkipped: false,
                    barPercentage: 0.7,
                    categoryPercentage: 0.9,
                    maxBarThickness: 22,
                }],
            },
            options: {
                indexAxis: "y",
                maintainAspectRatio: false,
                animation: { duration: 300 },
                layout: { padding: { right: 8 } },
                interaction: { mode: "index", axis: "y", intersect: false },
                onHover: (_ev, elements) => {
                    this.setActive(elements.length ? elements[0].index : -1);
                },
                plugins: {
                    legend: { display: false },
                    mefsBarValues: { ink, active: -1 },
                    tooltip: {
                        displayColors: false,
                        padding: 10,
                        callbacks: {
                            title: (items) => rows[items[0].dataIndex].label,
                            label: (ctx) => {
                                const row = rows[ctx.dataIndex];
                                const share = total ? Math.round((row.amount / total) * 1000) / 10 : 0;
                                const lines = [
                                    this.formatAmount(row.amount),
                                    `${share}% of planned income`,
                                ];
                                if (row.date) {
                                    lines.push(`Planned for ${row.date}`);
                                }
                                return lines;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        min: 0,
                        max: axis.max,
                        title: {
                            display: true,
                            text: "Planned Income (Millions)",
                            color: muted,
                            font: { size: 11, weight: "600" },
                        },
                        ticks: {
                            color: muted,
                            stepSize: axis.step,
                            callback: (v) => formatTick(v),
                        },
                        grid: { color: grid, drawTicks: false },
                        border: { display: false, dash: [3, 4] },
                    },
                    y: {
                        title: {
                            display: true,
                            text: "Work Item",
                            color: muted,
                            font: { size: 11, weight: "600" },
                        },
                        ticks: { color: ink, autoSkip: false, padding: 8, font: { size: 13 } },
                        grid: { display: false },
                        border: { display: false },
                    },
                },
            },
            plugins: [barTracks, barValues],
        });
    }
}

export const incomeBarChart = {
    component: IncomeBarChart,
};

registry.category("fields").add("mefs_income_bar_chart", incomeBarChart);
