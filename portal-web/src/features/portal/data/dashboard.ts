import type { PortalDashboardData } from '../types'

export const portalDashboard: PortalDashboardData = {
  sidebar: {
    productName: 'Data Analysis AI',
    productTagline: 'Data Intelligence',
    primaryNav: [
      { label: 'New Analysis', icon: 'add_chart', active: true },
      { label: 'History', icon: 'history' },
      { label: 'Data Sources', icon: 'database' },
      { label: 'Models', icon: 'neurology' },
    ],
    recentSessions: [
      { title: 'Q4 Sales Projections' },
      { title: 'User Growth Correlation' },
      { title: 'Inventory Anomaly Detection' },
    ],
    secondaryNav: [
      { label: 'Settings', icon: 'settings' },
      { label: 'Help', icon: 'help' },
    ],
    profile: {
      name: 'Alex Architect',
      plan: 'Pro Plan',
      initials: 'AA',
    },
  },
  header: {
    searchPlaceholder: 'Search analysis, datasets, or prompts...',
    actions: ['notifications', 'ios_share', 'account_circle'],
  },
  conversation: {
    messages: [
      {
        role: 'user',
        text: 'Analyze the provided CSV file. I want to see the correlation between marketing spend and new user acquisition for the last 12 months. Please generate a monthly breakdown and identify any anomalies.',
      },
      {
        role: 'assistant',
        author: 'Architect Intelligence',
        text: "I've processed marketing_metrics_v2.csv. The dataset contains 12 months of high-fidelity logs. I found a strong positive correlation (r = 0.89) between digital ad spend and conversion rates, with a significant anomaly detected in October.",
        codeBlock: {
          language: 'python',
          content: `# Correlation Analysis\ncorrelation = df['ad_spend'].corr(df['new_users'])\nanomalies = df[df['new_users'] > df['new_users'].mean() + 2 * df['new_users'].std()]\n\nprint(f"Correlation: {correlation:.2f}")\nprint(f"Detected Anomalies: {len(anomalies)} row(s)")`,
        },
        bullets: [
          { text: 'Q3 growth exceeded projections by 14%' },
          { text: 'October spike linked to "Project Horizon" campaign' },
          { text: 'Spend efficiency (CAC) decreased by 4% in December' },
        ],
      },
    ],
    thinkingLabel: 'Processing visualization...',
  },
  composer: {
    chips: [
      { icon: 'description', label: 'marketing_metrics_v2.csv', tone: 'primary' },
      { icon: 'smart_toy', label: 'GPT-4 Omni (Data)', tone: 'neutral' },
    ],
    placeholder: 'Ask Architect to analyze, predict, or visualize...',
  },
  analytics: {
    title: 'Analytical Canvas',
    chartTitle: 'User Acquisition vs Spend',
    chartChange: '+12.4%',
    chartPoints: [
      { label: 'Jan', spend: 34 },
      { label: 'Feb', spend: 48 },
      { label: 'Mar', spend: 40 },
      { label: 'Apr', spend: 61 },
      { label: 'May', spend: 57 },
      { label: 'Jun', spend: 72 },
      { label: 'Jul', spend: 86 },
      { label: 'Aug', spend: 78 },
      { label: 'Sep', spend: 55 },
      { label: 'Oct', spend: 93 },
      { label: 'Nov', spend: 47 },
      { label: 'Dec', spend: 31 },
    ],
    metrics: [
      { label: 'Confidence', value: '98.2%', meta: 'Forecast stability', tone: 'primary' },
      { label: 'Anomalies', value: '02', meta: 'Requires review', tone: 'warning' },
    ],
    tableRows: [
      { channel: 'Social Ads', roi: '4.2x', trend: 'up' },
      { channel: 'Search Engine', roi: '2.8x', trend: 'up' },
      { channel: 'Email Direct', roi: '12.5x', trend: 'flat' },
    ],
    insight: {
      title: 'Architect Insight',
      body: 'Increasing budget for Social Ads by 15% next month could yield an estimated 200+ additional users based on historical October performance.',
      actionLabel: 'Run Projection Model',
    },
  },
}
