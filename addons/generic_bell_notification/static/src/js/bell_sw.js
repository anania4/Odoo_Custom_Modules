/* Service worker of generic_bell_notification.
 * Only used to show OS notifications (required by Android) and to react to clicks. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil(self.clients.claim()));

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const data = event.notification.data || {};
    event.waitUntil(
        self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((windows) => {
            for (const win of windows) {
                if ("focus" in win) {
                    win.postMessage({ type: "gbn_open", id: data.id });
                    return win.focus();
                }
            }
            return self.clients.openWindow(data.url || "/odoo");
        })
    );
});
