// Real-Time Dashboard JavaScript
// Uses Server-Sent Events (SSE) for zero-lag updates

// Chart.js setup with smooth animations
const borrowRateChart = new Chart(document.getElementById('borrowRateChart'), {
  type: 'line',
  data: {
    labels: [],
    datasets: [{
      label: 'Borrows/min',
      data: [],
      borderColor: '#00adef',
      backgroundColor: 'rgba(0, 173, 239, 0.1)',
      tension: 0.4,
      fill: true,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 4
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 300,
      easing: 'easeInOutQuad'
    },
    scales: {
      x: { 
        display: true,
        grid: { display: false }
      },
      y: { 
        beginAtZero: true,
        ticks: { precision: 0 }
      }
    },
    plugins: {
      legend: { display: false },
      tooltip: { mode: 'index', intersect: false }
    }
  }
});

const overageChart = new Chart(document.getElementById('overageChart'), {
  type: 'line',
  data: {
    labels: [],
    datasets: [{
      label: 'Overage Checkouts',
      data: [],
      borderColor: '#d32f2f',
      backgroundColor: 'rgba(211, 47, 47, 0.1)',
      tension: 0.4,
      fill: true,
      borderWidth: 2,
      pointRadius: 0,
      pointHoverRadius: 4
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 300,
      easing: 'easeInOutQuad'
    },
    scales: {
      x: { 
        display: true,
        grid: { display: false }
      },
      y: { 
        beginAtZero: true,
        ticks: { precision: 0 }
      }
    },
    plugins: {
      legend: { display: false },
      tooltip: { mode: 'index', intersect: false }
    }
  }
});

const utilizationChart = new Chart(document.getElementById('utilizationChart'), {
  type: 'bar',
  data: {
    labels: [],
    datasets: [{
      label: 'In Commit',
      data: [],
      backgroundColor: '#00adef',
      stack: 'stack1'
    }, {
      label: 'In Overage',
      data: [],
      backgroundColor: '#f57c00',
      stack: 'stack1'
    }, {
      label: 'Available',
      data: [],
      backgroundColor: '#e0e0e0',
      stack: 'stack1'
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: {
      duration: 300,
      easing: 'easeInOutQuad'
    },
    indexAxis: 'y',
    scales: {
      x: { 
        stacked: true,
        beginAtZero: true,
        ticks: { precision: 0 }
      },
      y: { 
        stacked: true,
        ticks: {
          autoSkip: false,
          font: { size: 11 }
        }
      }
    },
    plugins: {
      legend: { 
        display: true,
        position: 'bottom'
      },
      tooltip: { 
        mode: 'index',
        intersect: false
      }
    }
  }
});

// Per-Tool Charts (created on demand)
let toolBorrowChart = new Chart(document.getElementById('toolBorrowChart'), {
  type: 'line',
  data: {
    labels: [],
    datasets: [{
      label: 'Borrows',
      data: [],
      borderColor: '#00adef',
      backgroundColor: 'rgba(0, 173, 239, 0.1)',
      tension: 0.4,
      fill: true,
      borderWidth: 2,
      pointRadius: 4,
      pointHoverRadius: 6,
      pointBackgroundColor: '#00adef'
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    animation: { duration: 300 },
    scales: {
      x: { display: true },
      y: { beginAtZero: true, ticks: { precision: 0 } }
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        mode: 'index',
        intersect: false,
        callbacks: {
          afterLabel: function(context) {
            // Add user info to tooltip
            const dataPoint = context.dataset.metadata?.[context.dataIndex];
            if (dataPoint && dataPoint.user) {
              return `User: ${dataPoint.user}`;
            }
            return '';
          }
        }
      }
    }
  }
});

let toolUserChart = new Chart(document.getElementById('toolUserChart'), {
  type: 'doughnut',
  data: {
    labels: [],
    datasets: [{
      data: [],
      backgroundColor: [
        '#00adef', '#667eea', '#f093fb', '#4facfe', 
        '#43e97b', '#fa709a', '#fee140', '#30cfd0'
      ]
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'right' },
      tooltip: {
        callbacks: {
          label: function(context) {
            return `${context.label}: ${context.formattedValue} checkouts`;
          }
        }
      }
    }
  }
});

let toolCommitChart = new Chart(document.getElementById('toolCommitChart'), {
  type: 'doughnut',
  data: {
    labels: ['In Commit', 'In Overage', 'Available'],
    datasets: [{
      data: [0, 0, 0],
      backgroundColor: ['#00adef', '#f57c00', '#e0e0e0']
    }]
  },
  options: {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { position: 'bottom' }
    }
  }
});

// Metrics tracking
let WINDOW_SIZE = 1800; // Default: 30 minutes (in seconds)

// Throttle chart updates to prevent blocking during heavy load
let chartUpdatePending = false;
let chartUpdateScheduled = false;
let lastBorrowRate = 0;
let lastOverageRate = 0;
let selectedTool = 'all'; // Current tool filter
let allTools = []; // List of all available tools

// Server-side tool metrics are now buffered on the backend
// We just need to track which tool is selected
let toolMetricsCache = null; // Will store the latest tool_metrics from SSE
let prevToolNames = [];

// Time range selector
const timeRangeSelector = document.getElementById('time-range');
timeRangeSelector.addEventListener('change', (e) => {
  const newRange = parseInt(e.target.value);
  WINDOW_SIZE = newRange;
  
  // Update chart titles
  const label = getTimeRangeLabel(newRange);
  document.getElementById('borrow-chart-title').textContent = `License Borrows (Last ${label})`;
  document.getElementById('overage-chart-title').textContent = `Overage Checkouts (Last ${label})`;
  
  // Clear overview charts
  borrowRateChart.data.labels = [];
  borrowRateChart.data.datasets[0].data = [];
  overageChart.data.labels = [];
  overageChart.data.datasets[0].data = [];
  borrowRateChart.update();
  overageChart.update();
  
  // If a tool is selected, it will reload from server-side buffer on next SSE event
  if (selectedTool !== 'all' && toolMetricsCache) {
    updateToolSpecificCharts(selectedTool, toolMetricsCache);
  }
  
  console.log(`Time range changed to: ${label} (${newRange} seconds)`);
});

function getTimeRangeLabel(seconds) {
  if (seconds < 60) return `${seconds} seconds`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} minutes`;
  return `${Math.round(seconds / 3600)} hour${seconds > 3600 ? 's' : ''}`;
}

// Tool filter selector
const toolFilterSelector = document.getElementById('tool-filter');
toolFilterSelector.addEventListener('change', (e) => {
  selectedTool = e.target.value;
  
  if (selectedTool === 'all') {
    // Show overview charts
    document.getElementById('overview-charts').style.display = 'block';
    document.getElementById('tool-specific-charts').style.display = 'none';
    document.getElementById('tool-info').textContent = '';
  } else {
    // Show tool-specific charts
    document.getElementById('overview-charts').style.display = 'none';
    document.getElementById('tool-specific-charts').style.display = 'block';
    
    // Load buffered data for this tool from server-side cache immediately
    if (toolMetricsCache) {
      updateToolSpecificCharts(selectedTool, toolMetricsCache);
    } else {
      // Clear while waiting for first SSE payload
      toolBorrowChart.data.labels = [];
      toolBorrowChart.data.datasets[0].data = [];
      toolBorrowChart.data.datasets[0].metadata = [];
      toolBorrowChart.update();
    }
    
    // Clear other charts (will be populated by next SSE update)
    toolUserChart.data.labels = [];
    toolUserChart.data.datasets[0].data = [];
    toolCommitChart.data.datasets[0].data = [0, 0, 0];
    
    toolUserChart.update();
    toolCommitChart.update();
  }
  
  console.log(`Tool filter changed to: ${selectedTool}`);
});

function updateToolSelector(tools) {
  const names = tools.map(t => t.tool).sort();
  if (JSON.stringify(names) === JSON.stringify(prevToolNames)) {
    return; // No change; avoid resetting the dropdown while user interacts
  }
  prevToolNames = names;
  allTools = tools;
  const currentSelection = toolFilterSelector.value;
  toolFilterSelector.innerHTML = '<option value="all">All Tools (Overview)</option>';
  tools.forEach(tool => {
    const option = document.createElement('option');
    option.value = tool.tool;
    option.textContent = tool.tool;
    toolFilterSelector.appendChild(option);
  });
  if (currentSelection && currentSelection !== 'all') {
    const stillExists = tools.some(t => t.tool === currentSelection);
    if (stillExists) {
      toolFilterSelector.value = currentSelection;
    }
  }
}

function updateToolSpecificCharts(tool, toolMetrics) {
  if (tool === 'all') return;
  
  // Get the tool's buffered metrics from server
  const toolHistory = toolMetrics[tool] || [];
  
  // Filter based on current window size
  const cutoff = new Date(Date.now() - WINDOW_SIZE * 1000);
  const filteredHistory = toolHistory.filter(point => {
    const pointTime = new Date(point.timestamp);
    return pointTime >= cutoff;
  });
  
  // Update borrow chart with user annotations
  toolBorrowChart.data.labels = filteredHistory.map(point => {
    const time = new Date(point.timestamp);
    return time.toLocaleTimeString();
  });
  toolBorrowChart.data.datasets[0].data = filteredHistory.map(point => point.count);
  
  // Store metadata for tooltip
  toolBorrowChart.data.datasets[0].metadata = filteredHistory.map(point => ({
    users: point.users,
    count: point.count
  }));
  
  toolBorrowChart.update('none'); // Use 'none' for performance during heavy load
  
  // Fetch current tool status and borrows for other charts
  Promise.all([
    fetch(`/licenses/${encodeURIComponent(tool)}/status`).then(res => res.json()),
    fetch(`/borrows?user=all`).then(res => res.json())
  ]).then(([toolStatus, allBorrows]) => {
    // Update tool info
    document.getElementById('tool-info').textContent = 
      `${toolStatus.borrowed}/${toolStatus.total} in use (${toolStatus.in_commit} commit, ${toolStatus.overage} overage)`;
    
    // Update user distribution (from current borrows)
    const toolBorrows = allBorrows.filter(b => b.tool === tool);
    const userCounts = {};
    toolBorrows.forEach(b => {
      userCounts[b.user] = (userCounts[b.user] || 0) + 1;
    });
    
    toolUserChart.data.labels = Object.keys(userCounts);
    toolUserChart.data.datasets[0].data = Object.values(userCounts);
    toolUserChart.update('none');
    
    // Update commit vs overage chart
    const inCommit = Math.min(toolStatus.borrowed, toolStatus.commit);
    const inOverage = toolStatus.overage;
    const available = toolStatus.available;
    
    toolCommitChart.data.datasets[0].data = [inCommit, inOverage, available];
    toolCommitChart.update('none');
    
    // Update recent events table from historical data
    const recentToolEvents = toolHistory
      .slice(-20) // Last 20 time points
      .reverse()
      .map(point => ({
        time: new Date(point.timestamp).toLocaleTimeString(),
        event: 'Activity',
        user: point.users.join(', '),
        type: point.overage_count > 0 ? `${point.overage_count} Overage` : 'Commit'
      }));
    
    const tbody = document.getElementById('events-tbody');
    if (recentToolEvents.length === 0) {
      tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; padding: 20px; color: #999;">No recent activity</td></tr>';
    } else {
      tbody.innerHTML = recentToolEvents.map(event => `
        <tr style="border-bottom: 1px solid #f0f0f0;">
          <td style="padding: 8px;">${event.time}</td>
          <td style="padding: 8px;">
            <span style="display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #00adef; margin-right: 6px;"></span>
            ${event.event}
          </td>
          <td style="padding: 8px;">${event.user}</td>
          <td style="padding: 8px;">
            ${event.type.includes('Overage') ? `<span style="color: #f57c00; font-weight: 500;">${event.type}</span>` : 
              `<span style="color: #00adef;">${event.type}</span>`}
          </td>
        </tr>
      `).join('');
    }
  }).catch(err => console.error('Error updating tool-specific charts:', err));
}

// Connect to SSE stream
let eventSource = null;
let reconnectAttempts = 0;
const MAX_RECONNECT_ATTEMPTS = 10;

function connectSSE() {
  console.log('Connecting to real-time stream...');
  
  eventSource = new EventSource('/realtime/stream');
  
  eventSource.onopen = () => {
    console.log('✅ Connected to real-time stream');
    reconnectAttempts = 0;
    updateConnectionStatus(true);
  };
  
  eventSource.onerror = (error) => {
    console.error('❌ SSE connection error:', error);
    updateConnectionStatus(false);
    
    // Attempt reconnection
    if (reconnectAttempts < MAX_RECONNECT_ATTEMPTS) {
      reconnectAttempts++;
      const delay = Math.min(1000 * Math.pow(2, reconnectAttempts), 30000);
      console.log(`Reconnecting in ${delay/1000}s... (attempt ${reconnectAttempts}/${MAX_RECONNECT_ATTEMPTS})`);
      
      setTimeout(() => {
        if (eventSource) {
          eventSource.close();
        }
        connectSSE();
      }, delay);
    } else {
      console.error('Max reconnection attempts reached');
      document.getElementById('status-text').textContent = 'Connection failed';
    }
  };
  
  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data);
      
      // Cache the tool metrics from server (includes all historical data)
      if (data.tool_metrics) {
        toolMetricsCache = data.tool_metrics;
      }
      
      updateDashboard(data);
    } catch (error) {
      console.error('Error parsing SSE data:', error);
    }
  };
}

function updateConnectionStatus(connected) {
  const statusEl = document.getElementById('connection-status');
  const textEl = document.getElementById('status-text');
  
  if (connected) {
    statusEl.className = 'connection-status connected';
    textEl.textContent = 'Connected (real-time)';
  } else {
    statusEl.className = 'connection-status disconnected';
    textEl.textContent = 'Disconnected (retrying...)';
  }
}

function updateDashboard(data) {
  // Update tool selector (if tools changed)
  if (data.tools && data.tools.length > 0) {
    updateToolSelector(data.tools);
  }
  
  // Update metric cards (lightweight, always update)
  updateMetricCards(data.rates, data.tools, data.buffer_stats);
  
  // Throttle chart updates using requestAnimationFrame to prevent blocking
  if (!chartUpdateScheduled) {
    chartUpdateScheduled = true;
    requestAnimationFrame(() => {
      chartUpdateScheduled = false;
      updateCharts(data);
    });
  }
}

function updateCharts(data) {
  // Update charts based on selected view
  if (selectedTool === 'all') {
    // Update overview charts from server-buffered history (for correct windowed history)
    if (toolMetricsCache && Object.keys(toolMetricsCache).length > 0) {
      rebuildOverviewFromBuffer(toolMetricsCache);
    } else {
      // Fallback to live tick if buffer not yet available
      updateBorrowRateChart(data.rates.borrow_per_min);
      updateOverageChart(data.recent_events.borrows);
    }
    updateUtilizationChart(data.tools);
  } else {
    // Update tool-specific charts with server-buffered data
    if (toolMetricsCache && toolMetricsCache[selectedTool]) {
      updateToolSpecificCharts(selectedTool, toolMetricsCache);
    }
  }
}

// Build overview charts from buffered per-tool metrics
function rebuildOverviewFromBuffer(toolMetrics) {
  // Aggregate per-minute across all tools within current WINDOW_SIZE
  const cutoffMs = Date.now() - WINDOW_SIZE * 1000;
  const bucketMap = new Map(); // ts (ISO) -> {count, overage}
  
  Object.keys(toolMetrics).forEach(tool => {
    const series = toolMetrics[tool] || [];
    series.forEach(point => {
      const tsMs = new Date(point.timestamp).getTime();
      if (tsMs < cutoffMs) return;
      const key = point.timestamp; // already minute-rounded server-side
      const prev = bucketMap.get(key) || { count: 0, overage: 0 };
      prev.count += (point.count || 0);
      prev.overage += (point.overage_count || 0);
      bucketMap.set(key, prev);
    });
  });
  
  // Sort by timestamp
  const entries = Array.from(bucketMap.entries()).sort((a, b) => new Date(a[0]) - new Date(b[0]));
  const labels = entries.map(([ts]) => new Date(ts).toLocaleTimeString());
  const borrowCounts = entries.map(([, v]) => v.count);
  const overageCounts = entries.map(([, v]) => v.overage);
  
  // Replace entire datasets for accurate history
  borrowRateChart.data.labels = labels;
  borrowRateChart.data.datasets[0].data = borrowCounts;
  borrowRateChart.update('none'); // Use 'none' for performance during heavy load
  
  overageChart.data.labels = labels;
  overageChart.data.datasets[0].data = overageCounts;
  overageChart.update('none'); // Use 'none' for performance during heavy load
}

function updateMetricCards(rates, tools, bufferStats) {
  // Borrow rate
  const borrowRate = Math.round(rates.borrow_per_min);
  document.getElementById('borrow-rate').textContent = borrowRate;
  
  // Pulse animation when activity detected
  const borrowCard = document.getElementById('borrow-card');
  if (borrowRate > lastBorrowRate) {
    borrowCard.classList.add('pulse-active');
    setTimeout(() => borrowCard.classList.remove('pulse-active'), 1000);
  }
  lastBorrowRate = borrowRate;
  
  // Overage rate with color coding
  const overageRate = rates.overage_percent;
  const overageEl = document.getElementById('overage-rate');
  const overageCard = document.getElementById('overage-card');
  overageEl.textContent = overageRate.toFixed(1) + '%';
  
  // Color code based on threshold
  overageEl.className = 'metric-value';
  if (overageRate > 30) {
    overageEl.classList.add('critical');
    overageCard.classList.add('pulse-active');
  } else if (overageRate > 15) {
    overageEl.classList.add('warning');
  }
  
  // Pulse when overage increases
  if (overageRate > lastOverageRate) {
    overageCard.classList.add('pulse-active');
    setTimeout(() => overageCard.classList.remove('pulse-active'), 1000);
  }
  lastOverageRate = overageRate;
  
  // Return rate
  document.getElementById('return-rate').textContent = Math.round(rates.return_per_min);
  
  // Failure rate
  document.getElementById('failure-rate').textContent = Math.round(rates.failure_per_min);
  
  // Active licenses (total borrowed across all tools)
  const totalBorrowed = tools.reduce((sum, t) => sum + t.borrowed, 0);
  document.getElementById('active-licenses').textContent = totalBorrowed;
  
  // Buffer size
  document.getElementById('buffer-size').textContent = bufferStats.total_events.toLocaleString();
}

function updateBorrowRateChart(borrowRate) {
  const now = new Date();
  const label = now.toLocaleTimeString();
  
  // Add data point
  borrowRateChart.data.labels.push(label);
  borrowRateChart.data.datasets[0].data.push(borrowRate);
  
  // Keep only last WINDOW_SIZE points
  if (borrowRateChart.data.labels.length > WINDOW_SIZE) {
    borrowRateChart.data.labels.shift();
    borrowRateChart.data.datasets[0].data.shift();
  }
  
  borrowRateChart.update('none'); // Use 'none' for performance during heavy load
}

function updateOverageChart(recentBorrows) {
  const now = new Date();
  const label = now.toLocaleTimeString();
  
  // Count overage borrows in recent events
  const overageCount = recentBorrows.filter(b => b.is_overage).length;
  
  // Add data point
  overageChart.data.labels.push(label);
  overageChart.data.datasets[0].data.push(overageCount);
  
  // Keep only last WINDOW_SIZE points
  if (overageChart.data.labels.length > WINDOW_SIZE) {
    overageChart.data.labels.shift();
    overageChart.data.datasets[0].data.shift();
  }
  
  overageChart.update('none'); // Use 'none' for performance during heavy load
}

function updateUtilizationChart(tools) {
  // Sort tools by name for consistent ordering
  const sortedTools = [...tools].sort((a, b) => a.tool.localeCompare(b.tool));
  
  // Shorten tool names for better display
  utilizationChart.data.labels = sortedTools.map(t => {
    const parts = t.tool.split(' - ');
    return parts.length > 1 ? parts[1] : t.tool;
  });
  
  // Calculate stacked bar data
  const inCommit = sortedTools.map(t => Math.min(t.borrowed, t.commit));
  const inOverage = sortedTools.map(t => t.overage);
  const available = sortedTools.map(t => t.available);
  
  utilizationChart.data.datasets[0].data = inCommit;
  utilizationChart.data.datasets[1].data = inOverage;
  utilizationChart.data.datasets[2].data = available;
  
  utilizationChart.update('none'); // Use 'none' for performance during heavy load
}

// Initialize connection
connectSSE();

// Cleanup on page unload
window.addEventListener('beforeunload', () => {
  if (eventSource) {
    eventSource.close();
  }
});

// Log for debugging
console.log('Real-Time Dashboard initialized');
console.log('- SSE endpoint: /realtime/stream');
console.log('- Update interval: 2 seconds');
console.log('- Data retention: 6 hours');
console.log('- Default chart window: 30 minutes (configurable)');
console.log('- Available ranges: 1min, 5min, 10min, 30min, 1h, 3h, 6h');

