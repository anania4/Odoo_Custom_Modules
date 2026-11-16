/** @odoo-module **/
import { Component, useState, onMounted, onWillUnmount, useRef } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import {
    playDing,
    systemPermission,
    requestSystemPermission,
    initSystemAlerts,
    showSystemNotification,
    closeSystemNotifications,
    onSystemNotificationClick,
} from "./bell_alerts";

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
            alertPermission: systemPermission(),
        });

        this._onBusUpdate = (payload) => {
            if (payload.action === "remove") {
                this._onRemoved(payload.notification_ids);
            } else {
                this._addOrUpdateNotification(payload.notification);
            }
        };
        this.busService.subscribe("generic_notification_update", this._onBusUpdate);
        this.busService.start();

        this._onClickOutside = this._onClickOutside.bind(this);

        onMounted(async () => {
            const data = await this.orm.call("res.users", "systray_identity", []);
            this.userId = data.user_id;
            this.partnerId = data.partner_id;
            await this._loadNotifications();
            await this._popPending();
            initSystemAlerts();
            this._stopClickListener = onSystemNotificationClick((id) => this.openNotification(id));
        });

        onWillUnmount(() => {
            this.busService.unsubscribe("generic_notification_update", this._onBusUpdate);
            this._removeOutsideListeners();
            if (this._stopClickListener) {
                this._stopClickListener();
            }
        });
    }

    async _loadNotifications(offset = 0) {
        const domain = [["user_id", "=", this.userId]];
        const fields = ["id","name","body","create_date","res_model","res_id","is_read","module_category","notif_type","icon_class","action_required"];
        const records = await this.orm.searchRead("generic.notification", domain, fields, {limit: this.state.limit, offset, order: "action_required desc nulls last, create_date desc"});
        this.state.notifications = records;
        // Count on the server: only the latest notifications are loaded here.
        this.state.counter = await this.orm.searchCount("generic.notification", [
            ["user_id", "=", this.userId],
            ["is_read", "=", false],
        ]);
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
        playDing();
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
                this.state.counter++;
                this._showCornerPopup(notif);
                const dinged = playDing();
                showSystemNotification(notif, dinged);
            }
        }
    }

    /** Somebody dealt with the record: these notifications no longer exist. */
    _onRemoved(notifIds) {
        closeSystemNotifications(notifIds);
        if (this.userId) {
            this._loadNotifications();
        }
    }

    _markLocallyRead(notifId) {
        const notif = this.state.notifications.find(n => n.id === notifId);
        if (notif && !notif.is_read && !notif.action_required) {
            notif.is_read = true;
            this.state.counter = Math.max(0, this.state.counter - 1);
        }
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
        this._markLocallyRead(notifId);
        closeSystemNotifications([notifId]);
    }

    async enableAlerts() {
        this.state.alertPermission = await requestSystemPermission();
        playDing();
    }

    /** Ids of the loaded notifications that may be dismissed: never the
     * action-required ones, which stay until the task is done. */
    _dismissableIds() {
        return this.state.notifications.filter(n => !n.action_required).map(n => n.id);
    }

    async markAllAsRead() {
        closeSystemNotifications(this._dismissableIds());
        await this.orm.call("generic.notification", "action_mark_all_as_read", []);
        await this._loadNotifications();
    }

    async clearAll() {
        closeSystemNotifications(this._dismissableIds());
        await this.orm.call("generic.notification", "action_clear_all", []);
        await this._loadNotifications();
    }

    async openNotification(notifId) {
        const action = await this.orm.call("generic.notification", "action_open_record", [notifId]);
        this._markLocallyRead(notifId);
        closeSystemNotifications([notifId]);
        if (action && action.type === "ir.actions.act_window_close") {
            // The record is gone, or the notification had no record to open.
            await this._loadNotifications();
        }
        this.state.open = false;
        this._removeOutsideListeners();
        if (action && action.type) this.action.doAction(action);
    }
}

registry.category("systray").add("generic_bell_notification", {
    Component: GenericBellSystray,
    sequence: 100,
});
