/** @odoo-module **/

import { Component, onWillStart, onWillUnmount, useEffect, useRef } from "@odoo/owl";
import { loadBundle } from "@web/core/assets";
import { registry } from "@web/core/registry";
import { standardFieldProps } from "@web/views/fields/standard_field_props";
import { formatMonetary } from "@web/views/fields/formatters";
import { formatDate } from "@web/core/l10n/dates";
import { niceAxis, formatTick } from "./income_bar_chart";

const { DateTime } = luxon;

const LINE_COLOR = "#2e6da4";
const TOTAL_COLOR = "rgba(29, 79, 124, 0.55)";
const DAY_MS = 86400000;
// Tick interval candidates in days; the first that gives <= MAX_TICKS wins.
const TICK_STEPS = [1, 2, 7, 14, 30, 60, 90, 180, 365];
const MAX_TICKS = 12;

function toDateTime(value) {
    if (!value) {
        return null;
    }
    if (value instanceof DateTime) {
        return value.startOf("day");
    }
    const dt = DateTime.fromISO(String(value));
    return dt.isValid ? dt.startOf("day") : null;
}

function roundedRect(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, r);
}

/** Vertical crosshair at the hovered point. */
const crosshair = {
    id: "mefsCrosshair",
    afterDatasetsDraw(chart) {
        const active = chart.tooltip?.getActiveElements?.() || [];
        if (!active.length) {
            return;
        }
        const { ctx, chartArea } = chart;
        const x = active[0].element.x;
        ctx.save();
        ctx.strokeStyle = "rgba(107, 114, 128, 0.45)";
        ctx.setLineDash([4, 4]);
        ctx.beginPath();
        ctx.moveTo(x, chartArea.top);
        ctx.lineTo(x, chartArea.bottom);
        ctx.stroke();
        ctx.restore();
    },
};

/** Dashed line at the final total, labelled at the right. */
const totalLine = {
    id: "mefsTotalLine",
    beforeDatasetsDraw(chart, _args, opts) {
        if (!(opts.value > 0)) {
            return;
        }
        const { ctx, chartArea, scales } = chart;
        const y = scales.y.getPixelForValue(opts.value);
        ctx.save();
        ctx.strokeStyle = TOTAL_COLOR;
        ctx.setLineDash([6, 5]);
        ctx.beginPath();
        ctx.moveTo(chartArea.left, y);
        ctx.lineTo(chartArea.right, y);
        ctx.stroke();
        ctx.setLineDash([]);
        ctx.font = "600 11px sans-serif";
        ctx.fillStyle = "#1d4f7c";
        ctx.textAlign = "left";
        ctx.textBaseline = "bottom";
        ctx.fillText(opts.label, chartArea.left + 6, y - 4);
        ctx.restore();
    },
};

/**
 * Running total (in millions) above each point, as a small pill. Drawn from
 * the last point backwards and skipped where it would overlap, so the final
 * total is always shown.
 */
const pointValues = {
    id: "mefsPointValues",
    afterDatasetsDraw(chart, _args, opts) {
        const { ctx, chartArea } = chart;
        const meta = chart.getDatasetMeta(0);
        const points = opts.points || [];
        ctx.save();
        ctx.font = "600 11px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        let leftEdge = Infinity;
        for (let i = meta.data.length - 1; i >= 0; i--) {
            const p = points[i];
            if (!p || !p.amount) {
                continue;
            }
            const pt = meta.data[i];
            const text = `${formatTick(p.y)}M`;
            const w = ctx.measureText(text).width + 12;
            const h = 18;
            let cx = Math.min(Math.max(pt.x, chartArea.left + w / 2), chartArea.right - w / 2);
            if (cx + w / 2 + 4 > leftEdge) {
                continue;
            }
            const cy = Math.max(pt.y - 16, chartArea.top + h / 2);
            ctx.fillStyle = "rgba(255, 255, 255, 0.95)";
            ctx.strokeStyle = "rgba(46, 109, 164, 0.35)";
            roundedRect(ctx, cx - w / 2, cy - h / 2, w, h, h / 2);
            ctx.fill();
            ctx.stroke();
            ctx.fillStyle = "#1d4f7c";
            ctx.fillText(text, cx, cy + 0.5);
            leftEdge = cx - w / 2;
        }
        ctx.restore();
    },
};

/**
 * Planned cumulative income over the project timeline: x = date, y =
 * cumulative income in millions. Reads the live Planned Income Summary lines
 * of the dashboard form; the date range follows the dated rows.
 */
export class IncomeCumulativeChart extends Component {
    static template = "mefs_budget_planning.IncomeCumulativeChart";
    static props = { ...standardFieldProps };

    setup() {
        this.canvasRef = useRef("canvas");
        this.chart = null;
        onWillStart(() => loadBundle("web.chartjs_lib"));
        useEffect(
            () => this.renderChart(),
            () => [JSON.stringify(this.series)]
        );
        onWillUnmount(() => this.chart?.destroy());
    }

    /** Points sorted by date, cumulated in date order. */
    get series() {
        const data = this.props.record.data;
        const lines = data.income_line_ids ? data.income_line_ids.records : [];
        const dated = lines
            .map((rec) => {
                const wt = rec.data.work_type_id;
                return {
                    date: toDateTime(rec.data.date),
                    amount: rec.data.amount || 0,
                    name: wt ? wt.display_name ?? wt[1] ?? "" : "",
                };
            })
            .filter((l) => l.date)
            .sort((a, b) => a.date - b.date);

        const start = toDateTime(data.project_start_date);
        if (!dated.length) {
            return { points: [], start: start?.toMillis(), end: start?.toMillis(), payments: 0 };
        }
        let running = 0;
        const points = dated.map((l) => {
            running += l.amount;
            return {
                x: l.date.toMillis(),
                y: running / 1e6,
                amount: running,
                step: l.amount,
                name: l.name,
            };
        });
        if (start && start.toMillis() < points[0].x) {
            points.unshift({ x: start.toMillis(), y: 0, amount: 0, step: 0, name: "Project start" });
        }
        // The date range follows the data: from the start (or first row) to
        // the last dated row, so a few rows spread over the full width.
        return {
            points,
            start: points[0].x,
            end: points[points.length - 1].x,
            payments: dated.length,
        };
    }

    // ---- Summary strip ----
    get total() {
        const pts = this.series.points;
        return pts.length ? pts[pts.length - 1].amount : 0;
    }

    get periodLabel() {
        const { points } = this.series;
        const firstPayment = points.find((p) => p.step > 0) || points[0];
        const last = points[points.length - 1];
        return `${this.fmtDate(firstPayment.x)} → ${this.fmtDate(last.x)}`;
    }

    get halfwayLabel() {
        const half = this.total / 2;
        const p = this.series.points.find((pt) => pt.amount >= half && pt.amount > 0);
        return p ? this.fmtDate(p.x) : "—";
    }

    fmtDate(ms) {
        return formatDate(DateTime.fromMillis(ms));
    }

    formatMillions(value) {
        return `${formatTick(value / 1e6)}M`;
    }

    formatAmount(value) {
        const currency = this.props.record.data.currency_id;
        const currencyId = currency ? currency.id ?? currency[0] : undefined;
        return formatMonetary(value, { currencyId });
    }

    /**
     * Calendar-aligned date ticks covering [start, end]: daily, weekly on
     * Mondays, or on the 1st of the month (every 1, 2, 3, 6 or 12 months).
     * The axis starts and ends on a tick.
     */
    dateTicks(start, end) {
        const days = Math.max(1, Math.round((end - start) / DAY_MS));
        const step = TICK_STEPS.find((s) => days / s <= MAX_TICKS) || TICK_STEPS.at(-1);
        const first = DateTime.fromMillis(start).startOf("day");
        const last = DateTime.fromMillis(end).startOf("day");
        let cursor;
        let advance;
        if (step < 7) {
            cursor = first;
            advance = (d) => d.plus({ days: step });
        } else if (step < 30) {
            cursor = first.startOf("week"); // ISO week: Monday
            advance = (d) => d.plus({ weeks: step / 7 });
        } else {
            const months = Math.max(1, Math.round(step / 30.4));
            cursor = first.startOf("month");
            cursor = cursor.set({ month: Math.floor((cursor.month - 1) / months) * months + 1 });
            advance = (d) => d.plus({ months });
        }
        const ticks = [cursor.toMillis()];
        // At least two ticks, so a single date still gets a usable axis
        while (cursor < last || ticks.length < 2) {
            cursor = advance(cursor);
            ticks.push(cursor.toMillis());
        }
        return ticks;
    }

    // ------------------------------------------------------------------
    // Download: the graph drawn like the "Budget Schedule" sheet (straight
    // line, green callouts, daily date ticks) saved as an A4 landscape PDF.
    // ------------------------------------------------------------------
    buildExportCanvas() {
        const points = this.series.points;
        const project = this.props.record.data.project_id;
        const projectName = project ? project.display_name ?? project[1] ?? "" : "";
        const W = 2400;
        const H = 1500;
        const canvas = document.createElement("canvas");
        canvas.width = W;
        canvas.height = H;
        canvas.style.width = `${W}px`;
        canvas.style.height = `${H}px`;
        // Chart.js needs the canvas in the DOM: render it off-screen
        const holder = document.createElement("div");
        holder.style.cssText = `position:fixed;left:-99999px;top:0;width:${W}px;height:${H}px;`;
        holder.appendChild(canvas);
        document.body.appendChild(holder);

        const LINE = "#4472c4";
        const gridColor = "#d9d9d9";
        const text = "#404040";
        const font = "Calibri, 'Segoe UI', Arial, sans-serif";
        const formatAmount = (v) => this.formatAmount(v);

        // Daily ticks, thinned so at most ~45 labels fit
        const first = DateTime.fromMillis(points[0].x).startOf("day");
        const last = DateTime.fromMillis(points[points.length - 1].x).startOf("day");
        const days = Math.max(1, Math.round((last - first) / DAY_MS));
        const every = Math.max(1, Math.ceil(days / 45));
        const xTicks = [];
        for (let d = first; d <= last.plus({ days: every - 1 }); d = d.plus({ days: every })) {
            xTicks.push(d.toMillis());
        }
        const yAxis = niceAxis(Math.max(...points.map((p) => p.amount)) * 1.08, 6);

        const whiteBackground = {
            id: "mefsExportBackground",
            beforeDraw(chart) {
                const { ctx } = chart;
                ctx.save();
                ctx.fillStyle = "#fff";
                ctx.fillRect(0, 0, chart.width, chart.height);
                ctx.restore();
            },
        };

        // Green callout per point ("Work item," / running total), alternating
        // above and below the line at two heights, with a leader line.
        const callouts = {
            id: "mefsExportCallouts",
            afterDatasetsDraw(chart) {
                const { ctx, chartArea } = chart;
                const meta = chart.getDatasetMeta(0);
                ctx.save();
                ctx.font = `21px ${font}`;
                ctx.textAlign = "center";
                ctx.textBaseline = "middle";
                let k = 0;
                meta.data.forEach((pt, i) => {
                    const p = points[i];
                    if (!p.step) {
                        return;
                    }
                    const lines = [`${p.name},`, formatAmount(p.amount)];
                    const w = Math.max(...lines.map((t) => ctx.measureText(t).width)) + 22;
                    const h = 56;
                    const above = k % 2 === 0;
                    const offset = 48 + (k % 4 < 2 ? 0 : 38);
                    k++;
                    const cx = Math.min(Math.max(pt.x, chartArea.left + w / 2 + 2), chartArea.right - w / 2 - 2);
                    let cy = above ? pt.y - offset - h / 2 : pt.y + offset + h / 2;
                    cy = Math.min(Math.max(cy, chartArea.top + h / 2 + 2), chartArea.bottom - h / 2 - 2);
                    ctx.strokeStyle = "#a6a6a6";
                    ctx.lineWidth = 1.5;
                    ctx.beginPath();
                    ctx.moveTo(pt.x, pt.y);
                    ctx.lineTo(cx, above ? cy + h / 2 : cy - h / 2);
                    ctx.stroke();
                    ctx.fillStyle = "#e2efda";
                    ctx.strokeStyle = "#a9d08e";
                    ctx.fillRect(cx - w / 2, cy - h / 2, w, h);
                    ctx.strokeRect(cx - w / 2, cy - h / 2, w, h);
                    ctx.fillStyle = text;
                    ctx.fillText(lines[0], cx, cy - 13);
                    ctx.fillText(lines[1], cx, cy + 13);
                });
                ctx.restore();
            },
        };

        const chart = new Chart(canvas, {
            type: "line",
            data: {
                datasets: [{
                    label: "Cumulative Income",
                    data: points.map((p) => ({ x: p.x, y: p.amount })),
                    borderColor: LINE,
                    backgroundColor: LINE,
                    borderWidth: 4,
                    tension: 0,
                    pointRadius: 0,
                    fill: false,
                }],
            },
            options: {
                responsive: false,
                animation: false,
                devicePixelRatio: 1,
                layout: { padding: { top: 20, right: 50, bottom: 20, left: 30 } },
                plugins: {
                    title: {
                        display: true,
                        text: "Planned Cumulative Income Throughout the Project Timeline",
                        color: "#262626",
                        font: { size: 34, weight: "bold", family: font },
                        padding: { top: 10, bottom: 6 },
                    },
                    subtitle: {
                        display: Boolean(projectName),
                        text: projectName,
                        color: "#595959",
                        font: { size: 24, family: font },
                        padding: { bottom: 10 },
                    },
                    legend: {
                        display: true,
                        position: "top",
                        align: "end",
                        labels: { color: text, font: { size: 21, family: font }, boxWidth: 44, boxHeight: 3 },
                    },
                    tooltip: { enabled: false },
                },
                scales: {
                    x: {
                        type: "linear",
                        min: xTicks[0],
                        max: xTicks.at(-1),
                        afterBuildTicks: (scale) => {
                            scale.ticks = xTicks.map((value) => ({ value }));
                        },
                        title: { display: true, text: "Project Timeline", color: text, font: { size: 24, family: font } },
                        ticks: {
                            color: text,
                            autoSkip: false,
                            minRotation: 90,
                            maxRotation: 90,
                            font: { size: 18, family: font },
                            callback: (v) => DateTime.fromMillis(v).toFormat("d-LLL"),
                        },
                        grid: { color: gridColor },
                        border: { color: "#bfbfbf" },
                    },
                    y: {
                        min: 0,
                        max: yAxis.max,
                        title: { display: true, text: "Cumulative Income", color: text, font: { size: 24, family: font } },
                        ticks: {
                            color: text,
                            stepSize: yAxis.step,
                            font: { size: 19, family: font },
                            callback: (v) => formatAmount(v),
                        },
                        grid: { color: gridColor },
                        border: { display: false },
                    },
                },
            },
            plugins: [whiteBackground, callouts],
        });
        const jpeg = canvas.toDataURL("image/jpeg", 0.95);
        chart.destroy();
        holder.remove();
        return { jpeg, width: W, height: H, projectName };
    }

    /**
     * Minimal one-page PDF (A4 landscape) holding a JPEG image, built by hand
     * so no PDF library is needed.
     */
    makePdf(jpegDataUrl, imgW, imgH) {
        const binary = atob(jpegDataUrl.split(",")[1]);
        const jpg = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; i++) {
            jpg[i] = binary.charCodeAt(i);
        }
        const pageW = 842;
        const pageH = 595;
        const margin = 24;
        const scale = Math.min((pageW - 2 * margin) / imgW, (pageH - 2 * margin) / imgH);
        const drawW = (imgW * scale).toFixed(2);
        const drawH = (imgH * scale).toFixed(2);
        const x = ((pageW - imgW * scale) / 2).toFixed(2);
        const y = ((pageH - imgH * scale) / 2).toFixed(2);
        const content = `q ${drawW} 0 0 ${drawH} ${x} ${y} cm /Im0 Do Q`;

        const enc = new TextEncoder();
        const parts = [];
        const offsets = [];
        let length = 0;
        const push = (chunk) => {
            const bytes = typeof chunk === "string" ? enc.encode(chunk) : chunk;
            parts.push(bytes);
            length += bytes.length;
        };
        const obj = (n, body) => {
            offsets[n] = length;
            push(`${n} 0 obj\n${body}\nendobj\n`);
        };
        push("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n");
        obj(1, "<< /Type /Catalog /Pages 2 0 R >>");
        obj(2, "<< /Type /Pages /Kids [3 0 R] /Count 1 >>");
        obj(3, `<< /Type /Page /Parent 2 0 R /MediaBox [0 0 ${pageW} ${pageH}] ` +
            "/Resources << /XObject << /Im0 4 0 R >> >> /Contents 5 0 R >>");
        offsets[4] = length;
        push(`4 0 obj\n<< /Type /XObject /Subtype /Image /Width ${imgW} /Height ${imgH} ` +
            `/ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length ${jpg.length} >>\nstream\n`);
        push(jpg);
        push("\nendstream\nendobj\n");
        obj(5, `<< /Length ${content.length} >>\nstream\n${content}\nendstream`);
        const xref = length;
        let table = "xref\n0 6\n0000000000 65535 f \n";
        for (let n = 1; n <= 5; n++) {
            table += `${String(offsets[n]).padStart(10, "0")} 00000 n \n`;
        }
        push(`${table}trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n${xref}\n%%EOF\n`);
        return new Blob(parts, { type: "application/pdf" });
    }

    onDownload() {
        if (!this.series.points.length) {
            return;
        }
        const { jpeg, width, height, projectName } = this.buildExportCanvas();
        const blob = this.makePdf(jpeg, width, height);
        const safe = (projectName || "Project").replace(/[\\/:*?"<>|]+/g, " ").trim();
        const link = document.createElement("a");
        link.href = URL.createObjectURL(blob);
        link.download = `Planned Cumulative Income - ${safe}.pdf`;
        document.body.appendChild(link);
        link.click();
        link.remove();
        setTimeout(() => URL.revokeObjectURL(link.href), 1000);
    }

    renderChart() {
        const { points, start, end } = this.series;
        this.chart?.destroy();
        this.chart = null;
        if (!points.length || !this.canvasRef.el) {
            return;
        }
        const ink = getComputedStyle(this.canvasRef.el).color;
        const muted = "#6b7280";
        const grid = "rgba(107, 114, 128, 0.14)";
        const xTicks = this.dateTicks(start, end);
        const total = this.total;
        // Headroom above the last point for its label, then rounded
        const yAxis = niceAxis(Math.max(...points.map((p) => p.y)) * 1.12, 7);

        const areaFill = (ctx) => {
            const area = ctx.chart.chartArea;
            if (!area) {
                return "rgba(46, 109, 164, 0.12)";
            }
            const g = ctx.chart.ctx.createLinearGradient(0, area.top, 0, area.bottom);
            g.addColorStop(0, "rgba(46, 109, 164, 0.28)");
            g.addColorStop(1, "rgba(46, 109, 164, 0.02)");
            return g;
        };

        this.chart = new Chart(this.canvasRef.el, {
            type: "line",
            data: {
                datasets: [{
                    data: points,
                    borderColor: LINE_COLOR,
                    backgroundColor: areaFill,
                    fill: "origin",
                    borderWidth: 2.5,
                    tension: 0, // straight segments with sharp corners, as in the sheet
                    borderJoinStyle: "miter",
                    pointRadius: (ctx) => (points[ctx.dataIndex]?.step ? 4.5 : 3),
                    pointHoverRadius: 7,
                    pointBackgroundColor: "#fff",
                    pointBorderColor: LINE_COLOR,
                    pointBorderWidth: 2,
                    pointHoverBackgroundColor: LINE_COLOR,
                    pointHoverBorderColor: "#fff",
                    pointHitRadius: 14,
                }],
            },
            options: {
                maintainAspectRatio: false,
                animation: { duration: 300 },
                layout: { padding: { top: 10, right: 12 } },
                interaction: { mode: "nearest", intersect: false, axis: "x" },
                plugins: {
                    legend: { display: false },
                    mefsTotalLine: {
                        value: total / 1e6,
                        label: `Total ${formatTick(total / 1e6)}M`,
                    },
                    mefsPointValues: { points },
                    tooltip: {
                        displayColors: false,
                        padding: 10,
                        callbacks: {
                            title: (items) => this.fmtDate(items[0].parsed.x),
                            label: (ctx) => {
                                const p = points[ctx.dataIndex];
                                const lines = [];
                                if (p.name) {
                                    lines.push(p.name);
                                }
                                if (p.step) {
                                    lines.push(`+ ${this.formatAmount(p.step)}`);
                                }
                                lines.push(`Cumulative: ${this.formatAmount(p.amount)}`);
                                return lines;
                            },
                        },
                    },
                },
                scales: {
                    x: {
                        type: "linear",
                        min: xTicks[0],
                        max: xTicks.at(-1),
                        title: {
                            display: true,
                            text: "Project Timeline",
                            color: muted,
                            font: { size: 11, weight: "600" },
                        },
                        afterBuildTicks: (scale) => {
                            scale.ticks = xTicks.map((value) => ({ value }));
                        },
                        ticks: {
                            color: muted,
                            autoSkip: false,
                            maxRotation: 0,
                            callback: (value) => DateTime.fromMillis(value).toFormat("d LLL"),
                        },
                        grid: { color: grid, drawTicks: false },
                        border: { display: false },
                    },
                    y: {
                        min: 0,
                        max: yAxis.max,
                        title: {
                            display: true,
                            text: "Cumulative Income (Millions)",
                            color: muted,
                            font: { size: 11, weight: "600" },
                        },
                        ticks: {
                            color: ink,
                            stepSize: yAxis.step,
                            padding: 6,
                            callback: (v) => formatTick(v),
                        },
                        grid: { color: grid, drawTicks: false },
                        border: { display: false },
                    },
                },
            },
            plugins: [totalLine, crosshair, pointValues],
        });
    }
}

registry.category("fields").add("mefs_income_cumulative_chart", {
    component: IncomeCumulativeChart,
});
