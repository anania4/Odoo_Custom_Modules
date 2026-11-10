/** @odoo-module **/

/**
 * Hour / minute picker for float time fields (e.g. 8.5 = 08:30).
 * Same behaviour and look as Odoo's Time Off "float_time_selection"
 * widget, kept here so the module does not depend on hr_holidays.
 * The field still stores a plain float, so no model logic changes.
 */
import { Component, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { usePopover } from "@web/core/popover/popover_hook";
import { FloatTimeField, floatTimeField } from "@web/views/fields/float_time/float_time_field";

const numberRange = (min, max) => [...Array(max - min)].map((_, i) => i + min);
const HOURS = numberRange(0, 24).map((h) => [h, String(h).padStart(2, "0")]);
const MINUTES = numberRange(0, 60).map((m) => [m, String(m).padStart(2, "0")]);

function floatToHoursMinutes(value) {
    value = value || 0;
    let hours = Math.floor(value);
    let minutes = Math.round((value - hours) * 60);
    if (minutes === 60) {
        hours += 1;
        minutes = 0;
    }
    return { hours: hours % 24, minutes };
}

export class EquipmentTimePickerPopover extends Component {
    static template = "equipment_timesheet.TimePickerPopover";
    static props = {
        close: { type: Function },
        hours: Number,
        minutes: Number,
        onTimeChange: { type: Function },
    };

    setup() {
        this.availableHours = HOURS;
        this.availableMinutes = MINUTES;
        this.state = useState({
            hours: this.props.hours,
            minutes: this.props.minutes,
        });
    }

    onChange() {
        this.props.onTimeChange(parseInt(this.state.hours), parseInt(this.state.minutes));
    }
}

export class EquipmentTimePickerField extends FloatTimeField {
    static template = "equipment_timesheet.TimePickerField";

    setup() {
        super.setup();
        this.popover = usePopover(EquipmentTimePickerPopover);
    }

    onInputClick(ev) {
        if (this.popover.isOpen) {
            return;
        }
        const { hours, minutes } = floatToHoursMinutes(this.props.record.data[this.props.name]);
        this.popover.open(ev.currentTarget, {
            hours,
            minutes,
            onTimeChange: (h, m) => {
                // Save straight away so computed totals refresh live
                this.props.record.update({ [this.props.name]: h + m / 60 });
            },
        });
    }

    onInputTyped() {
        // Typing by hand works like the normal float_time field
        this.popover.close();
    }
}

registry.category("fields").add("equipment_time_picker", {
    ...floatTimeField,
    component: EquipmentTimePickerField,
});
