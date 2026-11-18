/** @odoo-module **/

import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";
import { PROJECTS, TODAY } from "./sample_data";

// Where a ledger reference lives, by document source
const SOURCE_MODELS = {
    "Purchase order": { model: "purchase.order", fields: ["name"] },
    "Site payroll": { model: "site.payroll", fields: ["name"] },
    "Expense request": { model: "payment.request", fields: ["name"] },
    default: { model: "account.move", fields: ["name", "ref"] },
};

const DAY = 86400000;
const toTime = (d) => Date.parse(d + "T00:00:00Z");
const daysBetween = (a, b) => Math.round((toTime(b) - toTime(a)) / DAY);
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
const numFmt = new Intl.NumberFormat("en-US", { maximumFractionDigits: 0 });

export const TABS = [
    { key: "overview", label: "Overview", icon: "fa-th-large" },
    { key: "income", label: "Income", icon: "fa-money" },
    { key: "cost", label: "Cost vs Budget", icon: "fa-balance-scale" },
    { key: "packages", label: "Work Packages", icon: "fa-cubes" },
    { key: "machinery", label: "Machinery & Fuel", icon: "fa-truck" },
    { key: "schedule", label: "Schedule", icon: "fa-calendar" },
    { key: "ledger", label: "Ledger", icon: "fa-book" },
];

const CLASS_COLORS = [
    "#2e6da4", "#b26a00", "#1f7a45", "#5b4bb7", "#c2410c", "#0e7490",
    "#7c8a2e", "#a3367a", "#4b5563", "#7fb0dc", "#d4a017", "#8a94a6",
];

export class MefsProjectDashboard extends Component {
    static template = "mefs_project_dashboard.Dashboard";
    static props = ["*"];

    setup() {
        this.action = useService("action");
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.projects = PROJECTS;
        this.tabs = TABS;
        this.state = useState({
            projectId: PROJECTS[0].id,
            tab: "overview",
            // Ledger filters
            ledgerCostType: "all",
            ledgerWorkType: "all",
            ledgerMonth: "all",
            // Schedule: which work types show their BOQ items
            scheduleOpen: {},
        });
    }

    // ------------------------------------------------------------------ format
    birr(v, digits = 2) {
        const a = Math.abs(v);
        if (a >= 1e6) {
            return `Birr ${(v / 1e6).toFixed(digits)}M`;
        }
        if (a >= 1e3) {
            return `Birr ${(v / 1e3).toFixed(0)}K`;
        }
        return `Birr ${numFmt.format(v)}`;
    }
    num(v) {
        return numFmt.format(v);
    }
    pct(v, digits = 1) {
        return `${(v || 0).toFixed(digits)}%`;
    }
    date(d) {
        if (!d) {
            return "—";
        }
        const [y, m, dd] = d.split("-");
        return `${parseInt(dd, 10)} ${MONTHS[parseInt(m, 10) - 1]} ${y}`;
    }

    // ------------------------------------------------------------------ project
    get project() {
        return PROJECTS.find((p) => p.id === this.state.projectId) || PROJECTS[0];
    }
    onProjectChange(ev) {
        this.state.projectId = parseInt(ev.target.value, 10);
        this.clearLedgerFilters();
        this.state.scheduleOpen = {};
    }
    setTab(key) {
        this.state.tab = key;
    }
    toggleWorkType(workType) {
        this.state.scheduleOpen[workType] = !this.state.scheduleOpen[workType];
    }

    // ------------------------------------------------------------------ cards
    get totals() {
        const cc = this.project.costClasses;
        const budget = cc.reduce((s, c) => s + c.budget, 0);
        const booked = cc.reduce((s, c) => s + c.booked, 0);
        const unbooked = cc.reduce((s, c) => s + c.unbooked, 0);
        return { budget, booked, unbooked, total: booked + unbooked };
    }

    /** Actual / forecast finish. Source still to be agreed: sample value for the delay card only. */
    get forecastFinish() {
        const a = this.project.actualFinish;
        return a && a > this.project.plannedFinish ? a : this.project.plannedFinish;
    }

    get cards() {
        const p = this.project;
        const t = this.totals;
        const income = p.contractIncome;
        const variance = t.total - t.budget;
        const margin = income ? ((income - t.total) / income) * 100 : 0;
        const marginBooked = income ? ((income - t.booked) / income) * 100 : 0;
        const marginBudget = income ? ((income - t.budget) / income) * 100 : 0;
        const delay = Math.max(0, daysBetween(p.plannedFinish, this.forecastFinish));
        return {
            income,
            total: t.total,
            budget: t.budget,
            variance,
            booked: t.booked,
            unbooked: t.unbooked,
            margin,
            marginBooked,
            marginBudget,
            delay,
            plannedFinish: p.plannedFinish,
            forecastFinish: this.forecastFinish,
        };
    }

    // ------------------------------------------------------------------ overview
    /** Margin (contract income − cost) under four progressively fuller views of cost. */
    get marginViews() {
        const p = this.project;
        const t = this.totals;
        const income = p.contractIncome;
        const rebar = this.rebarUnderRun;
        const views = [
            { key: "budget", label: "Budget", note: "Planned cost", cost: t.budget, cls: "is-budget" },
            { key: "booked", label: "Booked to date", note: "Posted in accounting", cost: t.booked, cls: "is-booked" },
            { key: "unbooked", label: "+ unbooked costs", note: `+ ${this.birr(t.unbooked)} on file`, cost: t.booked + t.unbooked, cls: "is-unbooked" },
            { key: "rebar", label: "+ rebar at budget", note: `+ ${this.birr(rebar)} under-run`, cost: t.booked + t.unbooked + rebar, cls: "is-rebar" },
        ];
        for (const v of views) {
            v.margin = income - v.cost;
            v.pct = income ? (v.margin / income) * 100 : 0;
        }
        const max = Math.max(...views.map((v) => Math.abs(v.margin)), 1);
        for (const v of views) {
            v.h = (Math.abs(v.margin) / max) * 100;
            v.neg = v.margin < 0;
        }
        return { income, views, rebar, rebarType: p.rebarCostType };
    }

    /** Reinforcement budget not yet consumed: treated as uncosted stock, added back at budget. */
    get rebarUnderRun() {
        const c = this.project.costClasses.find((x) => x.name === this.project.rebarCostType);
        return c ? Math.max(c.budget - c.booked - c.unbooked, 0) : 0;
    }

    /** Bills / documents on file that are not yet booked (unpaid). */
    get unbookedList() {
        const rows = this.project.ledger
            .filter((e) => !e.booked)
            .sort((a, b) => a.date.localeCompare(b.date))
            .map((e) => ({ ...e, daysOpen: Math.max(daysBetween(e.date, TODAY), 0) }));
        return { rows, total: rows.reduce((s, r) => s + r.amount, 0) };
    }

    /**
     * Progress, like the task-based workflow: each BOQ item is a task weighted by its value
     * (qty × unit price ÷ BOQ total) and earns executed qty ÷ BOQ qty of that weight.
     * Construction progress = earned value ÷ contract value. Other phases: done ÷ total tasks.
     */
    get progress() {
        const p = this.project;
        const items = p.scheduleItems || [];
        const contract = items.reduce((s, i) => s + (i.value || 0), 0);
        const executedValue = items.reduce((s, i) => s + ((i.value || 0) * (i.executed || 0)) / 100, 0);
        const construction = contract ? (executedValue / contract) * 100 : 0;
        const boqDone = items.filter((i) => (i.executed || 0) >= 100).length;
        const phases = (p.phases || []).map((ph) => {
            if (ph.boq) {
                return { ...ph, progress: construction, tasksDone: boqDone, tasksTotal: items.length, basis: "Weighted by BOQ value" };
            }
            const total = ph.tasksTotal || 0;
            return { ...ph, progress: total ? (ph.tasksDone / total) * 100 : 0, basis: "Tasks completed" };
        });
        const tasksTotal = phases.reduce((s, ph) => s + (ph.tasksTotal || 0), 0);
        const tasksDone = phases.reduce((s, ph) => s + (ph.tasksDone || 0), 0);
        const elapsed = Math.min(Math.max(daysBetween(p.plannedStart, TODAY) / Math.max(daysBetween(p.plannedStart, p.plannedFinish), 1), 0), 1) * 100;
        const current = phases.find((ph) => ph.current);
        return {
            construction,
            executedValue,
            contract,
            phases,
            currentPhase: current ? current.name : "",
            tasksTotal,
            tasksDone,
            tasksPending: tasksTotal - tasksDone,
            elapsed,
            ring: { r: 54, c: 2 * Math.PI * 54, offset: 2 * Math.PI * 54 * (1 - Math.min(construction, 100) / 100) },
        };
    }

    /** IPCs that count as earned income: approved or paid. */
    get earnedIpcs() {
        return (this.project.ipcs || []).filter((i) => i.state === "approved" || i.state === "paid");
    }

    /** Income: contract (BOQ), earned (approved + paid IPCs), collected (paid IPCs). */
    get income() {
        const ipcs = this.project.ipcs || [];
        const sum = (list) => list.reduce((s, i) => s + i.amount, 0);
        const earned = sum(this.earnedIpcs);
        const collected = sum(ipcs.filter((i) => i.state === "paid"));
        const submitted = sum(ipcs.filter((i) => i.state === "submitted"));
        const contract = this.project.contractIncome;
        return {
            contract,
            earned,
            collected,
            outstanding: earned - collected,
            submitted,
            earnedPct: contract ? (earned / contract) * 100 : 0,
            collectedPct: earned ? (collected / earned) * 100 : 0,
            rows: [...ipcs].sort((a, b) => b.date.localeCompare(a.date)),
        };
    }
    ipcStateLabel(s) {
        return { paid: "Paid", approved: "Approved", submitted: "Submitted", draft: "Draft", cancel: "Cancelled" }[s] || s;
    }
    ipcStateClass(s) {
        return { paid: "o_pd_badge_good", approved: "o_pd_badge_done", submitted: "o_pd_badge_warn" }[s] || "o_pd_badge_muted";
    }

    // ------------------------------------------------------------------ cost vs budget
    /** Cost types sorted from most over budget to most under budget. */
    get costRows() {
        return this.project.costClasses
            .map((c, i) => {
                const total = c.booked + c.unbooked;
                const variance = total - c.budget;
                return {
                    ...c, total, variance,
                    color: CLASS_COLORS[i % CLASS_COLORS.length],
                    varPct: c.budget ? (variance / c.budget) * 100 : null,
                    isRebar: c.name === this.project.rebarCostType,
                };
            })
            .sort((a, b) => b.variance - a.variance);
    }

    /** Diverging bars: over budget to the right (red), under budget to the left (green). */
    get varianceChart() {
        const rows = this.costRows;
        const maxOver = Math.max(0, ...rows.map((r) => r.variance));
        const maxUnder = Math.max(0, ...rows.map((r) => -r.variance));
        const span = maxOver + maxUnder || 1;
        const zero = (maxUnder / span) * 100;
        return {
            zero,
            rows: rows.map((r) => ({
                ...r,
                over: r.variance > 0,
                left: r.variance >= 0 ? zero : zero - (-r.variance / span) * 100,
                w: (Math.abs(r.variance) / span) * 100,
                label: (r.variance > 0 ? "+" : r.variance < 0 ? "−" : "") + this.birr(Math.abs(r.variance)),
            })),
        };
    }

    /**
     * Stacked monthly spend from the ledger: bill lines (paid and unpaid) by bill date,
     * stacked by cost type (budget-level product category). Overhead excluded.
     */
    get monthlySpend() {
        const isOverhead = (name) => /overhead/i.test(name || "");
        const lines = this.project.ledger.filter((e) => !isOverhead(e.costClass));
        // Series = cost types that have spend, in budget order, with the budget chart's colours
        const classes = this.project.costClasses;
        const series = classes
            .map((c, i) => ({ key: c.name, label: c.name, color: CLASS_COLORS[i % CLASS_COLORS.length] }))
            .filter((s) => lines.some((e) => e.costClass === s.key));
        // Every month from the first to the last bill date
        const keys = lines.map((e) => e.date.slice(0, 7)).sort();
        const monthKeys = [];
        if (keys.length) {
            let [y, m] = keys[0].split("-").map(Number);
            const [ly, lm] = keys.at(-1).split("-").map(Number);
            while (y < ly || (y === ly && m <= lm)) {
                monthKeys.push(`${y}-${String(m).padStart(2, "0")}`);
                m += 1;
                if (m > 12) {
                    m = 1;
                    y += 1;
                }
            }
        }
        const months = monthKeys.map((k) => {
            const inMonth = lines.filter((e) => e.date.startsWith(k));
            const total = inMonth.reduce((s, e) => s + e.amount, 0);
            const [y, mo] = k.split("-");
            return {
                key: k,
                label: `${MONTHS[parseInt(mo, 10) - 1]} ${y.slice(2)}`,
                total,
                segs: series
                    .map((s) => ({ ...s, value: inMonth.filter((e) => e.costClass === s.key).reduce((a, e) => a + e.amount, 0) }))
                    .filter((s) => s.value)
                    .map((s) => ({ ...s, share: total ? (s.value / total) * 100 : 0 })),
            };
        });
        const top = Math.max(...months.map((m) => m.total), 1);
        const step = [250e3, 500e3, 1e6, 2e6, 2.5e6, 5e6, 10e6, 20e6].find((s) => top / s <= 5) || 50e6;
        const max = Math.ceil(top / step) * step;
        for (const m of months) {
            m.h = (m.total / max) * 100;
        }
        const ticks = [];
        for (let v = 0; v <= max + 1; v += step) {
            ticks.push({ v, bottom: (v / max) * 100, label: v ? this.birr(v) : "Birr 0K" });
        }
        const pf = this.project.plannedFinish;
        const [py, pm] = pf.split("-");
        const finishLabel = `${MONTHS[parseInt(pm, 10) - 1]} ${py}`;
        const note = pf < TODAY ? `Budgeted work was to finish in ${finishLabel}.` : `Budgeted work is to finish in ${finishLabel}.`;
        return { months, ticks, series, note };
    }

    signedPct(v) {
        if (v === null || v === undefined) {
            return "—";
        }
        const r = Math.round(v);
        return (r > 0 ? "+" : r < 0 ? "−" : "") + Math.abs(r) + "%";
    }
    signedNum(v) {
        return (v > 0 ? "+" : v < 0 ? "−" : "") + numFmt.format(Math.abs(v));
    }

    // ------------------------------------------------------------------ packages
    /**
     * Cost per work package (BOQ work type), like the ledger: bill lines grouped by the
     * work item chosen on the store request. Booked = paid, unbooked = unpaid.
     * Lines with no work item form the "Not allocated" row, so the tab adds up to project cost.
     */
    get packageRows() {
        // Every BOQ work type (zero when no cost yet), filled from the ledger's bill lines
        // grouped by work item; lines without a work item go to "Not allocated" (last).
        const groups = new Map();
        for (const p of this.project.packages) {
            groups.set(p.name, { code: p.code, name: p.name, booked: 0, unbooked: 0, unallocated: false });
        }
        for (const e of this.project.ledger) {
            const key = e.workType || null;
            if (!groups.has(key)) {
                groups.set(key, { code: key || "NA", name: key || "Not allocated", booked: 0, unbooked: 0, unallocated: !key });
            }
            groups.get(key)[e.booked ? "booked" : "unbooked"] += e.amount;
        }
        // Executed % per work type: executed value ÷ contract value of its BOQ items
        const exec = {};
        for (const it of this.project.scheduleItems || []) {
            exec[it.workType] ||= { value: 0, done: 0 };
            exec[it.workType].value += it.value || 0;
            exec[it.workType].done += ((it.value || 0) * (it.executed || 0)) / 100;
        }
        for (const g of groups.values()) {
            const e = exec[g.name];
            g.executedPct = !g.unallocated && e && e.value ? (e.done / e.value) * 100 : null;
        }
        const pk = [...groups.values()].sort((a, b) => Number(a.unallocated) - Number(b.unallocated));
        const max = Math.max(1, ...pk.map((p) => p.booked + p.unbooked));
        const grand = pk.reduce((s, p) => s + p.booked + p.unbooked, 0) || 1;
        return pk.map((p) => {
            const total = p.booked + p.unbooked;
            // Income not available yet (to be connected later): null → shown as "—"
            const income = null;
            return {
                ...p,
                income,
                total,
                margin: income ? ((income - p.booked) / income) * 100 : null,
                marginAll: income ? ((income - total) / income) * 100 : null,
                share: (total / grand) * 100,
                bars: [
                    { key: "income", cls: "is-income", value: income, w: income ? (income / max) * 100 : 0 },
                    { key: "booked", cls: "is-booked", value: p.booked, w: (p.booked / max) * 100 },
                    { key: "total", cls: "is-total", value: total, w: (total / max) * 100 },
                ],
            };
        });
    }
    get packageTotals() {
        const rows = this.packageRows;
        const booked = rows.reduce((s, r) => s + r.booked, 0);
        const unbooked = rows.reduce((s, r) => s + r.unbooked, 0);
        return { income: null, booked, unbooked, total: booked + unbooked, margin: null, marginAll: null };
    }
    marginPct(v) {
        if (v === null || v === undefined) {
            return "—";
        }
        return (v < 0 ? "−" : "") + Math.abs(v).toFixed(1) + "%";
    }
    /** Money or "—" when the value is not available yet. */
    numOrDash(v) {
        return v === null || v === undefined ? "—" : this.num(v);
    }
    birrOrDash(v) {
        return v === null || v === undefined ? "—" : this.birr(v);
    }

    // ------------------------------------------------------------------ machinery
    /** Machine use and fuel, from the machinery timesheet log (sorted by hours). */
    get machineRows() {
        return this.project.machines
            .map((m) => ({
                ...m,
                lph: m.hours ? m.fuel / m.hours : 0,
                util: m.daysLogged ? (m.daysWorked / m.daysLogged) * 100 : 0,
                avgDay: m.daysWorked ? m.hours / m.daysWorked : 0,
            }))
            .sort((a, b) => b.hours - a.hours);
    }
    /** Fuel burned per working hour, highest first. */
    get fuelRateChart() {
        const rows = [...this.machineRows].sort((a, b) => b.lph - a.lph);
        const max = Math.max(1, ...rows.map((r) => r.lph));
        return rows.map((r) => ({ id: r.id, name: r.name, label: `${r.lph.toFixed(1)} L/h`, w: (r.lph / max) * 100 }));
    }
    /** Share of days on site that logged hours, lowest first; under 60% flagged. */
    get utilisationChart() {
        return [...this.machineRows]
            .sort((a, b) => a.util - b.util)
            .map((r) => ({ id: r.id, name: r.name, label: `${r.util.toFixed(0)}%`, w: r.util, low: r.util < 60 }));
    }

    // ------------------------------------------------------------------ schedule
    /**
     * One milestone per work type: planned completion = end date of the last
     * BOQ item of that work type in the budget plan schedule.
     */
    get milestoneRows() {
        const groups = new Map();
        for (const it of this.project.scheduleItems || []) {
            if (!groups.has(it.workType)) {
                groups.set(it.workType, []);
            }
            groups.get(it.workType).push(it);
        }
        return [...groups.entries()]
            .map(([workType, items]) => {
                const dated = items.filter((i) => i.end);
                const last = dated.reduce((a, b) => (!a || b.end > a.end ? b : a), null);
                const first = items.reduce((a, b) => (!a || (b.start && b.start < a.start) ? b : a), null);
                return {
                    id: workType,
                    name: `${workType} complete`,
                    workType,
                    items: [...items]
                        .sort((a, b) => (a.start || "").localeCompare(b.start || ""))
                        .map((i) => ({ ...i, isLast: last ? i.item === last.item : false })),
                    planned: last ? last.end : null,
                    start: first ? first.start : null,
                    lastItem: last,
                    itemCount: items.length,
                    undated: items.length - dated.length,
                };
            })
            .sort((a, b) => (a.planned || "9999").localeCompare(b.planned || "9999"));
    }

    /** Planned dots only, on a weekly date axis. */
    get milestoneChart() {
        const rows = this.milestoneRows.filter((r) => r.planned);
        if (!rows.length) {
            return { rows: [], weeks: [], showToday: false };
        }
        const dates = rows.map((r) => r.planned).sort();
        const [fy, fm] = dates[0].split("-").map(Number);
        const [ly, lm] = dates.at(-1).split("-").map(Number);
        const rs = Date.UTC(fy, fm - 1, 1);
        const re = Date.UTC(ly, lm, 1); // first day of the month after the last date
        const pos = (d) => ((toTime(d) - rs) / (re - rs)) * 100;
        const weeks = [];
        let lastMonth = -1;
        for (let t = rs; t < re; t += 7 * DAY) {
            const dt = new Date(t);
            const mo = dt.getUTCMonth();
            weeks.push({
                key: t,
                left: ((t - rs) / (re - rs)) * 100,
                label: mo !== lastMonth ? MONTHS[mo] + (mo === 0 || lastMonth === -1 ? ` ${String(dt.getUTCFullYear()).slice(2)}` : "") : "",
            });
            lastMonth = mo;
        }
        return {
            weeks,
            showToday: toTime(TODAY) >= rs && toTime(TODAY) < re,
            today: pos(TODAY),
            rows: rows.map((r) => ({ ...r, plannedLeft: pos(r.planned), label: this.date(r.planned) })),
        };
    }

    // ------------------------------------------------------------------ ledger
    // Paid = booked bill, unpaid = bill on file not yet booked. "none" = not allocated to a work type.
    get ledgerFilterOptions() {
        const ledger = this.project.ledger;
        const costTypes = this.project.costClasses.map((c) => c.name).filter((n) => ledger.some((e) => e.costClass === n));
        const workTypes = this.project.packages.map((p) => p.name).filter((n) => ledger.some((e) => e.workType === n));
        const hasUnallocated = ledger.some((e) => !e.workType);
        const months = [...new Set(ledger.map((e) => e.date.slice(0, 7)))]
            .sort()
            .reverse()
            .map((m) => {
                const [y, mo] = m.split("-");
                return { key: m, label: `${MONTHS[parseInt(mo, 10) - 1]} ${y}` };
            });
        return { costTypes, workTypes, hasUnallocated, months };
    }
    get ledgerRows() {
        const { ledgerCostType, ledgerWorkType, ledgerMonth } = this.state;
        return this.project.ledger
            .filter(
                (e) =>
                    (ledgerCostType === "all" || e.costClass === ledgerCostType) &&
                    (ledgerWorkType === "all" || (ledgerWorkType === "none" ? !e.workType : e.workType === ledgerWorkType)) &&
                    (ledgerMonth === "all" || e.date.startsWith(ledgerMonth))
            )
            .sort((a, b) => b.date.localeCompare(a.date));
    }
    get ledgerTotals() {
        const rows = this.ledgerRows;
        const paid = rows.filter((r) => r.booked);
        const unpaid = rows.filter((r) => !r.booked);
        const sum = (list) => list.reduce((s, r) => s + r.amount, 0);
        return {
            paid: sum(paid),
            unpaid: sum(unpaid),
            total: sum(rows),
            count: rows.length,
            paidCount: paid.length,
            unpaidCount: unpaid.length,
        };
    }
    get ledgerFiltered() {
        const s = this.state;
        return s.ledgerCostType !== "all" || s.ledgerWorkType !== "all" || s.ledgerMonth !== "all";
    }
    onLedgerCostType(ev) {
        this.state.ledgerCostType = ev.target.value;
    }
    onLedgerWorkType(ev) {
        this.state.ledgerWorkType = ev.target.value;
    }
    onLedgerMonth(ev) {
        this.state.ledgerMonth = ev.target.value;
    }
    clearLedgerFilters() {
        this.state.ledgerCostType = "all";
        this.state.ledgerWorkType = "all";
        this.state.ledgerMonth = "all";
    }

    /**
     * Open the document behind a ledger reference (vendor bill in Accounting, or the PO).
     * Rows with a real `moveId` open directly; sample rows are looked up by reference.
     */
    async openBill(e) {
        const target = SOURCE_MODELS[e.source] || SOURCE_MODELS.default;
        let resId = e.moveId || false;
        if (!resId) {
            try {
                for (const field of target.fields) {
                    const ids = await this.orm.search(target.model, [[field, "=", e.ref]], { limit: 1 });
                    if (ids.length) {
                        resId = ids[0];
                        break;
                    }
                }
            } catch {
                // model not installed here (e.g. site payroll / expense requests)
                resId = false;
            }
        }
        if (!resId) {
            this.notification.add(_t("%s was not found in Odoo (sample data).", e.ref), { type: "warning" });
            return;
        }
        await this.action.doAction({
            type: "ir.actions.act_window",
            res_model: target.model,
            res_id: resId,
            views: [[false, "form"]],
            target: "current",
        });
    }
}

registry.category("actions").add("mefs_project_dashboard", MefsProjectDashboard);
