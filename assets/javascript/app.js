import * as JsCookie from "js-cookie";
import Chart from 'chart.js/auto';
import { DashboardCharts as AppDashboardCharts } from './dashboard/dashboard-charts';
import { installCommandCenter } from './dashboard/command-center';
export { AppDashboardCharts as DashboardCharts };
export const Cookies = JsCookie.default;

// Ensure SiteJS global exists
if (typeof window.SiteJS === 'undefined') {
  window.SiteJS = {};
}
window.Chart = Chart;
window.dispatchEvent(new Event('novena:chart-ready'));

// Assign this entry's exports to SiteJS.app
window.SiteJS.app = {
  DashboardCharts: AppDashboardCharts,
  Cookies: JsCookie.default,
};

installCommandCenter();
