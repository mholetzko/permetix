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

// Metrics tracking
let WINDOW_SIZE = 1800; // Default: 30 minutes (in seconds)
let lastBorrowRate = 0;
let lastOverageRate = 0;

// Time range selector
const timeRangeSelector = document.getElementById('time-range');
timeRangeSelector.addEventListener('change', (e) => {
  const newRange = parseInt(e.target.value);
  WINDOW_SIZE = newRange;
  
  // Update chart titles
  const label = getTimeRangeLabel(newRange);
  document.getElementById('borrow-chart-title').textContent = `License Borrows (Last ${label})`;
  document.getElementById('overage-chart-title').textContent = `Overage Checkouts (Last ${label})`;
  
  // Clear charts to start fresh with new range
  borrowRateChart.data.labels = [];
  borrowRateChart.data.datasets[0].data = [];
  overageChart.data.labels = [];
  overageChart.data.datasets[0].data = [];
  borrowRateChart.update();
  overageChart.update();
  
  console.log(`Time range changed to: ${label} (${newRange} seconds)`);
});

function getTimeRangeLabel(seconds) {
  if (seconds < 60) return `${seconds} seconds`;
  if (seconds < 3600) return `${Math.round(seconds / 60)} minutes`;
  return `${Math.round(seconds / 3600)} hour${seconds > 3600 ? 's' : ''}`;
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
  // Update metric cards
  updateMetricCards(data.rates, data.tools, data.buffer_stats);
  
  // Update charts
  updateBorrowRateChart(data.rates.borrow_per_min);
  updateOverageChart(data.recent_events.borrows);
  updateUtilizationChart(data.tools);
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
  
  borrowRateChart.update('none'); // Update without animation for smoothness
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
  
  overageChart.update('none');
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
  
  utilizationChart.update('none');
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
console.log('- Update interval: 1 second');
console.log('- Data retention: 6 hours');
console.log('- Default chart window: 30 minutes (configurable)');
console.log('- Available ranges: 1min, 5min, 10min, 30min, 1h, 3h, 6h');

