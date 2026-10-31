/** @odoo-module **/
import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService, useBus } from "@web/core/utils/hooks";

export class GenericBellSystray extends Component {
    static template = "generic_bell_notification.BellSystray";

    setup() {
        this.orm = useService("orm");
        this.busService = useService("bus_service");
        this.action = useService("action");
        this.notification = useService("notification");
        this.rootRef = useRef("root");

        this.state = useState({
            notifications: [],
            counter: 0,
            open: false,
            limit: 10,
        });

        useBus(this.busService, "notification", (notifications) => {
            for (const n of notifications) {
                if (n.type === "generic_notification_update") {
                    this._addOrUpdateNotification(n.notification);
                }
            }
        });

        this._onClickOutside = this._onClickOutside.bind(this);

        onMounted(async () => {
            const data = await this.orm.call("res.users", "systray_identity", []);
            this.userId = data.user_id;
            this.partnerId = data.partner_id;
            if (this.partnerId) this.busService.addChannel(String(this.partnerId));
            await this._loadNotifications();
            await this._popPending();
        });

        onWillUnmount(() => {
            this._removeOutsideListeners();
        });
    }

    async _loadNotifications(offset = 0) {
        const domain = [["user_id", "=", this.userId]];
        const fields = ["id","name","body","create_date","res_model","res_id","is_read","module_category","notif_type","icon_class"];
        const records = await this.orm.searchRead("generic.notification", domain, fields, {limit: this.state.limit, offset, order: "create_date desc"});
        this.state.notifications = records;
        this.state.counter = records.filter(n => !n.is_read).length;
    }

    _showCornerPopup(n) {
        const validTypes = ["info", "success", "warning", "danger"];
        let closeFn;
        closeFn = this.notification.add(n.body || "", {
            title: n.name,
            type: validTypes.includes(n.notif_type) ? n.notif_type : "info",
            sticky: false,
            autocloseDelay: 4000,
            buttons: [
                {
                    name: "Open",
                    primary: true,
                    onClick: () => {
                        if (closeFn) {
                            closeFn();
                        }
                        this.openNotification(n.id);
                    },
                },
            ],
        });
        return closeFn;
    }

    /**
     * Show a corner popup (once) for unread notifications that arrived while
     * the user was offline. Up to 3 individual popups, then one summary popup.
     * All popups automatically disappear after 4 seconds.
     */
    async _popPending() {
        let pending = [];
        try {
            pending = await this.orm.call("generic.notification", "pop_pending", []);
        } catch (e) {
            return;
        }
        if (!pending.length) {
            return;
        }
        const MAX_INDIVIDUAL = 3;
        // oldest first so the newest ends up on top of the stack
        const shown = pending.slice(0, MAX_INDIVIDUAL).reverse();
        for (const n of shown) {
            this._showCornerPopup(n);
        }
        const rest = pending.length - MAX_INDIVIDUAL;
        if (rest > 0) {
            let closeFn;
            closeFn = this.notification.add(
                rest === 1
                    ? "You have 1 more unread notification."
                    : `You have ${rest} more unread notifications.`,
                {
                    title: "Notifications",
                    type: "info",
                    sticky: false,
                    autocloseDelay: 4000,
                    buttons: [
                        {
                            name: "Open bell",
                            primary: true,
                            onClick: () => {
                                if (closeFn) {
                                    closeFn();
                                }
                                if (!this.state.open) {
                                    this._onToggle();
                                }
                            },
                        },
                    ],
                }
            );
        }
    }

    async loadMore() {
        this.state.limit += 10;
        await this._loadNotifications();
    }

    _addOrUpdateNotification(notif) {
        const index = this.state.notifications.findIndex(n => n.id === notif.id);
        if (index !== -1) {
            this.state.notifications[index] = notif;
        } else {
            // arrived live: the user is online, mark popped so pop_pending doesn't replay it
            this.orm.call("generic.notification", "action_mark_popped", [notif.id]).catch(() => {});
            this.state.notifications.unshift(notif);
            if (this.state.notifications.length > this.state.limit) {
                this.state.notifications.pop();
            }
            if (!notif.is_read) {
                this._showCornerPopup(notif);
            }
        }
        this.state.counter = this.state.notifications.filter(n => !n.is_read).length;
    }

    _onToggle() {
        this.state.open = !this.state.open;
        if (this.state.open) {
            setTimeout(() => {
                document.addEventListener("click", this._onClickOutside);
                document.addEventListener("touchstart", this._onClickOutside, { passive: true });
            }, 0);
        } else {
            this._removeOutsideListeners();
        }
    }

    _removeOutsideListeners() {
        document.removeEventListener("click", this._onClickOutside);
        document.removeEventListener("touchstart", this._onClickOutside);
    }

    _onClickOutside(ev) {
        if (this.rootRef.el && !this.rootRef.el.contains(ev.target)) {
            this.state.open = false;
            this._removeOutsideListeners();
        }
    }

    async markAsRead(notifId) {
        await this.orm.call("generic.notification", "action_mark_as_read", [notifId]);
        const notif = this.state.notifications.find(n => n.id === notifId);
        if (notif) notif.is_read = true;
        this.state.counter = this.state.notifications.filter(n => !n.is_read).length;
    }

    async markAllAsRead() {
        await this.orm.call("generic.notification", "action_mark_all_as_read", []);
        this.state.notifications.forEach(n => n.is_read = true);
        this.state.counter = 0;
    }

    async clearAll() {
        await this.orm.call("generic.notification", "action_clear_all", []);
        this.state.notifications = [];
        this.state.counter = 0;
    }

    async openNotification(notifId) {
        const action = await this.orm.call("generic.notification", "action_open_record", [notifId]);
        const notif = this.state.notifications.find(n => n.id === notifId);
        if (notif) notif.is_read = true;
        this.state.counter = this.state.notifications.filter(n => !n.is_read).length;
        this.state.open = false;
        this._removeOutsideListeners();
        if (action && action.type) this.action.doAction(action);
    }
}

registry.category("systray").add("generic_bell_notification", {
    Component: GenericBellSystray,
    sequence: 100,
});
