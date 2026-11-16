// @odoo-module ignore
/* eslint-disable no-restricted-globals */
/* Bell notifications received by Web Push (works when Odoo is closed).
 * Prepended to Odoo's backend service worker (/web/service-worker.js), see
 * controllers/webmanifest.py. Only pushes flagged `gbn` are handled here;
 * everything else is left to Odoo's own push code. */

function gbnPushData(event) {
    try {
        const notification = event.data.json();
        return notification.options && notification.options.data && notification.options.data.gbn
            ? notification
            : null;
    } catch {
        return null;
    }
}

self.addEventListener("push", (event) => {
    const notification = gbnPushData(event);
    if (!notification) {
        return;
    }
    event.stopImmediatePropagation();
    event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
            // Odoo is on screen: the bell already shows its popup and plays its sound.
            if (windows.some((win) => win.focused && win.visibilityState === "visible")) {
                return;
            }
            return self.registration.showNotification(notification.title, notification.options);
        })
    );
});

self.addEventListener("notificationclick", (event) => {
    const data = event.notification.data;
    if (!data || !data.gbn) {
        return;
    }
    event.stopImmediatePropagation();
    event.notification.close();
    event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
            for (const win of windows) {
                if ("focus" in win) {
                    // the bell opens the record and marks the notification as read
                    win.postMessage({ type: "gbn_open", id: data.id });
                    return win.focus();
                }
            }
            return self.clients.openWindow(data.url || "/odoo");
        })
    );
});
