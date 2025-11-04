use clap::Parser;
use colored::*;
use indicatif::{MultiProgress, ProgressBar, ProgressStyle};
use rand::Rng;
use reqwest::Client;
use serde::{Deserialize, Serialize};
use std::sync::Arc;
use std::time::{Duration, Instant};
use tokio::sync::Semaphore;
use tokio::time::sleep;

#[derive(Parser, Debug)]
#[command(author, version, about = "License Server Stress Testing Tool", long_about = None)]
struct Args {
    /// Server URL
    #[arg(short, long, default_value = "http://localhost:8000")]
    url: String,

    /// Number of concurrent workers
    #[arg(short = 'w', long, default_value = "10")]
    workers: usize,

    /// Total number of operations
    #[arg(short = 'n', long, default_value = "100")]
    operations: usize,

    /// Tool to test (specific tool name or "random" for all)
    #[arg(short, long, default_value = "random")]
    tool: String,

    /// Hold time in seconds (how long to keep license borrowed)
    #[arg(short = 'H', long, default_value = "1")]
    hold_time: u64,

    /// Test mode: checkout-only, return-all, or full-cycle
    #[arg(short, long, default_value = "full-cycle")]
    mode: String,

    /// Ramp-up time in seconds (gradually increase load)
    #[arg(short, long, default_value = "0")]
    ramp_up: u64,
}

#[derive(Debug, Serialize, Deserialize)]
struct BorrowRequest {
    tool: String,
    user: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct BorrowResponse {
    id: String,
    tool: String,
    user: String,
    borrowed_at: String,
}

#[derive(Debug, Serialize, Deserialize)]
struct StatusResponse {
    tool: String,
    total: i32,
    borrowed: i32,
    available: i32,
}

#[derive(Debug, Clone)]
struct TestStats {
    successful_borrows: usize,
    failed_borrows: usize,
    successful_returns: usize,
    failed_returns: usize,
    total_duration: Duration,
}

impl TestStats {
    fn new() -> Self {
        Self {
            successful_borrows: 0,
            failed_borrows: 0,
            successful_returns: 0,
            failed_returns: 0,
            total_duration: Duration::from_secs(0),
        }
    }
}

async fn borrow_license(
    client: &Client,
    base_url: &str,
    tool: &str,
    user: &str,
) -> Result<BorrowResponse, String> {
    let url = format!("{}/licenses/borrow", base_url);
    let req = BorrowRequest {
        tool: tool.to_string(),
        user: user.to_string(),
    };

    let response = client
        .post(&url)
        .json(&req)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    if response.status().is_success() {
        response
            .json::<BorrowResponse>()
            .await
            .map_err(|e| format!("Parse failed: {}", e))
    } else {
        Err(format!("HTTP {}: {}", response.status(), response.text().await.unwrap_or_default()))
    }
}

async fn return_license(
    client: &Client,
    base_url: &str,
    borrow_id: &str,
) -> Result<(), String> {
    let url = format!("{}/licenses/return", base_url);
    
    #[derive(Serialize)]
    struct ReturnRequest {
        id: String,
    }
    
    let req = ReturnRequest {
        id: borrow_id.to_string(),
    };

    let response = client
        .post(&url)
        .json(&req)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    if response.status().is_success() {
        Ok(())
    } else {
        Err(format!("HTTP {}: {}", response.status(), response.text().await.unwrap_or_default()))
    }
}

async fn get_status(client: &Client, base_url: &str) -> Result<Vec<StatusResponse>, String> {
    let url = format!("{}/licenses/status", base_url);

    let response = client
        .get(&url)
        .send()
        .await
        .map_err(|e| format!("Request failed: {}", e))?;

    if response.status().is_success() {
        response
            .json::<Vec<StatusResponse>>()
            .await
            .map_err(|e| format!("Parse failed: {}", e))
    } else {
        Err(format!("HTTP {}", response.status()))
    }
}

fn get_random_tool() -> &'static str {
    let tools = [
        "ECU Development Suite",
        "GreenHills Multi IDE",
        "AUTOSAR Configuration Tool",
        "CAN Bus Analyzer Pro",
        "Model-Based Design Studio",
    ];
    let mut rng = rand::thread_rng();
    tools[rng.gen_range(0..tools.len())]
}

async fn run_worker(
    worker_id: usize,
    client: Arc<Client>,
    base_url: Arc<String>,
    tool: Arc<String>,
    hold_time: u64,
    mode: Arc<String>,
    operations: usize,
    semaphore: Arc<Semaphore>,
    progress: ProgressBar,
) -> TestStats {
    let mut stats = TestStats::new();
    let start = Instant::now();

    for i in 0..operations {
        let _permit = semaphore.acquire().await.unwrap();

        let selected_tool = if tool.as_str() == "random" {
            get_random_tool()
        } else {
            tool.as_str()
        };

        let user = format!("stress-worker-{}", worker_id);

        // Borrow phase
        match borrow_license(&client, &base_url, selected_tool, &user).await {
            Ok(borrow_response) => {
                stats.successful_borrows += 1;
                progress.set_message(format!(
                    "Worker {} | Borrow ✓ {} | Op {}/{}",
                    worker_id, selected_tool, i + 1, operations
                ));

                if mode.as_str() == "full-cycle" {
                    // Hold the license
                    sleep(Duration::from_secs(hold_time)).await;

                    // Return phase
                    match return_license(&client, &base_url, &borrow_response.id).await {
                        Ok(_) => {
                            stats.successful_returns += 1;
                            progress.set_message(format!(
                                "Worker {} | Return ✓ {} | Op {}/{}",
                                worker_id, selected_tool, i + 1, operations
                            ));
                        }
                        Err(e) => {
                            stats.failed_returns += 1;
                            progress.set_message(format!(
                                "Worker {} | Return ✗ {} | Op {}/{}",
                                worker_id, e, i + 1, operations
                            ));
                        }
                    }
                }
            }
            Err(e) => {
                stats.failed_borrows += 1;
                progress.set_message(format!(
                    "Worker {} | Borrow ✗ {} | Op {}/{}",
                    worker_id, e, i + 1, operations
                ));
            }
        }

        progress.inc(1);

        // Small delay to avoid overwhelming the server
        sleep(Duration::from_millis(10)).await;
    }

    stats.total_duration = start.elapsed();
    progress.finish_with_message(format!("Worker {} completed", worker_id));
    stats
}

#[tokio::main]
async fn main() {
    let args = Args::parse();

    println!("{}", "╔══════════════════════════════════════════════════════════╗".cyan().bold());
    println!("{}", "║   License Server Stress Test                             ║".cyan().bold());
    println!("{}", "╚══════════════════════════════════════════════════════════╝".cyan().bold());
    println!();

    println!("{}", "Configuration:".yellow().bold());
    println!("  Server:      {}", args.url.green());
    println!("  Workers:     {}", args.workers.to_string().green());
    println!("  Operations:  {} per worker", args.operations.to_string().green());
    println!("  Total Ops:   {}", (args.workers * args.operations).to_string().green().bold());
    println!("  Tool:        {}", args.tool.green());
    println!("  Hold Time:   {}s", args.hold_time.to_string().green());
    println!("  Mode:        {}", args.mode.green());
    println!("  Ramp-up:     {}s", args.ramp_up.to_string().green());
    println!();

    let client = Arc::new(
        Client::builder()
            .timeout(Duration::from_secs(30))
            .build()
            .expect("Failed to create HTTP client"),
    );

    // Check server status
    print!("{}", "🔍 Checking server status... ".cyan());
    match get_status(&client, &args.url).await {
        Ok(statuses) => {
            println!("{}", "✓".green().bold());
            for status in statuses {
                println!(
                    "   {} → {} total, {} borrowed, {} available",
                    status.tool.yellow(),
                    status.total,
                    status.borrowed.to_string().red(),
                    status.available.to_string().green()
                );
            }
        }
        Err(e) => {
            println!("{}", "✗".red().bold());
            eprintln!("{} {}", "Error:".red().bold(), e);
            std::process::exit(1);
        }
    }
    println!();

    println!("{}", "🚀 Starting stress test...".cyan().bold());
    println!();

    let multi_progress = MultiProgress::new();
    let style = ProgressStyle::default_bar()
        .template("[{bar:40.cyan/blue}] {pos}/{len} {msg}")
        .unwrap()
        .progress_chars("█▓▒░ ");

    let base_url = Arc::new(args.url.clone());
    let tool = Arc::new(args.tool.clone());
    let mode = Arc::new(args.mode.clone());
    let semaphore = Arc::new(Semaphore::new(args.workers));

    let start_time = Instant::now();

    let mut handles = vec![];

    for worker_id in 0..args.workers {
        let client = Arc::clone(&client);
        let base_url = Arc::clone(&base_url);
        let tool = Arc::clone(&tool);
        let mode = Arc::clone(&mode);
        let semaphore = Arc::clone(&semaphore);

        let progress = multi_progress.add(ProgressBar::new(args.operations as u64));
        progress.set_style(style.clone());

        // Ramp-up delay
        if args.ramp_up > 0 {
            let delay = (args.ramp_up * 1000) / args.workers as u64;
            sleep(Duration::from_millis(delay * worker_id as u64)).await;
        }

        let handle = tokio::spawn(async move {
            run_worker(
                worker_id,
                client,
                base_url,
                tool,
                args.hold_time,
                mode,
                args.operations,
                semaphore,
                progress,
            )
            .await
        });

        handles.push(handle);
    }

    // Wait for all workers
    let mut all_stats = TestStats::new();
    for handle in handles {
        let stats = handle.await.expect("Worker panicked");
        all_stats.successful_borrows += stats.successful_borrows;
        all_stats.failed_borrows += stats.failed_borrows;
        all_stats.successful_returns += stats.successful_returns;
        all_stats.failed_returns += stats.failed_returns;
    }

    let total_time = start_time.elapsed();

    println!();
    println!("{}", "╔══════════════════════════════════════════════════════════╗".cyan().bold());
    println!("{}", "║   Test Results                                           ║".cyan().bold());
    println!("{}", "╚══════════════════════════════════════════════════════════╝".cyan().bold());
    println!();

    println!("{}", "Performance:".yellow().bold());
    println!("  Total Time:         {:.2}s", total_time.as_secs_f64());
    println!(
        "  Throughput:         {:.2} ops/sec",
        (all_stats.successful_borrows + all_stats.successful_returns) as f64 / total_time.as_secs_f64()
    );
    println!();

    println!("{}", "Borrow Operations:".yellow().bold());
    println!("  Successful:         {} {}", all_stats.successful_borrows, "✓".green());
    println!("  Failed:             {} {}", all_stats.failed_borrows, if all_stats.failed_borrows > 0 { "✗".red() } else { "✓".green() });
    let borrow_success_rate = if all_stats.successful_borrows + all_stats.failed_borrows > 0 {
        (all_stats.successful_borrows as f64 / (all_stats.successful_borrows + all_stats.failed_borrows) as f64) * 100.0
    } else {
        0.0
    };
    println!("  Success Rate:       {:.2}%", borrow_success_rate);
    println!();

    if args.mode == "full-cycle" {
        println!("{}", "Return Operations:".yellow().bold());
        println!("  Successful:         {} {}", all_stats.successful_returns, "✓".green());
        println!("  Failed:             {} {}", all_stats.failed_returns, if all_stats.failed_returns > 0 { "✗".red() } else { "✓".green() });
        let return_success_rate = if all_stats.successful_returns + all_stats.failed_returns > 0 {
            (all_stats.successful_returns as f64 / (all_stats.successful_returns + all_stats.failed_returns) as f64) * 100.0
        } else {
            0.0
        };
        println!("  Success Rate:       {:.2}%", return_success_rate);
        println!();
    }

    // Final server status
    println!("{}", "Final Server Status:".yellow().bold());
    match get_status(&client, &args.url).await {
        Ok(statuses) => {
            for status in statuses {
                println!(
                    "  {} → {} total, {} borrowed, {} available",
                    status.tool.yellow(),
                    status.total,
                    status.borrowed.to_string().red(),
                    status.available.to_string().green()
                );
            }
        }
        Err(e) => {
            eprintln!("  {} {}", "Error:".red().bold(), e);
        }
    }
    println!();

    if all_stats.failed_borrows == 0 && all_stats.failed_returns == 0 {
        println!("{}", "🎉 All operations completed successfully!".green().bold());
    } else {
        println!("{}", "⚠️  Some operations failed - check server logs".yellow().bold());
    }
}

