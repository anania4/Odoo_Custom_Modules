/** @odoo-module **/
import { Component, useState, useRef, onWillStart, onWillUnmount } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

/**
 * Car icon in the top bar for drivers (Fleet Driver access right) with a
 * vehicle delegated to them. Green badge = Active, red = In Use, grey = other.
 * One click switches the vehicle between Active and In Use.
 */
export class FleetDriverSwitch extends Component {
    static template = "fleet_operations_pro.DriverSwitch";
    static props = {};

    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.busService = useService("bus_service");
        this.rootRef = useRef("root");
        this.state = useState({ isDriver: false, vehicles: [], open: false, busy: false });

        this._onClickOutside = this._onClickOutside.bind(this);
        this._onBusUpdate = () => this.load();

        onWillStart(() => this.load());
        this.busService.subscribe("fleet_driver_vehicle_update", this._onBusUpdate);
        onWillUnmount(() => {
            this.busService.unsubscribe("fleet_driver_vehicle_update", this._onBusUpdate);
            this._removeOutsideListeners();
        });
    }

    async load() {
        const data = await this.orm.call("fleet.vehicle", "get_my_driver_vehicles", []);
        this.state.isDriver = data.is_driver;
        this.state.vehicles = data.vehicles;
    }

    /** One badge for the icon: red if any vehicle is In Use, green if any is Active, else grey */
    get overall() {
        const dots = this.state.vehicles.map((v) => v.dot);
        if (dots.includes("in_use")) {
            return "in_use";
        }
        if (dots.includes("active")) {
            return "active";
        }
        return "other";
    }

    get tooltip() {
        return this.state.vehicles.map((v) => `Vehicle ${v.plate}: ${v.status || "No status"}`).join("\n");
    }

    since(vehicle) {
        if (!vehicle.since) {
            return "";
        }
        const date = new Date(vehicle.since.replace(" ", "T") + "Z");
        const now = new Date();
        const time = date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        if (date.toDateString() === now.toDateString()) {
            return `since ${time}`;
        }
        return `since ${date.toLocaleDateString([], { day: "2-digit", month: "short" })} ${time}`;
    }

    async toggle() {
        this.state.open = !this.state.open;
        if (this.state.open) {
            await this.load();
            setTimeout(() => document.addEventListener("click", this._onClickOutside), 0);
        } else {
            this._removeOutsideListeners();
        }
    }

    async switchStatus(vehicle) {
        if (this.state.busy) {
            return;
        }
        this.state.busy = true;
        try {
            const data = await this.orm.call("fleet.vehicle", "driver_switch_status", [vehicle.id]);
            this.state.vehicles = data.vehicles;
            const updated = data.vehicles.find((v) => v.id === vehicle.id);
            if (updated) {
                this.notification.add(`${updated.plate} is now ${updated.status}`, {
                    type: updated.dot === "in_use" ? "warning" : "success",
                });
            }
        } finally {
            this.state.busy = false;
        }
    }

    _removeOutsideListeners() {
        document.removeEventListener("click", this._onClickOutside);
    }

    _onClickOutside(ev) {
        if (this.rootRef.el && !this.rootRef.el.contains(ev.target)) {
            this.state.open = false;
            this._removeOutsideListeners();
        }
    }
}

registry.category("systray").add("fleet_operations_pro.driver_switch", {
    Component: FleetDriverSwitch,
    sequence: 99,
});
