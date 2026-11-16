/** @odoo-module **/
/**
 * Sound + system (Windows / macOS / Android) notifications for the generic bell.
 *
 *  - playDing(): short two-note "ding-ding" generated with Web Audio (no audio file).
 *  - showSystemNotification(): OS-level notification in the screen corner, shown
 *    only when Odoo is in the background. It stays until the user clicks or
 *    dismisses it (requireInteraction).
 *  Both need the user to have clicked somewhere in Odoo at least once (browser rule),
 *  and system notifications need HTTPS (or localhost) + the user's permission.
 */

const SW_URL = "/generic_bell_notification/static/src/js/bell_sw.js";
const SW_SCOPE = "/generic_bell_notification/static/src/js/";
const ICON = "/web/static/img/favicon.ico";

let audioCtx = null;
let swRegistration = null;

/* ------------------------------ sound ------------------------------ */

function getAudioContext() {
    if (!audioCtx) {
        const Ctx = window.AudioContext || window.webkitAudioContext;
        if (!Ctx) {
            return null;
        }
        audioCtx = new Ctx();
    }
    return audioCtx;
}

function unlockAudio() {
    const ctx = getAudioContext();
    if (ctx && ctx.state === "suspended") {
        ctx.resume().catch(() => {});
    }
}
// Browsers only allow sound after a user gesture: unlock on the first interaction.
for (const evt of ["pointerdown", "keydown", "touchstart"]) {
    document.addEventListener(evt, unlockAudio, { passive: true });
}

function tone(ctx, freq, start, duration, volume) {
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(freq, start);
    gain.gain.setValueAtTime(0.0001, start);
    gain.gain.exponentialRampToValueAtTime(volume, start + 0.01);
    gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start(start);
    osc.stop(start + duration + 0.05);
}

/** Play the notification sound. Returns true if the browser allowed it right away. */
export function playDing() {
    const ctx = getAudioContext();
    if (!ctx) {
        return false;
    }
    const schedule = () => {
        const t = ctx.currentTime;
        tone(ctx, 880, t, 0.45, 0.25);
        tone(ctx, 1318.5, t + 0.12, 0.7, 0.22);
    };
    if (ctx.state === "running") {
        schedule();
        return true;
    }
    ctx.resume().then(schedule).catch(() => {});
    return false;
}

/* ------------------------ system notifications ------------------------ */

export function systemAlertsSupported() {
    return window.isSecureContext && "Notification" in window;
}

export function systemPermission() {
    return systemAlertsSupported() ? Notification.permission : "unsupported";
}

async function registerSW() {
    if (swRegistration) {
        return swRegistration;
    }
    if (!("serviceWorker" in navigator)) {
        return null;
    }
    const reg = await navigator.serviceWorker.register(SW_URL, { scope: SW_SCOPE });
    if (!reg.active) {
        const worker = reg.installing || reg.waiting;
        if (worker) {
            await new Promise((resolve) => {
                if (worker.state === "activated") {
                    return resolve();
                }
                worker.addEventListener("statechange", () => {
                    if (worker.state === "activated") {
                        resolve();
                    }
                });
                setTimeout(resolve, 5000);
            });
        }
    }
    swRegistration = reg;
    return reg;
}

/** Must be called from a click handler (browser rule). */
export async function requestSystemPermission() {
    if (!systemAlertsSupported()) {
        return "unsupported";
    }
    const permission = await Notification.requestPermission();
    if (permission === "granted") {
        try {
            await registerSW();
        } catch (e) {
            // service worker unavailable: plain Notification fallback is used
        }
    }
    return permission;
}

/** Prepare the service worker when permission was already granted earlier. */
export async function initSystemAlerts() {
    if (systemPermission() === "granted") {
        try {
            await registerSW();
        } catch (e) {
            // ignore
        }
    }
}

function recordUrl(n) {
    if (n.res_model && n.res_id) {
        return `/web#model=${n.res_model}&id=${n.res_id}&view_type=form`;
    }
    return "/odoo";
}

/**
 * Show an OS notification, only when Odoo is in the background.
 * `silent` = true when our own ding already played (avoids a double sound).
 */
export async function showSystemNotification(n, silent = false) {
    if (systemPermission() !== "granted") {
        return;
    }
    if (document.visibilityState === "visible" && document.hasFocus()) {
        return;
    }
    if (await hasPushSubscription()) {
        return; // Web Push delivers it (bell_push_sw.js): avoid a double notification
    }
    const options = {
        body: n.body || "",
        icon: ICON,
        badge: ICON,
        tag: `gbn-${n.id}`,
        requireInteraction: true, // stays until the user acts on it
        silent,
        data: { id: n.id, url: recordUrl(n) },
    };
    try {
        const reg = await registerSW();
        if (reg) {
            await reg.showNotification(n.name, options);
            return;
        }
    } catch (e) {
        // fall through to the plain Notification API
    }
    try {
        const native = new Notification(n.name, options);
        native.onclick = () => {
            window.focus();
            native.close();
        };
    } catch (e) {
        // not supported (e.g. Android without service worker)
    }
}

/** Remove OS notifications once handled inside Odoo. ids = null closes all. */
export async function closeSystemNotifications(ids = null) {
    // our own worker (shown by this page) + Odoo's backend worker (shown by Web Push)
    const registrations = [swRegistration, await mainRegistration()].filter(Boolean);
    for (const reg of registrations) {
        try {
            const list = await reg.getNotifications();
            for (const notif of list) {
                const data = notif.data || {};
                if (reg !== swRegistration && !data.gbn) {
                    continue; // not a bell notification
                }
                if (!ids || ids.includes(data.id)) {
                    notif.close();
                }
            }
        } catch (e) {
            // ignore
        }
    }
}

/** Odoo's backend service worker (/web/service-worker.js), which receives Web Push. */
async function mainRegistration() {
    try {
        return (await navigator.serviceWorker?.getRegistration("/odoo")) || null;
    } catch (e) {
        return null;
    }
}

async function hasPushSubscription() {
    try {
        const reg = await mainRegistration();
        return Boolean(reg && reg.pushManager && (await reg.pushManager.getSubscription()));
    } catch (e) {
        return false;
    }
}

/** Called when the user clicks an OS notification while Odoo is open. */
export function onSystemNotificationClick(callback) {
    if (!("serviceWorker" in navigator)) {
        return () => {};
    }
    const handler = (ev) => {
        if (ev.data && ev.data.type === "gbn_open") {
            callback(ev.data.id);
        }
    };
    navigator.serviceWorker.addEventListener("message", handler);
    return () => navigator.serviceWorker.removeEventListener("message", handler);
}
