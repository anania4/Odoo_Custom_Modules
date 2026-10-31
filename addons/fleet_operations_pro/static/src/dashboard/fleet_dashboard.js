/** @odoo-module **/

import { registry } from "@web/core/registry";
import { Component, onWillStart, useState } from "@odoo/owl";
import { useService } from "@web/core/utils/hooks";

export class FleetDashboard extends Component {
    setup() {
        this.orm = useService("orm");
        this.notification = useService("notification");
        this.action = useService("action");
        
        this.state = useState({
            data: null,
            loading: true,
            lastUpdated: null,
            activeTab: 'overview'
        });

        onWillStart(async () => {
            await this.loadDashboardData();
        });
    }

    async loadDashboardData() {
        this.state.loading = true;
        try {
            // Call the dashboard data method
            const data = await this.orm.call(
                "fleet.dashboard",
                "get_dashboard_data",
                []
            );
            
            // Process data for the dashboard
            this.processDashboardData(data);
            this.state.lastUpdated = new Date();
            
        } catch (error) {
            console.error("Error loading dashboard data:", error);
            this.notification.add(
                "Failed to load dashboard data. Please try again.",
                { type: "danger" }
            );
        } finally {
            this.state.loading = false;
        }
    }
    
    processDashboardData(data) {
        const totalVehicles = data.kpis.total_vehicles || 1;

        if (data.charts.vehicle_by_status) {
            data.charts.vehicle_by_status = data.charts.vehicle_by_status.map(status => ({
                ...status,
                percentage: Math.round((status.value / totalVehicles) * 100)
            }));
        }

        if (data.charts.vehicle_by_category) {
            data.charts.vehicle_by_category = data.charts.vehicle_by_category.map(category => ({
                ...category,
                percentage: Math.round((category.value / totalVehicles) * 100)
            }));
        }

        if (data.charts.fuel_cost_by_vehicle) {
            const maxFuelCost = Math.max(
                ...data.charts.fuel_cost_by_vehicle.map(item => item.value),
                1
            );
            data.charts.fuel_cost_by_vehicle = data.charts.fuel_cost_by_vehicle.map(item => ({
                ...item,
                percentage: Math.round((item.value / maxFuelCost) * 100)
            }));
        }

        if (data.alerts.contract_details) {
            data.alerts.contract_details = data.alerts.contract_details.map(item => {
                const daysLeft = Number(item.days_left) || 0;

                return {
                    ...item,
                    status: daysLeft < 0 ? 'Overdue' : 'Ending Soon',
                    status_class: daysLeft < 0 ? 'danger' : 'warning'
                };
            });
        }

        this.state.data = data;
    }

    async refresh() {
        this.notification.add("Refreshing dashboard data...", { type: "info" });
        await this.loadDashboardData();
    }
    
    openAction(resModel, domain, name) {
        const action = {
            type: 'ir.actions.act_window',
            name: name,
            res_model: resModel,
            views: [[false, 'list'], [false, 'form']],
            target: 'current',
        };
        if (domain) {
            action.domain = domain;
        }
        this.action.doAction(action);
    }
    
    openAvailableVehicles() {
        this.openAction('fleet.vehicle', [['status_code', '=', 'available']], 'Available Vehicles');
    }

    openAllVehicles() {
        this.openAction('fleet.vehicle', [], 'Vehicles');
    }

    openOpenServices() {
        this.openAction('fleet.service', [['state', 'in', ['new', 'running']]], 'Open Services');
    }

    openVehiclesDueByKm() {
        const ids = this.state.data?.cards?.services?.due_by_km_vehicle_ids || [];
        this.openAction('fleet.vehicle', [['id', 'in', ids]], 'Vehicles Due for Service (km)');
    }

    openContractsAttention() {
        const ids = this.state.data?.cards?.contracts?.attention_ids || [];
        this.openAction('fleet.contract', [['id', 'in', ids]], 'Contracts Needing Attention');
    }

    openPendingRequests() {
        if (!this.state.data?.cards?.requests?.allowed) {
            return;
        }
        this.openAction(
            'fleet.request',
            [['state', 'in', ['submitted', 'dept_approved', 'fleet_approved']]],
            'Pending Fleet Requests'
        );
    }

    openPendingFuelRequests() {
        this.openAction(
            'fleet.fuel.request',
            [['state', 'in', ['submitted', 'approved']]],
            'Pending Fuel Requests'
        );
    }

    openRecord(resModel, resId) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            res_model: resModel,
            res_id: resId,
            views: [[false, 'form']],
            target: 'current',
        });
    }
    
    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    formatCurrency(value) {
        const currency = this.state.data?.currency || {
            symbol: '$',
            position: 'before',
            decimal_places: 2
        };
        const numValue = Number(value) || 0;
        const absValue = Math.abs(numValue);
        const sign = numValue < 0 ? '-' : '';
        const withCurrency = (amount) => currency.position === 'after'
            ? `${sign}${amount} ${currency.symbol}`
            : `${sign}${currency.symbol}${amount}`;

        // Format large numbers with K, M, B suffix
        if (absValue >= 1000000000) {
            return withCurrency((absValue / 1000000000).toFixed(1) + 'B');
        } else if (absValue >= 1000000) {
            return withCurrency((absValue / 1000000).toFixed(1) + 'M');
        } else if (absValue >= 10000) {
            return withCurrency((absValue / 1000).toFixed(1) + 'K');
        }

        const amount = new Intl.NumberFormat('en-US', {
            minimumFractionDigits: currency.decimal_places,
            maximumFractionDigits: currency.decimal_places
        }).format(absValue);
        return withCurrency(amount);
    }
    
    formatCompactNumber(value) {
        if (value === undefined || value === null) return '0';
        const numValue = Number(value);
        if (isNaN(numValue)) return '0';
        
        // Format large numbers with K, M, B suffix
        if (Math.abs(numValue) >= 1000000000) {
            return (numValue / 1000000000).toFixed(1) + 'B';
        } else if (Math.abs(numValue) >= 1000000) {
            return (numValue / 1000000).toFixed(1) + 'M';
        } else if (Math.abs(numValue) >= 10000) {
            return (numValue / 1000).toFixed(1) + 'K';
        }
        
        return numValue.toLocaleString('en-US');
    }

    formatNumber(value, decimals = 2) {
        if (value === undefined || value === null) return '0';
        const numValue = Number(value);
        if (isNaN(numValue)) return '0';
        
        return numValue.toLocaleString('en-US', {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals
        });
    }
    
    formatDate(dateString) {
        if (!dateString) return '';
        const options = { 
            year: 'numeric', 
            month: 'short', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        };
        return new Date(dateString).toLocaleDateString('en-US', options);
    }
    
    getTimeAgo(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);
        
        let interval = Math.floor(seconds / 31536000);
        if (interval >= 1) return `${interval} year${interval === 1 ? '' : 's'} ago`;
        
        interval = Math.floor(seconds / 2592000);
        if (interval >= 1) return `${interval} month${interval === 1 ? '' : 's'} ago`;
        
        interval = Math.floor(seconds / 86400);
        if (interval >= 1) return `${interval} day${interval === 1 ? '' : 's'} ago`;
        
        interval = Math.floor(seconds / 3600);
        if (interval >= 1) return `${interval} hour${interval === 1 ? '' : 's'} ago`;
        
        interval = Math.floor(seconds / 60);
        if (interval >= 1) return `${interval} minute${interval === 1 ? '' : 's'} ago`;
        
        return 'Just now';
    }
}

// Add template and registry
FleetDashboard.template = "fleet_operations_pro.Dashboard";

// Add component to the action registry
registry.category("actions").add("fleet_dashboard", FleetDashboard);

// Add component to the public components for potential reuse
registry.category("public_components").add("fleet_dashboard", FleetDashboard);
