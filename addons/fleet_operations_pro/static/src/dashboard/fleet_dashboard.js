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
        // Calculate additional metrics
        const totalVehicles = data.kpis.total_vehicles || 1; // Avoid division by zero
        
        // Add percentage calculations for vehicle status
        if (data.charts.vehicle_by_status) {
            data.charts.vehicle_by_status = data.charts.vehicle_by_status.map(status => ({
                ...status,
                percentage: Math.round((status.value / totalVehicles) * 100)
            }));
        }
        
        // Calculate total costs for percentage calculations
        const totalCosts = data.kpis.total_costs || 1;
        
        // Add percentage for cost categories
        if (data.charts.cost_by_category) {
            data.charts.cost_by_category = data.charts.cost_by_category.map(category => ({
                ...category,
                percentage: Math.round((category.value / totalCosts) * 100)
            }));
        }
        
        // Process top cost vehicles with trend indicators
        if (data.charts.top_cost_vehicles) {
            const maxCost = Math.max(...data.charts.top_cost_vehicles.map(v => v.value), 1);
            data.charts.top_cost_vehicles = data.charts.top_cost_vehicles.map(vehicle => ({
                ...vehicle,
                percentage: Math.round((vehicle.value / maxCost) * 100),
                // Add mock trend data (in a real app, this would come from the backend)
                cost_change: Math.floor(Math.random() * 30) - 15, // Random number between -15 and 15
                mileage: Math.floor(Math.random() * 50000) + 5000 // Random mileage between 5k and 55k
            }));
        }
        
        // Process contract renewal alerts
        if (data.alerts.contract_details) {
            data.alerts.contract_details = data.alerts.contract_details.map(item => {
                const daysLeft = Number(item.days_left) || 0;
                
                return {
                    ...item,
                    status: daysLeft < 0 ? 'Overdue' : 
                            daysLeft <= 7 ? 'Ending Soon' : 'Ending Soon',
                    status_class: daysLeft < 0 ? 'danger' : 'warning'
                };
            });
        }
        
        // Add some mock trend data for demonstration
        data.kpis.vehicles_change_percent = (Math.random() * 10) - 2; // Random between -2% and 8%
        data.kpis.revenue_change = Math.floor(Math.random() * 5000) - 1000; // Random between -1000 and 4000
        data.kpis.revenue_change_percent = (Math.random() * 15) - 5; // Random between -5% and 10%
        data.kpis.avg_cost_per_km_change = (Math.random() * 5) - 2.5; // Random between -2.5% and 2.5%
        data.kpis.fuel_efficiency_change = (Math.random() * 8) - 4; // Random between -4% and 4%
        data.kpis.utilization_change = (Math.random() * 10) - 2; // Random between -2% and 8%
        data.kpis.monthly_budget = 50000; // Example monthly budget
        
        this.state.data = data;
    }

    async refresh() {
        this.notification.add("Refreshing dashboard data...", { type: "info" });
        await this.loadDashboardData();
    }
    
    openAction(resModel, domain, name) {
        this.action.doAction({
            type: 'ir.actions.act_window',
            name: name,
            res_model: resModel,
            view_mode: 'list,form',
            domain: domain,
            target: 'current',
        });
    }
    
    openFuelLogs() {
        const date30 = new Date(Date.now() - 30 * 86400000).toISOString().slice(0, 10);
        this.openAction('fleet.fuel.log', [['date', '>=', date30]], 'Fuel Logs (30 days)');
    }
    
    openRequests() {
        this.openAction('fleet.request', [], 'Fleet Requests');
    }
    
    openContracts() {
        this.openAction('fleet.contract', [['active', '=', true]], 'Contracts');
    }
    
    openServices() {
        this.openAction('fleet.service', [], 'Services');
    }
    
    setActiveTab(tab) {
        this.state.activeTab = tab;
    }

    formatCurrency(value) {
        if (value === undefined || value === null) return '$0.00';
        const numValue = Number(value);
        if (isNaN(numValue)) return '$0.00';
        
        // Format large numbers with K, M, B suffix
        if (Math.abs(numValue) >= 1000000000) {
            return '$' + (numValue / 1000000000).toFixed(1) + 'B';
        } else if (Math.abs(numValue) >= 1000000) {
            return '$' + (numValue / 1000000).toFixed(1) + 'M';
        } else if (Math.abs(numValue) >= 10000) {
            return '$' + (numValue / 1000).toFixed(1) + 'K';
        }
        
        return new Intl.NumberFormat('en-US', {
            style: 'currency',
            currency: 'USD',
            minimumFractionDigits: 2,
            maximumFractionDigits: 2
        }).format(numValue);
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
