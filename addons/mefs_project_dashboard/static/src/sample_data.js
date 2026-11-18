/** @odoo-module **/

// ---------------------------------------------------------------------------
// SAMPLE DATA — UI only. Each key mirrors what the backend will provide later:
//   contractIncome   ← approved BOQ total before VAT
//   costClasses      ← budget plan cost classes (budget) / analytic lines (booked)
//                      / open POs, draft bills, SIVs (unbooked)
//   ipcs             ← interim payment certificates (earned = approved + paid, collected = paid)
//   phases           ← project stages with their tasks (progress + task counts)
//   packages         ← BOQ lines grouped by work type
//   machines, fuel   ← equipment timesheet lines
//   scheduleItems    ← budget plan schedule lines (one per BOQ item, with its work type)
//   ledger           ← analytic lines (booked) + open documents (unbooked)
// ---------------------------------------------------------------------------

export const TODAY = "2026-11-18";

export const PROJECTS = [
    {
        id: 1,
        name: "Bole Lemi Deep Foundation Works",
        client: "Ethiopian Investment Holdings",
        budgetPlan: "BUD/2026/0001",
        boq: "BOQ/0007 REV1",
        contractIncome: 54267898,
        plannedStart: "2026-01-14",
        plannedFinish: "2026-04-30",
        // Cost types: budget (budget plan) / booked (accounting) / unbooked (documents on file)
        costClasses: [
            { name: "Machinery and Equipment Rental", budget: 3473733, booked: 5405959, unbooked: 5684000 },
            { name: "Fuel & Lubricants", budget: 2244464, booked: 4480328, unbooked: 286592 },
            { name: "Transport & Logistics", budget: 300000, booked: 961894, unbooked: 750000 },
            { name: "Maintenance and Tools", budget: 340981, booked: 1449462, unbooked: 0 },
            { name: "Concrete", budget: 7098983, booked: 8188804, unbooked: 0 },
            { name: "Overhead Cost", budget: 1876909, booked: 2262541, unbooked: 0 },
            { name: "Cement & Aggregates", budget: 690923, booked: 991760, unbooked: 0 },
            { name: "Site Operations & Admin", budget: 0, booked: 203616, unbooked: 0 },
            { name: "Other Material Purchases", budget: 0, booked: 113138, unbooked: 0 },
            { name: "Labor & Subcontract", budget: 857175, booked: 905017, unbooked: 0 },
            { name: "Anchor and Stressing", budget: 2969715, booked: 636314, unbooked: 1153350 },
            { name: "Reinforcement", budget: 10607971, booked: 3305686, unbooked: 0 },
        ],
        // The rebar under-run is treated as uncosted stock: added back at budget
        rebarCostType: "Reinforcement",
        // Work packages: cost per BOQ work type from bill lines (work item on the store request): booked = paid, unbooked = unpaid.
        // Overhead is not allocated. executed / certified feed the Overview progress figures.
        packages: [
            { code: "MOB", name: "Mob & demob", income: 450000, booked: 465135, unbooked: 750000, executed: 100, certified: 450000 },
            { code: "PILE", name: "Piling", income: 22029797, booked: 11279784, unbooked: 0, executed: 90, certified: 16900000 },
            { code: "CAP", name: "Capping beam", income: 1720098, booked: 985970, unbooked: 0, executed: 70, certified: 900000 },
            { code: "ANCHOR", name: "Anchoring", income: 7458000, booked: 1554756, unbooked: 1153350, executed: 45, certified: 2600000 },
            { code: "SHOT", name: "Shotcrete", income: 7293425, booked: 3304538, unbooked: 0, executed: 60, certified: 3500000 },
            { code: "EXC", name: "Excavation & cartaway", income: 15316578, booked: 9338387, unbooked: 5684000, executed: 85, certified: 10450000 },
        ],
        packagesNote: "Excavation & cartaway carries most of the unbooked cost: the unpaid cartaway trips. The diesel purchase order has no work item, so it sits under Not allocated.",
        // Equipment timesheets (approved): hours = total hours, fuel = total fuel consumed,
        // daysWorked = days with working hours, daysLogged = days with working or idle hours,
        // fuelBirr = source not decided yet
        machines: [
            { id: 1, name: "Doosan DX 340 2012", hours: 272.5, fuel: 4890, fuelBirr: 983442, daysWorked: 34, daysLogged: 38, from: "2026-05-15", to: "2026-06-22" },
            { id: 2, name: "Chain Excavator Rental", hours: 257.6, fuel: 5730, fuelBirr: 1150228, daysWorked: 29, daysLogged: 34, from: "2026-04-24", to: "2026-06-16" },
            { id: 3, name: "BG26", hours: 231.6, fuel: 3750, fuelBirr: 699781, daysWorked: 28, daysLogged: 30, from: "2026-03-16", to: "2026-04-17" },
            { id: 4, name: "Wheel Excavator Rental", hours: 176.9, fuel: 2550, fuelBirr: 529992, daysWorked: 20, daysLogged: 23, from: "2026-03-30", to: "2026-04-21" },
            { id: 5, name: "Hyundai HX340SL", hours: 139.8, fuel: 2630, fuelBirr: 508410, daysWorked: 20, daysLogged: 31, from: "2026-05-22", to: "2026-06-24" },
            { id: 6, name: "Klemm", hours: 104.3, fuel: 640, fuelBirr: 133108, daysWorked: 13, daysLogged: 28, from: "2026-05-05", to: "2026-06-01" },
            { id: 7, name: "Compressor", hours: 84.2, fuel: 2303, fuelBirr: 475367, daysWorked: 15, daysLogged: 28, from: "2026-05-05", to: "2026-06-01" },
        ],
        machinesNote: "The Klemm anchor rig and compressor logged hours on about half their days; with no breakdown hours recorded, idle and broken-down time can't be told apart.",
        // Budget plan schedule: one line per BOQ item, each with its work type.
        // A work type's planned completion = end date of its last BOQ item.
        scheduleItems: [
            { item: "1.01", name: "Mobilization of plant & site set-up", workType: "Mob & demob", start: "2026-01-05", end: "2026-01-14", value: 300000, executed: 100 },
            { item: "1.02", name: "Demobilization & site clearance", workType: "Mob & demob", start: "2026-04-25", end: "2026-04-30", value: 150000, executed: 100 },
            { item: "2.01", name: "Pile drilling Ø800 — row A", workType: "Piling", start: "2026-01-15", end: "2026-01-22", value: 5200000, executed: 100 },
            { item: "2.02", name: "Pile drilling Ø800 — row B", workType: "Piling", start: "2026-01-18", end: "2026-01-26", value: 5200000, executed: 100 },
            { item: "2.03", name: "Pile drilling Ø800 — row C", workType: "Piling", start: "2026-01-22", end: "2026-01-29", value: 5200000, executed: 100 },
            { item: "2.04", name: "Pile reinforcement & concreting", workType: "Piling", start: "2026-01-16", end: "2026-01-31", value: 6429797, executed: 100 },
            { item: "3.01", name: "Pile head trimming", workType: "Capping beam", start: "2026-01-28", end: "2026-02-01", value: 320098, executed: 100 },
            { item: "3.02", name: "Capping beam rebar & concrete", workType: "Capping beam", start: "2026-01-30", end: "2026-02-04", value: 1400000, executed: 100 },
            { item: "4.01", name: "Anchor drilling — row 1", workType: "Anchoring", start: "2026-02-05", end: "2026-02-15", value: 2900000, executed: 100 },
            { item: "4.02", name: "Anchor drilling — row 2", workType: "Anchoring", start: "2026-02-12", end: "2026-02-22", value: 2900000, executed: 100 },
            { item: "4.03", name: "Anchor stressing & lock-off", workType: "Anchoring", start: "2026-02-18", end: "2026-02-28", value: 1658000, executed: 100 },
            { item: "5.01", name: "Shotcrete facing — stage 1", workType: "Shotcrete", start: "2026-02-10", end: "2026-02-25", value: 3600000, executed: 100 },
            { item: "5.02", name: "Shotcrete facing — stage 2", workType: "Shotcrete", start: "2026-03-01", end: "2026-03-25", value: 3693425, executed: 100 },
            { item: "6.01", name: "Bulk excavation & cartaway — stage 1", workType: "Excavation & cartaway", start: "2026-02-01", end: "2026-03-10", value: 6500000, executed: 100 },
            { item: "6.02", name: "Bulk excavation & cartaway — stage 2", workType: "Excavation & cartaway", start: "2026-03-05", end: "2026-04-05", value: 6500000, executed: 100 },
            { item: "6.03", name: "Elevator pit excavation", workType: "Excavation & cartaway", start: "2026-04-01", end: "2026-04-20", value: 2316578, executed: 100 },
        ],
        // Actual completion source is still to be agreed; used only by the Completion Delay card for now.
        actualFinish: "2026-08-10",
        // Project phases (project stages). Construction tasks are the BOQ items above (one task per
        // item, weighted by value, done when executed qty = BOQ qty); other phases have manual tasks.
        phases: [
            { name: "Design", tasksDone: 3, tasksTotal: 3 },
            { name: "Tendering", tasksDone: 2, tasksTotal: 2 },
            { name: "Permits and Approvals", tasksDone: 2, tasksTotal: 2 },
            { name: "Construction", boq: true },
            { name: "Closeout", tasksDone: 3, tasksTotal: 5, current: true },
        ],
        // Interim payment certificates (mefs.boq.payment): amount = net before VAT, boq = BOQ (and revision) it certifies.
        // Earned = approved + paid; collected = paid.
        ipcs: [
            { id: 1, name: "IPC-01", boq: "BOQ/0007 REV0", date: "2026-01-31", state: "paid", amount: 1500000 },
            { id: 2, name: "IPC-02", boq: "BOQ/0007 REV0", date: "2026-02-28", state: "paid", amount: 2500000 },
            { id: 3, name: "IPC-03", boq: "BOQ/0007 REV0", date: "2026-03-31", state: "paid", amount: 5000000 },
            { id: 4, name: "IPC-04", boq: "BOQ/0007 REV1", date: "2026-04-30", state: "paid", amount: 8000000 },
            { id: 5, name: "IPC-05", boq: "BOQ/0007 REV1", date: "2026-05-31", state: "paid", amount: 9000000 },
            { id: 6, name: "IPC-06", boq: "BOQ/0007 REV1", date: "2026-06-30", state: "paid", amount: 5000000 },
            { id: 7, name: "IPC-07", boq: "BOQ/0007 REV1", date: "2026-07-31", state: "approved", amount: 2500000 },
            { id: 8, name: "IPC-08", boq: "BOQ/0007 REV1", date: "2026-08-31", state: "submitted", amount: 1300000 },
        ],
        // One row per bill line (amount incl. VAT). booked = paid, unbooked = unpaid.
        //   productCategory ← product category of the line's product (as is)
        //   costClass       ← budget cost type it counts under (budgeted category it rolls up to)
        //   workType    ← Description of Work on the originating store request (BOQ work type); null = not allocated
        //   description ← description text of the store request line
        ledger: [
            // Site payroll (daily workers): confirmed / paid payrolls, cost type Labor
            { id: 201, date: "2026-03-31", ref: "SPR/2026/0012", source: "Site payroll", partner: "Daily workers — 38", costClass: "Labor & Subcontract", productCategory: "Labor & Subcontract / Daily Workers", workType: null, description: "Site payroll — March, 612 man-days", amount: 214600, booked: true },
            { id: 202, date: "2026-04-30", ref: "SPR/2026/0015", source: "Site payroll", partner: "Daily workers — 35", costClass: "Labor & Subcontract", productCategory: "Labor & Subcontract / Daily Workers", workType: null, description: "Site payroll — April, 566 man-days", amount: 198300, booked: true },
            { id: 203, date: "2026-05-31", ref: "SPR/2026/0019", source: "Site payroll", partner: "Daily workers — 31", costClass: "Labor & Subcontract", productCategory: "Labor & Subcontract / Daily Workers", workType: null, description: "Site payroll — May, 505 man-days", amount: 176900, booked: true },
            // Expense requests (petty cash / payment requests): cost type from the line's product category
            { id: 301, date: "2026-03-18", ref: "EXP/2026/0041", source: "Expense request", partner: "Site petty cash", costClass: "Maintenance and Tools", productCategory: "Maintenance and Tools / Hand Tools", workType: null, description: "Workshop hand tools & grinding discs", amount: 46800, booked: true },
            { id: 302, date: "2026-04-22", ref: "EXP/2026/0057", source: "Expense request", partner: "Site petty cash", costClass: "Transport & Logistics", productCategory: "Transport & Logistics / Local Transport", workType: null, description: "Local transport & fuel advances for drivers", amount: 28500, booked: true },
            { id: 303, date: "2026-05-09", ref: "EXP/2026/0063", source: "Expense request", partner: "Bole local supplier", costClass: "Cement & Aggregates", productCategory: "Cement & Aggregates / Sand", workType: null, description: "River sand — 3 m³, urgent", amount: 18750, booked: true },
            { id: 1, date: "2026-01-20", ref: "DRAFT/BILL/0093", source: "Draft bill", partner: "Abay Logistics", costClass: "Transport & Logistics", productCategory: "Transport & Logistics / Mobilisation", workType: "Mob & demob", description: "Rig mobilisation & heavy haulage", amount: 750000, booked: false },
            { id: 2, date: "2026-02-20", ref: "BILL/2026/0384", source: "Vendor bill", partner: "Kality Steel", costClass: "Reinforcement", productCategory: "Reinforcement / Rebar", workType: "Piling", description: "Rebar Ø20 — 38 t", amount: 2774000, booked: true },
            { id: 3, date: "2026-02-28", ref: "BILL/2026/0377", source: "Vendor bill", partner: "Nyala Insurance", costClass: "Overhead Cost", productCategory: "Overhead Cost / Insurance", workType: null, description: "CAR insurance — Q1", amount: 418000, booked: true },
            { id: 4, date: "2026-03-14", ref: "PAY/2026/0118", source: "Payroll", partner: "Site payroll", costClass: "Labor & Subcontract", productCategory: "Labor & Subcontract / Site Labour", workType: "Piling", description: "Fortnight 2 — piling crew", amount: 186500, booked: true },
            { id: 5, date: "2026-03-26", ref: "JE/2026/0102", source: "Journal entry", partner: "Internal", costClass: "Site Operations & Admin", productCategory: "Site Operations & Admin", workType: null, description: "Site office & utilities allocation", amount: 203616, booked: true },
            { id: 6, date: "2026-03-31", ref: "BILL/2026/0398", source: "Vendor bill", partner: "Ethio Plant Hire", costClass: "Machinery and Equipment Rental", productCategory: "Machinery and Equipment Rental / Piling Rigs", workType: "Piling", description: "BG26 piling rig rental — March", amount: 1240000, booked: true },
            { id: 7, date: "2026-04-10", ref: "BILL/2026/0401", source: "Vendor bill", partner: "Habesha Ready-Mix", costClass: "Concrete", productCategory: "Concrete / Ready-mix", workType: "Piling", description: "C30 concrete — 410 m³", amount: 2214000, booked: true },
            { id: 8, date: "2026-04-16", ref: "BILL/2026/0412", source: "Vendor bill", partner: "Derba Cement", costClass: "Cement & Aggregates", productCategory: "Cement & Aggregates / Cement", workType: "Capping beam", description: "OPC cement — 200 qtl", amount: 248400, booked: true },
            { id: 81, date: "2026-04-16", ref: "BILL/2026/0412", source: "Vendor bill", partner: "Derba Cement", costClass: "Cement & Aggregates", productCategory: "Cement & Aggregates / Aggregates", workType: "Capping beam", description: "Crushed aggregate 10–20 mm — 18 m³", amount: 64000, booked: true },
            { id: 9, date: "2026-04-30", ref: "BILL/2026/0419", source: "Vendor bill", partner: "Bauer Spares", costClass: "Maintenance and Tools", productCategory: "Maintenance and Tools / Spare Parts", workType: "Piling", description: "Kelly bar & drilling teeth replacement", amount: 302400, booked: true },
            { id: 91, date: "2026-04-30", ref: "BILL/2026/0419", source: "Vendor bill", partner: "Bauer Spares", costClass: "Fuel & Lubricants", productCategory: "Fuel & Lubricants / Lubricants", workType: "Piling", description: "Hydraulic oil HV46 — 4 drums", amount: 84500, booked: true },
            { id: 10, date: "2026-05-13", ref: "BILL/2026/0405", source: "Vendor bill", partner: "Total Ethiopia", costClass: "Fuel & Lubricants", productCategory: "Fuel & Lubricants / Diesel", workType: "Excavation & cartaway", description: "Diesel — 4,300 L", amount: 862500, booked: true },
            { id: 101, date: "2026-05-13", ref: "BILL/2026/0405", source: "Vendor bill", partner: "Total Ethiopia", costClass: "Fuel & Lubricants", productCategory: "Fuel & Lubricants / Lubricants", workType: "Excavation & cartaway", description: "Engine oil 15W-40 — 2 drums", amount: 45100, booked: true },
            { id: 11, date: "2026-05-24", ref: "BILL/2026/0436", source: "Vendor bill", partner: "Abay Logistics", costClass: "Transport & Logistics", productCategory: "Transport & Logistics / Haulage", workType: "Excavation & cartaway", description: "Material haulage — May", amount: 241800, booked: true },
            { id: 12, date: "2026-05-28", ref: "PO/2026/0229", source: "Purchase order", partner: "DYWIDAG Ethiopia", costClass: "Anchor and Stressing", productCategory: "Anchor and Stressing / Strands & Anchorages", workType: "Anchoring", description: "Anchor strands & stressing — delivered, not billed", amount: 1153350, booked: false },
            { id: 13, date: "2026-06-15", ref: "PO/2026/0233", source: "Purchase order", partner: "Total Ethiopia", costClass: "Fuel & Lubricants", productCategory: "Fuel & Lubricants / Diesel", workType: null, description: "Diesel & hydraulic oil — delivered, not billed", amount: 286592, booked: false },
            { id: 14, date: "2026-06-22", ref: "BILL/2026/0458", source: "Vendor bill", partner: "Merkato Hardware", costClass: "Other Material Purchases", productCategory: "Other Material Purchases / Sundries", workType: "Shotcrete", description: "Mesh pins Ø8 — 1,200 pcs", amount: 41400, booked: true },
            { id: 141, date: "2026-06-22", ref: "BILL/2026/0458", source: "Vendor bill", partner: "Merkato Hardware", costClass: "Other Material Purchases", productCategory: "Other Material Purchases / Sundries", workType: "Shotcrete", description: "Tarpaulins 6×8 m — 20 pcs", amount: 38738, booked: true },
            { id: 142, date: "2026-06-22", ref: "BILL/2026/0458", source: "Vendor bill", partner: "Merkato Hardware", costClass: "Other Material Purchases", productCategory: "Other Material Purchases / Sundries", workType: "Shotcrete", description: "Binding wire & sundries", amount: 33000, booked: true },
            { id: 15, date: "2026-06-30", ref: "DRAFT/BILL/0091", source: "Draft bill", partner: "Ethio Plant Hire", costClass: "Machinery and Equipment Rental", productCategory: "Machinery and Equipment Rental / Trucks", workType: "Excavation & cartaway", description: "Cartaway truck trips — May–Jun, unpaid", amount: 5684000, booked: false },
        ],
    },
    {
        id: 2,
        name: "Hawassa Riverside Retaining Wall",
        client: "Sidama Urban Development",
        budgetPlan: "BUD/2026/0004",
        boq: "BOQ/0011 REV0",
        contractIncome: 62500000,
        plannedStart: "2026-09-15",
        plannedFinish: "2027-06-30",
        costClasses: [
            { name: "Machinery and Equipment Rental", budget: 4200000, booked: 2150000, unbooked: 600000 },
            { name: "Fuel & Lubricants", budget: 2600000, booked: 1340000, unbooked: 0 },
            { name: "Transport & Logistics", budget: 900000, booked: 420000, unbooked: 0 },
            { name: "Maintenance and Tools", budget: 500000, booked: 260000, unbooked: 0 },
            { name: "Concrete", budget: 9800000, booked: 3900000, unbooked: 0 },
            { name: "Overhead Cost", budget: 2100000, booked: 840000, unbooked: 0 },
            { name: "Cement & Aggregates", budget: 3400000, booked: 2150000, unbooked: 0 },
            { name: "Site Operations & Admin", budget: 300000, booked: 120000, unbooked: 0 },
            { name: "Other Material Purchases", budget: 200000, booked: 60000, unbooked: 0 },
            { name: "Labor & Subcontract", budget: 7500000, booked: 3580000, unbooked: 900000 },
            { name: "Anchor and Stressing", budget: 5200000, booked: 400000, unbooked: 0 },
            { name: "Reinforcement", budget: 8800000, booked: 3000000, unbooked: 1200000 },
        ],
        rebarCostType: "Reinforcement",
        packages: [
            { code: "MOB", name: "Mob & demob", income: 600000, booked: 520000, unbooked: 0, executed: 100, certified: 600000 },
            { code: "EXC", name: "Excavation & cartaway", income: 13400000, booked: 4900000, unbooked: 600000, executed: 60, certified: 7500000 },
            { code: "PILE", name: "Piling", income: 22000000, booked: 6800000, unbooked: 900000, executed: 20, certified: 3800000 },
            { code: "ANCHOR", name: "Anchoring", income: 12500000, booked: 600000, unbooked: 0, executed: 5, certified: 0 },
            { code: "SHOT", name: "Shotcrete", income: 8000000, booked: 0, unbooked: 0, executed: 0, certified: 0 },
            { code: "GROUT", name: "Grouting", income: 6000000, booked: 0, unbooked: 0, executed: 0, certified: 0 },
        ],
        packagesNote: "Overhead and fuel bought without a work item on the store request appear under Not allocated.",
        machines: [
            { id: 1, name: "BG20 Piling Rig", hours: 268.0, fuel: 4420, fuelBirr: 906100, daysWorked: 32, daysLogged: 36, from: "2026-10-12", to: "2026-11-16" },
            { id: 2, name: "CAT 320 Excavator", hours: 448.5, fuel: 7180, fuelBirr: 1471900, daysWorked: 52, daysLogged: 60, from: "2026-09-18", to: "2026-11-16" },
            { id: 3, name: "Hyundai R210 Rental", hours: 260.2, fuel: 4110, fuelBirr: 842550, daysWorked: 33, daysLogged: 48, from: "2026-09-30", to: "2026-11-16" },
            { id: 4, name: "Sinotruk Dump Truck", hours: 410.0, fuel: 6150, fuelBirr: 1260750, daysWorked: 50, daysLogged: 58, from: "2026-09-20", to: "2026-11-16" },
            { id: 5, name: "XCMG QY25 Crane", hours: 76.4, fuel: 990, fuelBirr: 202950, daysWorked: 11, daysLogged: 24, from: "2026-10-24", to: "2026-11-16" },
        ],
        machinesNote: "The mobile crane logged hours on fewer than half its days on site; check whether it can be released.",
        scheduleItems: [
            { item: "1.01", name: "Mobilization & site set-up", workType: "Mob & demob", start: "2026-09-15", end: "2026-09-25", value: 400000, executed: 100 },
            { item: "1.02", name: "Demobilization", workType: "Mob & demob", start: "2027-06-20", end: "2027-06-30", value: 200000, executed: 0 },
            { item: "2.01", name: "Site clearance", workType: "Excavation & cartaway", start: "2026-09-20", end: "2026-10-31", value: 1400000, executed: 100 },
            { item: "2.02", name: "Excavation & cartaway — stage 1", workType: "Excavation & cartaway", start: "2026-10-15", end: "2026-12-20", value: 7000000, executed: 70 },
            { item: "2.03", name: "Excavation & cartaway — stage 2", workType: "Excavation & cartaway", start: "2026-12-10", end: "2027-01-31", value: 5000000, executed: 0 },
            { item: "3.01", name: "Secant piles Ø600 — primary", workType: "Piling", start: "2026-10-20", end: "2027-01-31", value: 9000000, executed: 30 },
            { item: "3.02", name: "Secant piles Ø600 — secondary", workType: "Piling", start: "2026-12-01", end: "2027-03-15", value: 7000000, executed: 0 },
            { item: "3.03", name: "Pile reinforcement & concreting", workType: "Piling", start: "2026-10-25", end: "2027-03-31", value: 6000000, executed: 20 },
            { item: "4.01", name: "Tie-back anchors — row 1", workType: "Anchoring", start: "2026-11-10", end: "2027-02-28", value: 7000000, executed: 5 },
            { item: "4.02", name: "Tie-back anchors — row 2", workType: "Anchoring", start: "2027-02-15", end: "2027-04-30", value: 5500000, executed: 0 },
            { item: "5.01", name: "Shotcrete facing", workType: "Shotcrete", start: "2027-02-01", end: "2027-05-31", value: 8000000, executed: 0 },
            { item: "6.01", name: "Contact grouting", workType: "Grouting", start: "2027-04-01", end: "2027-06-30", value: 6000000, executed: 0 },
        ],
        actualFinish: "2027-07-07",
        phases: [
            { name: "Permits and Approvals", tasksDone: 2, tasksTotal: 2 },
            { name: "Construction", boq: true, current: true },
            { name: "Closeout", tasksDone: 0, tasksTotal: 3 },
        ],
        ipcs: [
            { id: 1, name: "IPC-01", boq: "BOQ/0011 REV0", date: "2026-09-30", state: "paid", amount: 2500000 },
            { id: 2, name: "IPC-02", boq: "BOQ/0011 REV0", date: "2026-10-31", state: "paid", amount: 5500000 },
            { id: 3, name: "IPC-03", boq: "BOQ/0011 REV0", date: "2026-11-15", state: "approved", amount: 7000000 },
        ],
        ledger: [
            { id: 201, date: "2026-10-31", ref: "SPR/2026/0044", source: "Site payroll", partner: "Daily workers — 26", costClass: "Labor & Subcontract", productCategory: "Labor & Subcontract / Daily Workers", workType: null, description: "Site payroll — October, 402 man-days", amount: 420000, booked: true },
            { id: 301, date: "2026-11-06", ref: "EXP/2026/0102", source: "Expense request", partner: "Site petty cash", costClass: "Maintenance and Tools", productCategory: "Maintenance and Tools / Hand Tools", workType: null, description: "Chain blocks & lifting slings", amount: 35600, booked: true },
            { id: 1, date: "2026-10-27", ref: "BILL/2026/0375", source: "Vendor bill", partner: "Nyala Insurance", costClass: "Overhead Cost", productCategory: "Overhead Cost / Insurance", workType: null, description: "CAR insurance — Q4", amount: 340000, booked: true },
            { id: 2, date: "2026-10-29", ref: "BILL/2026/0381", source: "Vendor bill", partner: "Rift Piling Plc", costClass: "Labor & Subcontract", productCategory: "Labor & Subcontract / Piling Subcontract", workType: "Piling", description: "Secant pile drilling — lot 1", amount: 2600000, booked: true },
            { id: 3, date: "2026-11-03", ref: "PO/2026/0227", source: "Purchase order", partner: "Rift Piling Plc", costClass: "Labor & Subcontract", productCategory: "Labor & Subcontract / Piling Subcontract", workType: "Piling", description: "Secant pile drilling — lot 2", amount: 900000, booked: false },
            { id: 4, date: "2026-11-05", ref: "DRAFT/BILL/0090", source: "Draft bill", partner: "Ethio Plant Hire", costClass: "Machinery and Equipment Rental", productCategory: "Machinery and Equipment Rental / Cranes", workType: "Excavation & cartaway", description: "Mobile crane rental — October", amount: 600000, booked: false },
            { id: 5, date: "2026-11-09", ref: "BILL/2026/0401", source: "Vendor bill", partner: "NOC Ethiopia", costClass: "Fuel & Lubricants", productCategory: "Fuel & Lubricants / Diesel", workType: "Excavation & cartaway", description: "Diesel — 6,500 L", amount: 1340000, booked: true },
            { id: 6, date: "2026-11-11", ref: "PAY/2026/0117", source: "Payroll", partner: "Site payroll", costClass: "Labor & Subcontract", productCategory: "Labor & Subcontract / Site Labour", workType: "Excavation & cartaway", description: "Fortnight 2 — civil crew", amount: 980000, booked: true },
            { id: 7, date: "2026-11-12", ref: "PO/2026/0231", source: "Purchase order", partner: "Kality Steel", costClass: "Reinforcement", productCategory: "Reinforcement / Rebar", workType: "Piling", description: "Rebar Ø16 — 14 t, not yet billed", amount: 1200000, booked: false },
            { id: 8, date: "2026-11-14", ref: "BILL/2026/0409", source: "Vendor bill", partner: "Habesha Cement", costClass: "Cement & Aggregates", productCategory: "Cement & Aggregates / Cement", workType: "Piling", description: "OPC cement — 1,100 qtl", amount: 2150000, booked: true },
        ],
    },
];
